#!/usr/bin/env bash
set -euo pipefail
set -x

PROJDIR="%PROJDIR%"
SUBMODULE_DIR="$PROJDIR/AIUQ-engine"

cd "$PROJDIR"

if [ ! -d "$SUBMODULE_DIR" ]; then
  echo "ERROR: submodule dir not found: $SUBMODULE_DIR"
  ls -la "$PROJDIR"
  exit 1
fi

# Linka ricorsivamente il contenuto di $src_dir dentro $dst_dir
# - crea directory
# - crea symlink per file
link_tree () {
  local src_dir="$1"
  local dst_dir="$2"

  mkdir -p "$dst_dir"

  # Trova sia file che directory, ricorsivo (esclude .git se presente)
  # -print0 per gestire spazi
  find "$src_dir" -mindepth 1 -not -path "*/.git/*" -print0 | while IFS= read -r -d '' item; do
    # path relativo rispetto a src_dir
    rel="${item#"$src_dir"/}"
    dst="$dst_dir/$rel"

    if [ -d "$item" ] && [ ! -L "$item" ]; then
      # directory reale: crea directory corrispondente
      mkdir -p "$dst"
      continue
    fi

    # item è file oppure symlink (anche a dir): crea symlink nel dst
    if [ -e "$dst" ] || [ -L "$dst" ]; then
      continue
    fi

    mkdir -p "$(dirname "$dst")"

    # crea link relativo (più portabile)
    # calcola un percorso relativo dal dst_dir al src (PROJDIR/AIUQ-engine/...)
    # qui usiamo un link relativo "pulito" basato sul fatto che dst_dir è sotto PROJDIR
    # e src_dir è sotto PROJDIR/AIUQ-engine
    ln -s "$(realpath --relative-to="$(dirname "$dst")" "$item")" "$dst"
  done
}

# --- link solo le parti che ti servono ---
link_tree "$SUBMODULE_DIR/conf/AIUQ-st"     "$PROJDIR/conf/AIUQ-st"
link_tree "$SUBMODULE_DIR/conf/cards"      "$PROJDIR/conf/cards"
link_tree "$SUBMODULE_DIR/templates"       "$PROJDIR/templates"
link_tree "$SUBMODULE_DIR/runscripts"      "$PROJDIR/runscripts"
link_tree "$SUBMODULE_DIR/lib"             "$PROJDIR/lib"

echo "OK: recursive symlink trees created under $PROJDIR"