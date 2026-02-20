#!/bin/bash

TARGET_PROJDIR=%PROJECT.PROJECT_DESTINATION%
SUBMODULE_PATH=%PROJECT.PROJECT_DESTINATION%/AIUQ-engine

# -> conf/AIUQ-st
mkdir -p conf/AIUQ-st
for f in $SUBMODULE_PATH/conf/AIUQ-st/*; do
  base=$(basename "$f")
  [ -e "conf/AIUQ-st/$base" ] || ln -s "$SUBMODULE_PATH/conf/AIUQ-st/$base" "$TARGET_PROJDIR/conf/AIUQ-st/$base"
done

# -> conf/cards
mkdir -p conf/cards
for f in $SUBMODULE_PATH/conf/cards/*; do
  base=$(basename "$f")
  [ -e "conf/cards/$base" ] || ln -s "$SUBMODULE_PATH/conf/cards/$base" "$TARGET_PROJDIR/conf/cards/$base"
done

# -> templates
mkdir -p templates
for f in $SUBMODULE_PATH/templates/*; do
  base=$(basename "$f")
  [ -e "templates/$base" ] || ln -s "$SUBMODULE_PATH/templates/$base" "$TARGET_PROJDIR/templates/$base"
done

# -> runscripts
mkdir -p runscripts
for f in $SUBMODULE_PATH/runscripts/*; do
  base=$(basename "$f")
  [ -e "runscripts/$base" ] || ln -s "$SUBMODULE_PATH/runscripts/$base" "$TARGET_PROJDIR/runscripts/$base"
done

# -> lib
mkdir -p lib
for f in $SUBMODULE_PATH/lib/*; do
  base=$(basename "$f")
  [ -e "lib/$base" ] || ln -s "$SUBMODULE_PATH/lib/$base" "$TARGET_PROJDIR/lib/$base"
done