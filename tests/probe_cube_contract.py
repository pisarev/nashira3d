"""The cube rotation contract, as it was settled after review.

The whole of it is here, as numbers: this file is the contract. It is checked
by measurement rather than by reading the code.

Why not by eye. The controls were caught inverted three times, and each time
the numbers in the camera state were correct. So what has to be checked is not
those numbers but what was promised to a person: the pivot stays where it is,
the radius does not drift, the sign of the drag is the same on both sides, a
diagonal mouse move does not skew, and the point that was grabbed follows the
hand.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ok, bad = 0, []


def check(name, got, want):
    global ok
    if got == want:
        ok += 1
        print("  ok   %-52s %s" % (name, got))
    else:
        bad.append(name)
        print("  FAIL %-52s got %r, want %r" % (name, got, want))


try:
    r = subprocess.run(["node", os.path.join(HERE, "cube_contract.js")],
                       capture_output=True, text=True, encoding="utf-8", timeout=180)
except FileNotFoundError:
    print("     Node was not found - the contract was NOT CHECKED")
    sys.exit(0)

txt = (r.stdout or "").strip()
if r.returncode != 0 or not txt.startswith("{"):
    print("     " + (r.stderr or "").strip()[:400])
    check("the contract measurement ran", False, True)
    print("")
    print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
    sys.exit(1)

d = json.loads(txt)
for k in ("pivotDriftPx", "radiusDrift", "wheelFocusDriftPx", "wheelRoundTrip"):
    print("     %-22s %s" % (k, d[k]))
print("     isotropy %s, degrees per short side %s"
      % (d["isotropy"], d["degPerShortSide"]))

# The pivot keeps ITS place on the screen. The requirement was less than 0.1 of
# a pixel across the whole pipeline; here it is the arithmetic of the page
# alone, and there it is seven orders better.
check("the pivot does not slide across the screen", d["pivotDriftPx"] < 0.01, True)
check("the radius to the pivot does not drift", d["radiusDrift"] < 1e-12, True)

# The cube must have no hidden side: a finite object has no reason to change
# the meaning of a drag because the camera is above or below the floor of the
# box.
check("the sideways drag has one sign on both sides of the floor",
      d["sideSigns"], "-1,-1,-1,-1")
# BOTH axes, not one. A fault injected into the elevation - "side put back" -
# went straight past a check that looked only at the azimuth.
check("and so does the up-down drag", d["sideSignsY"], "1,1,1,1")

# Isotropy. A mouse vector a hundred pixels long gives the same amount of
# control wherever it points. Otherwise a diagonal movement skews - which is
# exactly the VTK anisotropy this deliberately does without.
iso = d["isotropy"]
check("a hundred pixels diagonally equal a hundred horizontally",
      abs(iso["dia"] - iso["hor"]) < 1e-9 and abs(iso["ver"] - iso["hor"]) < 1e-9, True)
check("180 degrees across the short side of the frame",
      abs(d["degPerShortSide"] - 180) < 1e-6, True)

# The wheel slides along the camera-focus line: the screen place of the focus
# stands still, and eight clicks there and back bring the camera home.
check("the wheel does not shift the focus on the screen", d["wheelFocusDriftPx"] < 0.01, True)
check("eight clicks there and back bring the camera home", d["wheelRoundTrip"] < 1e-9, True)

# A clamp with engineering clearance: half a degree short of the singularity,
# not a machine zero.
check("the elevation is clamped at 89.5 above", abs(d["elMaxDeg"] - 89.5) < 1e-6, True)
check("and at -89.5 below", abs(d["elMinDeg"] + 89.5) < 1e-6, True)

# Orbit and move are DIFFERENT operations. That is exactly what was reported:
# the left button did the same thing as the right one.
check("orbit turns and holds the pivot",
      d["orbitTurned"] and d["orbitPivotFixed"], True)
check("move keeps the orientation but shifts the pivot",
      d["moveKeptOrientation"] and d["moveMovedPivot"], True)
# And the move follows THE HAND pixel for pixel, not six times faster as before.
check("the grabbed point follows the cursor pixel for pixel",
      d["movePivotFollow"] == [200, 100], True)

print("")
print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
sys.exit(1 if bad else 0)
