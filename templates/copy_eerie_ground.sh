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

SRC_ERA_HOST=%ERA.HOST%
SRC_ERA_BASE=%ERA.PATH%
SRC_ERA_BASE="${SRC_ERA_BASE%/}"

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

SAME_ERA_HOST=0
if [ "$SRC_ERA_HOST" = "$DST_HOST" ]; then
  SAME_ERA_HOST=1
fi

copy_file() {
  local src="$1" dst="$2"

  # Skip missing source files instead of failing the whole job.
  if [ "$SAME_HOST" -eq 1 ]; then
    if [ ! -f "$src" ]; then
      echo "WARN: source file not found, skipping: $src" >&2
      return 0
    fi
  else
    # Important: redirect stdin from /dev/null so ssh does not consume
    # the input stream used by the outer while-read loop.
    if ! ssh $SSHOPTS "$SRC_HOST" "test -f '$src'" >/dev/null 2>&1 < /dev/null; then
      echo "WARN: source file not found on $SRC_HOST, skipping: $src" >&2
      return 0
    fi
  fi

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
    # Important: redirect stdin from /dev/null so scp does not consume
    # the input stream used by the outer while-read loop.
    run "scp $SSHOPTS -p \"$SRC_HOST\":\"$src\" \"$DST_HOST\":\"$dst\" < /dev/null"
  fi
}

mk_dst_dir() {
  local d="$1"
  if [ "$SAME_HOST" -eq 1 ]; then
    run "mkdir -p \"$d\""
  else
    # Important: redirect stdin from /dev/null so ssh does not interfere
    # with any surrounding while-read loops.
    run "ssh $SSHOPTS \"$DST_HOST\" \"mkdir -p '$d'\" < /dev/null"
  fi
}

copy_era_file() {
  local src="$1" dst="$2"

  if [ "$SAME_ERA_HOST" -eq 1 ]; then
    if [ ! -f "$src" ]; then
      echo "WARN: source ERA file not found, skipping: $src" >&2
      return 0
    fi
  else
    if ! ssh $SSHOPTS "$SRC_ERA_HOST" "test -f '$src'" >/dev/null 2>&1 < /dev/null; then
      echo "WARN: source ERA file not found on $SRC_ERA_HOST, skipping: $src" >&2
      return 0
    fi
  fi

  if [ "$SAME_ERA_HOST" -eq 1 ]; then
    local dstdir
    dstdir="$(dirname "$dst")"
    run "mkdir -p \"$dstdir\""
    run "cp -p \"$src\" \"$dst\""
  else
    run "scp $SSHOPTS -p \"$SRC_ERA_HOST\":\"$src\" \"$DST_HOST\":\"$dst\" < /dev/null"
  fi
}

mk_era_dst_dir() {
  local d="$1"
  if [ "$SAME_ERA_HOST" -eq 1 ]; then
    run "mkdir -p \"$d\""
  else
    run "ssh $SSHOPTS \"$DST_HOST\" \"mkdir -p '$d'\" < /dev/null"
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

DEST_BASE_EERIE="${HPCROOTDIR}/truth/temp/eerie"
DEST_BASE_ERA="${HPCROOTDIR}/truth/temp/era"
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
  # Important: redirect stdin from /dev/null so ssh does not consume
  # input from later while-read loops.
  run "ssh $SSHOPTS \"$DST_HOST\" true < /dev/null"
fi
if [ "$SAME_ERA_HOST" -eq 0 ]; then
  run "ssh $SSHOPTS \"$SRC_ERA_HOST\" true < /dev/null"
fi

# Create EERIE destination directories ONCE
for var in "${VARS[@]}"; do
  for mem in "${MEMBERS[@]}"; do
    dst_dir="${DEST_BASE_EERIE}/${START_TIME}/${var}/${mem}"
    mk_dst_dir "$dst_dir"
  done
done

# Iterate days (portable)
while IFS= read -r ymd; do
  for var in "${VARS[@]}"; do
    for mem in "${MEMBERS[@]}"; do
      src_file="${SRC_BASE}/${var}/${mem}/${var}_${ymd}.nc"
      dst_dir="${DEST_BASE_EERIE}/${START_TIME}/${var}/${mem}"
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

# -----------------------
# ERA5 monthly files (no members)
# -----------------------

# Create ERA destination directories ONCE
for var in "${VARS[@]}"; do
  dst_dir="${DEST_BASE_ERA}/${START_TIME}/${var}"
  mk_era_dst_dir "$dst_dir"
done

# Iterate months for ERA (portable, deduplicated)
while IFS= read -r ym; do
  for var in "${VARS[@]}"; do
    src_file="${SRC_ERA_BASE}/${var}/${var}_${ym}.nc"
    dst_dir="${DEST_BASE_ERA}/${START_TIME}/${var}"
    dst_file="${dst_dir}/${var}_${ym}.nc"
    copy_era_file "$src_file" "$dst_file"
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

seen = set()
cur = start
one = timedelta(days=1)
while cur <= end:
    ym = cur.strftime("%Y%m")
    if ym not in seen:
        seen.add(ym)
        print(ym)
    cur += one
PY
)