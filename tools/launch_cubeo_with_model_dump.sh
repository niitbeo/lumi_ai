#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/nguyenletruong/cubeo-ai"
SRC="/Applications/Kumoo.app/Contents"
DST="/private/tmp/cubeo_main_hook/Contents"
DUMP_DIR="${CUBEO_MODEL_DUMP_DIR:-/private/tmp/cubeo_model_dump}"

mkdir -p "$DST/MacOS" "$DUMP_DIR"
cp "$SRC/MacOS/YunXiu-PC" "$DST/MacOS/YunXiu-PC"
ln -sfn "$SRC/Frameworks" "$DST/Frameworks"
ln -sfn "$SRC/PlugIns" "$DST/PlugIns"
ln -sfn "$SRC/Resources" "$DST/Resources"
ln -sfn "$SRC/MacOS/Yunxiu-Draft.app" "$DST/MacOS/Yunxiu-Draft.app"
ln -sfn "$SRC/MacOS/export_helper" "$DST/MacOS/export_helper"

codesign --force --sign - "$DST/MacOS/YunXiu-PC" >/dev/null 2>&1 || true

export CUBEO_MODEL_DUMP_DIR="$DUMP_DIR"
export DYLD_INSERT_LIBRARIES="$ROOT/tools/libtiamat_model_dump.dylib"

exec "$DST/MacOS/YunXiu-PC"
