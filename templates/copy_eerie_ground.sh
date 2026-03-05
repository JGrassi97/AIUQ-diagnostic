#!/bin/bash
set -euo pipefail

HPCROOTDIR=%HPCROOTDIR%
EXPID=%DEFAULT.EXPID%
JOBNAME=%JOBNAME%
ROOTDIR=%ROOTDIR%

JOBNAME_WITHOUT_EXPID=$(echo "${JOBNAME}" | sed 's/^[^_]*_//')
LOGS_DIR="${ROOTDIR}/tmp"
CONFIGFILE="${LOGS_DIR}/config_${JOBNAME_WITHOUT_EXPID}"

DRY_RUN="${DRY_RUN:-0}"

SRC_HOST="jgrassi@mafalda.polito.it"
SRC_BASE="/data/users/jgrassi/eerie/amip/day"
DST_HOST="bsc850074@glogin2.bsc.es"

SRC_BASE="${SRC_BASE%/}"

# -----------------------
# Helpers (must be before use)
# -----------------------
run() {
  if [ "${DRY_RUN}" = "1" ]; then
    echo "$@"
  else
    eval "$@"
  fi
}

copy_file() {
  local src="$1" dst="$2"
  run "scp -p \"$SRC_HOST\":\"$src\" \"$DST_HOST\":\"$dst\""
}

# -----------------------
# Read config (YAML) -> bash vars
# -----------------------
read -r INI_DATA_PATH START_TIME END_TIME OUT_VARS_JSON <<<"$(
python3 - "$CONFIGFILE" <<'PY'
import sys, json, re, yaml
cfg = yaml.safe_load(open(sys.argv[1]))

ini = cfg["INI_DATA_PATH"]
start = str(cfg["START_TIME"])
end = str(cfg["END_TIME"])
out = cfg["OUT_VARS"]

if isinstance(out, (list, tuple)):
    vars_list = list(out)
else:
    s = str(out).strip()
    try:
        vars_list = json.loads(s.replace("'", '"'))
    except Exception:
        vars_list = re.findall(r"[A-Za-z0-9_]+", s)

print(ini, start, end, json.dumps(vars_list))
PY
)"

# Basic sanity (avoid -u explosions later)
: "${START_TIME:?START_TIME empty}"
: "${END_TIME:?END_TIME empty}"
: "${OUT_VARS_JSON:?OUT_VARS_JSON empty}"

DEST_BASE="${HPCROOTDIR}/truth/temp"
MEMBERS=(1 2 3 4 5)

# -----------------------
# Build VARS array from JSON (bash 3.2 compatible)
# -----------------------
VARS=()
while IFS= read -r v; do
  [ -n "$v" ] && VARS+=("$v")
done < <(python3 - <<PY
import json
for x in json.loads('''$OUT_VARS_JSON'''):
    print(x)
PY
)

if [ "${#VARS[@]}" -eq 0 ]; then
  echo "ERROR: VARS array is empty (OUT_VARS_JSON=$OUT_VARS_JSON)" >&2
  exit 1
fi

# -----------------------
# Iterate days: START_TIME/END_TIME are yyyy-mm-dd; produce yyyymmdd
# (No `date -d`, portable across macOS/Linux)
# -----------------------
while IFS= read -r ymd; do
  for var in "${VARS[@]}"; do
    for mem in "${MEMBERS[@]}"; do
      src_file="${SRC_BASE}/${var}/${mem}/${ymd}.nc"
      dst_dir="${DEST_BASE}/${var}/${mem}"
      dst_file="${dst_dir}/${ymd}.nc"

      run "ssh \"$DST_HOST\" \"mkdir -p '$dst_dir'\""
      copy_file "$src_file" "$dst_file"
    done
  done
done < <(python3 - "$START_TIME" "$END_TIME" <<'PY'
import sys
from datetime import date, timedelta

start_s = sys.argv[1]
end_s   = sys.argv[2]

y, m, d = map(int, start_s.split("-"))
start = date(y, m, d)

y, m, d = map(int, end_s.split("-"))
end = date(y, m, d)

cur = start
one = timedelta(days=1)
while cur <= end:
    print(cur.strftime("%Y%m%d"))
    cur += one
PY
)