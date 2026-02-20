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

# Copia ricorsivamente il contenuto di $src_dir dentro $dst_dir
# - crea directory
# - copia file veri (preserva permessi e timestamp)
# - se trova symlink nel sorgente, copia il contenuto del target (dereferenzia)
copy_tree () {
  local src_dir="$1"
  local dst_dir="$2"

  mkdir -p "$dst_dir"

  find "$src_dir" -mindepth 1 -not -path "*/.git/*" -print0 | while IFS= read -r -d '' item; do
    rel="${item#"$src_dir"/}"
    dst="$dst_dir/$rel"

    # Directory reale: crea
    if [ -d "$item" ] && [ ! -L "$item" ]; then
      mkdir -p "$dst"
      continue
    fi

    # Se già esiste, non sovrascrivere
    if [ -e "$dst" ] || [ -L "$dst" ]; then
      continue
    fi

    mkdir -p "$(dirname "$dst")"

    # Copia dereferenziando eventuali symlink nel sorgente
    # -L: segue symlink
    # -p: preserva permessi/mtime
    cp -Lp "$item" "$dst"
  done
}

# --- copia solo le parti che ti servono ---
copy_tree "$SUBMODULE_DIR/conf/AIUQ-st"     "$PROJDIR/conf/AIUQ-st"
copy_tree "$SUBMODULE_DIR/conf/cards"      "$PROJDIR/conf/cards"
copy_tree "$SUBMODULE_DIR/templates"       "$PROJDIR/templates"
copy_tree "$SUBMODULE_DIR/runscripts"      "$PROJDIR/runscripts"
copy_tree "$SUBMODULE_DIR/lib"             "$PROJDIR/lib"

echo "OK: recursive copy completed under $PROJDIR"