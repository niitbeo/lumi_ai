#!/usr/bin/env bash
set -e

echo "Killing old processes..."
pkill -9 YunXiu-PC || true
pkill -9 Yunxiu-Draft || true

TRACE_APP="/private/tmp/KumooTrace.app"
rm -rf "$TRACE_APP"
cp -a "/Applications/Kumoo.app" "$TRACE_APP"

echo "Stripping signatures..."
codesign --remove-signature "$TRACE_APP/Contents/MacOS/YunXiu-PC" || true
codesign --remove-signature "$TRACE_APP/Contents/MacOS/Yunxiu-Draft.app/Contents/MacOS/Yunxiu-Draft" || true

echo "Compiling and installing YunXiu-PC C++ Wrapper..."
mv "$TRACE_APP/Contents/MacOS/YunXiu-PC" "$TRACE_APP/Contents/MacOS/YunXiu-PC.orig"
cat << 'C_WRAPPER' > /tmp/launcher.c
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <signal.h>

int main(int argc, char** argv) {
    setenv("CUBEO_MODEL_DUMP_DIR", "/private/tmp/cubeo_model_dump", 1);

    
    raise(SIGSTOP);
    argv[0] = "/private/tmp/KumooTrace.app/Contents/MacOS/YunXiu-PC.orig";
    execv(argv[0], argv);
    
    FILE* f = fopen("/tmp/wrapper.log", "w");
    if(f) { fprintf(f, "execv failed\n"); fclose(f); }
    perror("execv failed");
    return 1;
}
C_WRAPPER
clang -o "$TRACE_APP/Contents/MacOS/YunXiu-PC" /tmp/launcher.c -arch arm64

echo "Installing Yunxiu-Draft wrapper to block dylib injection..."
DRAFT_EXEC="$TRACE_APP/Contents/MacOS/Yunxiu-Draft.app/Contents/MacOS/Yunxiu-Draft"
mv "$DRAFT_EXEC" "$DRAFT_EXEC.orig"
cat << 'WRAPPER2' > "$DRAFT_EXEC"
#!/bin/bash
unset DYLD_INSERT_LIBRARIES
exec "$0.orig" "$@"
WRAPPER2
chmod +x "$DRAFT_EXEC"

echo "Signing the entire bundle..."
codesign --force --deep --sign - "$TRACE_APP" || true

echo "Launching KumooTrace..."
open "$TRACE_APP"
