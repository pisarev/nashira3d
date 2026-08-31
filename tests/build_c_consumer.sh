#!/bin/sh
# Building the outside consumer of the seam under Linux.
#
# The compiler here is foreign ON PURPOSE: the core is built by fpc and the
# consumer by cc. That is the whole point of this probe. Had one compiler
# built both sides, a shared mistake about layout would have gone unnoticed.
set -e
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/.." && pwd)
out="$root/build/probe"
mkdir -p "$out"
cc -std=c99 -Wall -Wextra -O1 -I"$root/include"    -o "$out/c_consumer" "$here/c_consumer.c" -ldl
echo "built: $out/c_consumer"
echo "run:   $out/c_consumer $root/build/linux64/libnashira3d.so"
