"""Where the domain comes from - the one difference between the cube and the
plane.

This question used to be fused with another one: how the camera is given. A
standing camera switched on the view-based domain by itself, and the two could
not be separated. The fusion had two consequences, both bad:

  - a point camera could not be walked INSIDE a declared domain;
  - the difference between the cube and the plane was smeared over four
    branches of the core, and there was no way to explain it in one place.

What is checked here is that the difference is ONE, and that everything else
follows from it: even sampling against screen sampling, edges against fading.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "python"))
import hashlib
import nashira3d

ok, bad = 0, []


def check(name, got, want):
    global ok
    if got == want:
        ok += 1
        print("  ok   %-52s %s" % (name, got))
    else:
        bad.append(name)
        print("  FAIL %-52s got %r, want %r" % (name, got, want))


W, H = 220, 165
FORM = "sin(2*x)*cos(2*y)"


def fresh():
    s = nashira3d.Session(FORM, quality=50)
    s.domain = (-2, 2, -2, 2)
    s.box = (1, 1, 0.3)
    s.fit = False
    s.grid = True
    s.axes = False
    return s


def h(s):
    return hashlib.sha256(bytes(memoryview(s.render(W, H)).cast("B"))).hexdigest()


# --- THE DEFAULT IS THE CUBE -------------------------------------------------
s = fresh()
check("the default is a declared domain", s.region_mode, "declared")

s.camera = (0.9, 0.6, 3.4, 0.9)
cube_orbit = h(s)

# --- ONE SESSION HOLDS BOTH MODES --------------------------------------------
s.stand(0.0, 0.0, 2.5, 0.9, 0.6, 0.9)
cube_stand = h(s)
check("a point camera inside a declared domain draws",
      cube_stand != cube_orbit, True)

s.region_mode = "view"
plane = h(s)
check("the same camera with a view-based domain gives something else",
      plane != cube_stand, True)

s.region_mode = "declared"
check("and going back reproduces the earlier frame", h(s) == cube_stand, True)

# --- AN INCOMPATIBLE COMBINATION IS REFUSED ----------------------------------
# A view-based domain is built through the view frustum, and the frustum is
# built by a camera given as a point IN THE COORDINATES OF THE PROBLEM. An
# orbit camera has no such point: it stands relative to the box, the box comes
# from the domain, and the domain from the camera. A circle.
s.camera = (0.9, 0.6, 3.4, 0.9)
s.region_mode = "view"
try:
    s.render(W, H)
    check("an orbit with a view-based domain is refused", False, True)
except nashira3d.Nashira3DError as e:
    check("an orbit with a view-based domain is refused",
          "standing camera" in str(e), True)
# A refusal does not spoil the session: put back something compatible and it
# draws.
s.region_mode = "declared"
check("the session is alive after the refusal", h(s) == cube_orbit, True)
s.close()

# --- EVERYTHING ELSE FOLLOWS FROM THE ONE DIFFERENCE -------------------------
# 1. A DECLARED DOMAIN HAS VISIBLE EDGES. The surface breaks off where a person
#    said it should, and there is background around it. With a view-based
#    domain the sheet fills the frame and fades away in the distance.
def background_share(sess):
    mv = memoryview(sess.render(W, H)).cast("B")
    n = t = 0
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            i = (y * W + x) * 4
            t += 1
            if mv[i] + mv[i + 1] + mv[i + 2] < 95:
                n += 1
    return 100.0 * n / t


# The camera looks AT the cube, not away from it. At first az=pi/2 stood here,
# at which the view runs towards decreasing y - a camera at y=-3 was looking
# away from the origin, the frame came out 100% empty, and the "edges are
# visible" check accepted it. The witness guarded the wrong thing: an empty
# frame and a sheet with edges look the same to it.
AZ_TO_ORIGIN = -1.5708
a = fresh()
a.stand(0.0, -3.0, 2.0, AZ_TO_ORIGIN, 0.55, 0.9)
cube_bg = background_share(a)
a.region_mode = "view"
plane_bg = background_share(a)
print("     background around the sheet: cube %.1f%%, plane %.1f%%"
      % (cube_bg, plane_bg))
check("a declared domain has visible edges", 15 < cube_bg < 85, True)
check("with a view-based domain the sheet fills the frame", plane_bg < 8, True)

# 2. SAMPLING. With a declared domain the lines stand evenly, with a computed
#    one by screen density. It shows in HOW the domain changes: with the cube
#    it does not change at all, with the plane it follows the camera.
# A witness that the camera does NOT move a declared domain. Two useless ones
# were thrown out, and both are worth naming:
#
#   a.domain - our own copy on the Python side, which the core does not touch
#   under any behaviour; an injected fault - "compute the domain from the
#   camera view" - went straight through it;
#
#   the number of folds across the frame at different heights. It measures two
#   things at once: how much of the function is visible, and HOW LARGE it is
#   drawn. From far away the cube is smaller and the lines merge, so the count
#   drops even on sound code - 52 against 5 measured.
#
# What works is a lever that affects ONLY the computed domain and nothing else:
# the extent limit. With a declared domain it has to mean nothing.
a.region_mode = "declared"
a.stand(0.0, -3.0, 2.0, AZ_TO_ORIGIN, 0.55, 0.9)
a.max_extent = 0
base = hashlib.sha256(bytes(memoryview(a.render(W, H)).cast("B"))).hexdigest()
a.max_extent = 0.3
tight = hashlib.sha256(bytes(memoryview(a.render(W, H)).cast("B"))).hexdigest()
check("the extent limit does not touch a declared domain", base == tight, True)
a.max_extent = 0

# The other side of it: with a computed domain the same lever has to change the
# frame - otherwise the check above would also pass on a build where the domain
# is not computed at all.
a.region_mode = "view"
v0 = hashlib.sha256(bytes(memoryview(a.render(W, H)).cast("B"))).hexdigest()
a.max_extent = 0.3
v1 = hashlib.sha256(bytes(memoryview(a.render(W, H)).cast("B"))).hexdigest()
check("but it does change a computed one", v0 != v1, True)
a.max_extent = 0
a.region_mode = "declared"
a.region_mode = "view"
r1 = a.region(W, H)
a.stand(1.0, -4.0, 6.0, AZ_TO_ORIGIN, 0.35, 0.9)
r2 = a.region(W, H)
check("a computed domain follows the camera",
      abs((r2[1] - r2[0]) - (r1[1] - r1[0])) > 0.5, True)
a.close()

print("")
print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
sys.exit(1 if bad else 0)
