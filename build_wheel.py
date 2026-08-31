"""Wheel build: the binary is placed INSIDE the package, then the wheel is made.

The order matters. The library looks for itself first at NASHIRA3D_LIB, then
next to itself in the package, and only then in build/. A wheel has nothing but
the second of those, so the file has to be there before the build - otherwise
the wheel comes out empty and the refusal turns up at the user rather than
here.
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(ROOT, "python", "nashira3d")

NAMES = {
    "win32": ("build/win64/nashira3d.dll", "nashira3d.dll"),
    "linux": ("build/linux64/libnashira3d.so", "libnashira3d.so"),
}

key = "win32" if sys.platform == "win32" else "linux"
src_rel, dst_name = NAMES[key]
src = os.path.join(ROOT, *src_rel.split("/"))
dst = os.path.join(PKG, dst_name)

if not os.path.isfile(src):
    sys.exit("no built library: %s\nbuild the core before packaging" % src)

shutil.copy2(src, dst)
print("placed into the package: %s, %d bytes" % (dst_name, os.path.getsize(dst)))

cmd = [sys.executable, "-m", "pip", "wheel", ".", "-w", "dist",
       "--no-deps", "--no-build-isolation"]
print(" ".join(cmd))
code = subprocess.call(cmd, cwd=ROOT)

# THE COPY IS ALWAYS REMOVED, including after a failure.
#
# The reason. The binding looks for the library in the package directory first
# and only then in build. A copy left here is a minute older than a freshly
# built one, and everything run from the source tree quietly picks it up. The
# edit then looks as if it did nothing: the shader in build/win64 is new, and
# the picture is the old one. That is exactly what happened: two frames
# compared byte for byte, and the time went into hunting a shader bug that did
# not exist.
#
# The library is needed here only for the length of the packaging: it has
# already gone into the wheel.
try:
    os.remove(dst)
    print("the copy has been removed from the package: %s" % dst_name)
except OSError as e:
    print("FAILED to remove the copy %s: %s" % (dst, e))
    print("remove it by hand, or a run from the source tree will pick it up")

sys.exit(code)
