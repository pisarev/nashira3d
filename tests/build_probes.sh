#!/bin/sh
# Build the Pascal probes and benchmarks. Needs FPC 3.2.2.
#
# THE PAIR TO build_probes.ps1. While it did not exist, the probes were not
# built under Linux at all: the core has both halves - .ps1 and .sh - and the
# probes had one. The very first run under Linux ran into that, and 57 checks
# out of 346 turned out to be unreachable.
#
# The path to the compiler comes from FPC_EXE, or is looked up in PATH.
set -e

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
CORE="$ROOT/core"
TP="$ROOT/thirdparty/pascal-mathparser"
OUT="$ROOT/build/probe"

if [ ! -d "$TP/src" ]; then
    echo "the parser is missing: $TP" >&2
    echo "clone it at the tag:" >&2
    echo "  git clone --branch v1.3.4 --depth 1 https://github.com/pisarev/pascal-mathparser.git $TP" >&2
    exit 1
fi

FPC=${FPC_EXE:-fpc}
mkdir -p "$OUT"
cd "$HERE"

# The probes the battery runs, and the benchmarks that are run by hand.
for T in mesh_probe cam_probe bench_mesh bench_adaptive; do
    # The artefact is deleted BEFORE the build: otherwise a failed build leaves
    # the previous file, it runs, and it gives numbers from old code.
    rm -f "$OUT/$T"

    "$FPC" -MDelphi -O2 -vw- -Sh -dNOFORMS -dNOGRAPHICS \
        -FU"$OUT" -FE"$OUT" \
        -Fu"$CORE" -Fu"$TP/src/compat" -Fu"$TP/src" -Fu"$TP/jit" -Fi"$TP/src" \
        "$T.dpr"

    if [ ! -x "$OUT/$T" ]; then
        echo "fpc said nothing, but there is no file: $OUT/$T" >&2
        exit 1
    fi
    echo "built: $OUT/$T $(stat -c %s "$OUT/$T") bytes"
done
