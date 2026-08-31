"""A STRANGER'S probe: run from a clean environment where only the wheel is
installed.

Why it is separate from run_all. The other probes go through the sources and
through the NASHIRA3D_LIB variable - that is, along the developer's road. This
one goes along the user's road, and it is the one that found a real defect:
without numpy, save_png fell over, although the README promised that numpy was
optional.

How to run it:

    python build_wheel.py
    python -m venv <empty directory>/.venv
    <empty directory>/.venv/Scripts/python -m pip install dist/*.whl
    cd <empty directory>
    .venv/Scripts/python <path to the sources>/tests/stranger_smoke.py

The working directory has to be OUTSIDE the sources, or Python will find the
package next to itself and check something other than what ships.
"""

import os
import sys

FAIL = []


def check(name, cond, got=""):
    if cond:
        print("  ok   %-44s %s" % (name, got))
    else:
        FAIL.append(name)
        print("  FAIL %-44s %s" % (name, got))


here = os.path.dirname(os.path.abspath(__file__))
check("running OUTSIDE the sources", os.path.abspath(os.getcwd()) != os.path.dirname(here),
      os.getcwd())
check("NASHIRA3D_LIB is not set", "NASHIRA3D_LIB" not in os.environ)

import nashira3d

check("the core version arrived", len(nashira3d.version()) > 0, nashira3d.version())

try:
    import numpy
    has_np = True
except ImportError:
    has_np = False
print("  numpy: %s" % ("yes " + numpy.__version__ if has_np else "NO"))

with nashira3d.Session("sin(3*x) * cos(3*y)", domain=(-2, 2, -2, 2), quality=60) as s:
    p = s.save_png("stranger.png", 400, 300)
    size = os.path.getsize(p)
    check("the PNG is written", size > 10000, "%d bytes" % size)
    check("the PNG header is right", open(p, "rb").read(4) == b"\x89PNG")
    img = s.render(64, 48)
    if has_np:
        check("the frame is an array of the right shape",
              tuple(img.shape) == (48, 64, 4), str(img.shape))
    else:
        check("the frame is a flat view of the right length",
              len(img) == 64 * 48 * 4, str(len(img)))

try:
    nashira3d.Session("x +* ")
    check("nonsense is rejected", False, "it went through in silence")
except nashira3d.Nashira3DError as e:
    check("nonsense is rejected", True, str(e)[:40])

# --- THE WHOLE TABLE, NOT ONLY ITS OLDER PART --------------------------------
# The ABI table grows, and it grows in three places at once: the header, the
# Pascal record and the cdef. A disagreement between the cdef and THE VERY
# library that went out in the wheel will surface not as a build error but as a
# call to the neighbouring function - in silence. So here every member of the
# table is CALLED at least once on the real wheel.

with nashira3d.Session("x*x + y*y", domain=(-2, 2, -2, 2), quality=40) as s:
    s.render(64, 48)

    s.fit_z()
    check("fit_z is callable", True, "")

    s.obstacles = [(0, 0, 20, 20)]
    check("the taken places are set", len(s.obstacles) == 4, str(s.obstacles))

    s.max_extent = 12.0
    check("the extent is set", s.max_extent == 12.0, str(s.max_extent))
    s.max_extent = 0

    s.z_exaggeration = 2.0
    check("the exaggeration is set", s.z_exaggeration == 2.0, str(s.z_exaggeration))
    s.z_exaggeration = 1.0

    s.auto_z = True
    check("Auto Z switches on", s.auto_z is True, str(s.auto_z))
    s.auto_z_fired()
    s.auto_z = False

    s.stand(0.5, 0.5, 2.0, 0.9, 0.85)
    s.render(64, 48)
    reg = s.region(64, 48)
    ok = (len(reg) == 4 and reg[1] > reg[0] and reg[3] > reg[2])
    check("the camera as a standing point, and its region", ok,
          ", ".join("%.2f" % v for v in reg))

    s.grid = True
    s.axes = False
    s.pan = (0.1, -0.1)
    s.light = (2.0, 0.8)
    s.box = (1, 1, 0.4)
    s.fit = False
    s.quality = 30
    s.formula = "sin(x) * cos(y)"
    check("the remaining settings are accepted", s.formula == "sin(x) * cos(y)",
          s.formula)

print("")
print("failures: %d" % len(FAIL))
sys.exit(1 if FAIL else 0)
