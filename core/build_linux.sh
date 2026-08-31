#!/bin/sh
# Build the core on Linux. Needs FPC 3.2.2 and the EGL headers from Mesa.
#
#   sudo apt-get install -y fpc libegl-dev
#
# The switches -dNOFORMS and -dNOGRAPHICS, together with the src/compat
# directory, are the parser's own "without LCL" build line. Without them it
# drags in the visual library of the IDE, which has no place in a windowless
# core.
set -e

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
TP="$ROOT/thirdparty/pascal-mathparser"
OUT="$ROOT/build/linux64"

if [ ! -d "$TP/src" ]; then
    echo "the parser is missing: $TP" >&2
    echo "clone it at the tag:" >&2
    echo "  git clone --branch v1.3.4 --depth 1 https://github.com/pisarev/pascal-mathparser.git $TP" >&2
    exit 1
fi

mkdir -p "$OUT"
cd "$HERE"

fpc -MDelphi -O2 -vw- -Sh -dNOFORMS -dNOGRAPHICS \
    -FU"$OUT" -FE"$OUT" \
    -Fu"$TP/src/compat" -Fu"$TP/src" -Fu"$TP/jit" -Fi"$TP/src" \
    nashira3d.lpr

LIB="$OUT/libnashira3d.so"
if [ ! -f "$LIB" ]; then
    echo "the build said nothing, but there is no library: $LIB" >&2
    exit 1
fi
echo "built: $LIB $(stat -c %s "$LIB") bytes"
