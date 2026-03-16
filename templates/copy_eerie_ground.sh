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

HPCUSER=%HPCUSER%
HPCHOST=%HPCHOST%

SRC_HOST=%EERIE.HOST%
SRC_BASE=%EERIE.PATH%
EERIE_MEMBERS="%EERIE.MEMBERS%"
DST_HOST="${HPCUSER}@${HPCHOST}"

SRC_BASE="${SRC_BASE%/}"

# -----------------------
# SSH reuse (faster for remote)
# -----------------------
CTL_DIR="${ROOTDIR}/tmp"
mkdir -p "$CTL_DIR"
CTL_PATH="${CTL_DIR}/sshctl_%r@%h:%p"
SSHOPTS="-o ControlMaster=auto -o ControlPersist=15m -o ControlPath=$CTL_PATH -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o BatchMode=yes"

# -----------------------
# Helpers
# -----------------------
run() {
  if [ "${DRY_RUN}" = "1" ]; then
    echo "$@"
  else
    eval "$@"
  fi
}

# Decide if source and destination are the same host
# (string-equality is enough in your templated setup)
SAME_HOST=0
if [ "$SRC_HOST" = "$DST_HOST" ]; then
  SAME_HOST=1
fi

copy_file() {
  local src="$1" dst="$2"

  if [ "$SAME_HOST" -eq 1 ]; then
    # Local copy: much faster than scp
    # Ensure parent exists (local)
    local dstdir
    dstdir="$(dirname "$dst")"
    run "mkdir -p \"$dstdir\""
    run "cp -p \"$src\" \"$dst\""
    # Alternative (often even better for many files): rsync
    # run "rsync -a --inplace \"$src\" \"$dst\""
  else
    # Remote copy
    run "scp $SSHOPTS -p \"$SRC_HOST\":\"$src\" \"$DST_HOST\":\"$dst\""
  fi
}

mk_dst_dir() {
  local d="$1"
  if [ "$SAME_HOST" -eq 1 ]; then
    run "mkdir -p \"$d\""
  else
    run "ssh $SSHOPTS \"$DST_HOST\" \"mkdir -p '$d'\""
  fi
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

: "${START_TIME:?START_TIME empty}"
: "${END_TIME:?END_TIME empty}"
: "${OUT_VARS_JSON:?OUT_VARS_JSON empty}"

DEST_BASE="${HPCROOTDIR}/truth/temp"
read -r -a MEMBERS <<< "$EERIE_MEMBERS"

if [ "${#MEMBERS[@]}" -eq 0 ]; then
  echo "ERROR: EERIE_MEMBERS is empty" >&2
  exit 1
fi

# Build VARS array (bash 3.2 compatible)
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

# Warm up remote connection only if needed
if [ "$SAME_HOST" -eq 0 ]; then
  run "ssh $SSHOPTS \"$DST_HOST\" true"
fi

# Create destination directories ONCE
for var in "${VARS[@]}"; do
  for mem in "${MEMBERS[@]}"; do
    dst_dir="${DEST_BASE}/${START_TIME}/${var}/${mem}"
    mk_dst_dir "$dst_dir"
  done
done

# Iterate days (portable)
while IFS= read -r ymd; do
  for var in "${VARS[@]}"; do
    for mem in "${MEMBERS[@]}"; do
      src_file="${SRC_BASE}/${var}/${mem}/${var}_${ymd}.nc"
      dst_dir="${DEST_BASE}/${START_TIME}/${var}/${mem}"
      dst_file="${dst_dir}/${var}_${ymd}.nc"
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