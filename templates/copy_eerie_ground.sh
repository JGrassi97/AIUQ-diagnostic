#!/bin/bash
set -euo pipefail

HPCROOTDIR=%HPCROOTDIR%
EXPID=%DEFAULT.EXPID%
JOBNAME=%JOBNAME%

JOBNAME_WITHOUT_EXPID=$(echo "${JOBNAME}" | sed 's/^[^_]*_//')
LOGS_DIR="${HPCROOTDIR}/LOG_${EXPID}"
CONFIGFILE="${LOGS_DIR}/config_${JOBNAME_WITHOUT_EXPID}"

DRY_RUN="${DRY_RUN:-0}"

SRC_HOST="jgrassi@mafalda.polito.it"
SRC_BASE="/data/users/jgrassi/eerie/amip/day"
DST_HOST="bsc850074@glogin2.bsc.es"

SRC_BASE="${SRC_BASE%/}"

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

DEST_BASE="${HPCROOTDIR}/truth/temp"
MEMBERS=(1 2 3 4 5)

start_epoch=$(date -d "$START_TIME" +%s)
end_epoch=$(date -d "$END_TIME" +%s)

mapfile -t VARS < <(python3 - <<PY
import json
print("\n".join(json.loads('''$OUT_VARS_JSON''')))
PY
)

run() { [[ "$DRY_RUN" == "1" ]] && echo "$*" || eval "$@"; }

copy_file() {
  local src="$1" dst="$2"
  run "scp -p \"$SRC_HOST\":\"$src\" \"$DST_HOST\":\"$dst\""
}

day_epoch="$start_epoch"
one_day=$((24*3600))

while (( day_epoch <= end_epoch )); do
  ymd=$(date -u -d "@$day_epoch" +%Y%m%d)

  for var in "${VARS[@]}"; do
    for mem in "${MEMBERS[@]}"; do
      src_file="${SRC_BASE}/${var}/${mem}/${ymd}.nc"
      dst_dir="${DEST_BASE}/${var}/${mem}"
      dst_file="${dst_dir}/${ymd}.nc"

      run "ssh \"$DST_HOST\" \"mkdir -p '$dst_dir'\""
      copy_file "$src_file" "$dst_file"
    done
  done

  day_epoch=$((day_epoch + one_day))
done