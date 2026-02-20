#!/usr/bin/env bash
set -euo pipefail
set -x

# Autosubmit variables (vengono sostituite nel template)
PROJDIR="%PROJECT.PROJECT_DESTINATION%"
SUBMODULE_DIR="$PROJDIR/AIUQ-engine"

# Vai nella root progetto (così mkdir/controlli sono coerenti)
cd "$PROJDIR"

# Sanity checks
if [ ! -d "$SUBMODULE_DIR" ]; then
  echo "ERROR: submodule dir not found: $SUBMODULE_DIR"
  echo "Content of PROJDIR:"
  ls -la "$PROJDIR"
  exit 1
fi

# Helper: crea symlink se non esiste già
link_if_missing () {
  local src="$1"
  local dst="$2"

  if [ -e "$dst" ] || [ -L "$dst" ]; then
    return 0
  fi
  mkdir -p "$(dirname "$dst")"
  ln -s "$src" "$dst"
}

# ---- conf/AIUQ-st (ricorsivo: linka cartelle v000/v010 ecc.) ----
mkdir -p conf/AIUQ-st
for p in "$SUBMODULE_DIR/conf/AIUQ-st/"*; do
  base="$(basename "$p")"
  link_if_missing "../AIUQ-engine/conf/AIUQ-st/$base" "conf/AIUQ-st/$base"
done

# ---- conf/cards (qui hai sottocartelle ics/models: linka ricorsivo) ----
mkdir -p conf/cards
for p in "$SUBMODULE_DIR/conf/cards/"*; do
  base="$(basename "$p")"
  link_if_missing "../AIUQ-engine/conf/cards/$base" "conf/cards/$base"
done

# ---- templates ----
mkdir -p templates
for p in "$SUBMODULE_DIR/templates/"*; do
  base="$(basename "$p")"
  link_if_missing "../AIUQ-engine/templates/$base" "templates/$base"
done

# ---- runscripts ----
mkdir -p runscripts
for p in "$SUBMODULE_DIR/runscripts/"*; do
  base="$(basename "$p")"
  link_if_missing "../AIUQ-engine/runscripts/$base" "runscripts/$base"
done

# ---- lib ----
mkdir -p lib
for p in "$SUBMODULE_DIR/lib/"*; do
  base="$(basename "$p")"
  link_if_missing "../AIUQ-engine/lib/$base" "lib/$base"
done

echo "OK: symlinks created in $PROJDIR"