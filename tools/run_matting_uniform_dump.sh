#!/bin/bash
# Launch the debuggable Kumoo with the matting-uniform interposer injected.
# Prereq: ~/CubeoDebug.app already created by dump/1_resign.sh.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
DYLIB="$HERE/libmatting_uniform_dump.dylib"
APPBIN="$HOME/CubeoDebug.app/Contents/MacOS/YunXiu-PC"
export CUBEO_UNIFORM_DUMP_DIR="$HOME/cubeo_uniform_dump"

[ -f "$DYLIB" ] || { echo "!! missing $DYLIB (build it first)"; exit 1; }
[ -x "$APPBIN" ] || { echo "!! missing $APPBIN (run dump/1_resign.sh first)"; exit 1; }

rm -rf "$CUBEO_UNIFORM_DUMP_DIR"; mkdir -p "$CUBEO_UNIFORM_DUMP_DIR"
echo "[*] Dump dir: $CUBEO_UNIFORM_DUMP_DIR"
echo "[*] Launching CubeoDebug with interposer…"
echo "    → Trong app: mở 1 ảnh, bấm 'Tách nền AI' 1 lần, chờ ra kết quả, rồi ĐÓNG app."
echo

DYLD_INSERT_LIBRARIES="$DYLIB" CUBEO_UNIFORM_DUMP_DIR="$CUBEO_UNIFORM_DUMP_DIR" "$APPBIN"

echo
echo "[✓] App đã đóng. Kết quả dump ở: $CUBEO_UNIFORM_DUMP_DIR"
echo "    ls \"$CUBEO_UNIFORM_DUMP_DIR\"  → gửi Claude nội dung uniforms.log + các file lut_*.bin / shader_*.glsl"
