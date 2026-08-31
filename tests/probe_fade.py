"""The surface fading with distance.

The sheet is finite: past the extent limit it is not computed at all. Without
the fade its edge shows as a straight cut across the frame - a cut the function
itself does not have.

The subject of the check is a FLAT surface seen at a shallow angle. Flat was
chosen not for simplicity: on a relief the tops of NEARBY humps are visible at
the horizon, they are bright by right, and they say nothing about the fade. On
a plane a change of brightness along the frame can only come from the fade.

Three things are checked:
  1. the transition exists and is WIDE - not a two-row cliff;
  2. it fades into the very background the background is painted with, not into
     blackness;
  3. an orbit camera has no fade at all - there the domain is given by a
     person, and no cut-off by extent exists.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "python"))
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


W, H = 240, 200


def column(buf, x):
    mv = memoryview(buf).cast("B")
    return [(mv[(y * W + x) * 4] + mv[(y * W + x) * 4 + 1]
             + mv[(y * W + x) * 4 + 2]) / 3.0 for y in range(H)]


def pixel(buf, x, y):
    mv = memoryview(buf).cast("B")
    i = (y * W + x) * 4
    return (mv[i], mv[i + 1], mv[i + 2])


# THE PREMISE IS NAMED OUT LOUD. A standing camera used to switch on the
# view-based domain by itself - two different things lived in one field. Now
# they are uncoupled: the camera says WHERE we look from, region_mode says
# WHERE the domain comes from. The subject of this probe is the infinite plane,
# so the library works the domain out.
s = nashira3d.Session("0.02*x", domain=(-4, 4, -4, 4), quality=50)
s.region_mode = "view"
s.grid = False
s.axes = False
s.box = (1, 1, 0.3)
s.fit = False
s.stand(0.0, -4.0, 2.0, 1.5708, 0.22, 0.9)
img = s.render(W, H)
col = column(img, W // 2)

near = col[H - 8]                       # at the bottom edge - right by the camera
sky = col[6]                            # at the top - background for certain
lo, hi = sky + (near - sky) * 0.10, sky + (near - sky) * 0.90
rows = [y for y in range(H) if lo <= col[y] <= hi]
span = (max(rows) - min(rows)) if rows else 0
print("     near %.1f, background %.1f, the transition takes %d rows out of %d"
      % (near, sky, span, H))

check("the surface far away is much darker than near", near - sky > 15, True)
# Eight rows is not a round number: with a law by DISTANCE rather than by its
# reciprocal, four were measured, and the threshold has to fall between those
# two cases.
check("the transition is wide, not a cliff", span >= 8, True)

# Monotonic: the brightness has to grow from top to bottom, with no dips larger
# than the noise.
back = sum(1 for y in range(min(rows) if rows else 0, H - 8)
           if col[y + 1] < col[y] - 3)
check("the brightness grows towards the camera with no dips", back, 0)

# --- NO SEAM -----------------------------------------------------------------
# The subject is exactly WHAT the eye sees: a step across the frame. Comparing
# the faded distance against "the background somewhere off to the side" failed
# twice: the background in the frame is not uniform, and a tilted plane also
# puts the horizon on a row of its own. Both times the wrong things were
# compared, and the probe went red on a sound picture.
#
# A seam, on the other hand, needs to know neither the formula of the
# background nor where the sheet ends: if the transition is smooth, NEIGHBOURING
# rows differ little EVERYWHERE. A cliff gives one row with a large jump - and
# that is what is looked for.
jump = max(abs(col[y + 1] - col[y]) for y in range(H - 1))
where = max(range(H - 1), key=lambda y: abs(col[y + 1] - col[y]))
print("     largest jump between neighbouring rows: %.1f at row %d"
      % (jump, where))
# The threshold is not round: with a cliff and no fade, 30 and more was
# measured; with a sound fade, single digits. Eight lies between.
check("there is no seam across the frame", jump < 8, True)

# --- INTO THE BACKGROUND, NOT INTO BLACKNESS ---------------------------------
# The seam check does NOT cover this, and at first that was written down wrong
# here. An injected fault - "fade into vec3(0.0)" - went straight past: at a
# shallow angle the plane is dark anyway (50 measured against a background of
# 22), and a drop into blackness gives a jump of 7.3 - below the seam
# threshold.
#
# It is caught by level, not by step. The surface is brighter than the
# background, so as it fades it approaches the background FROM ABOVE and cannot
# go BELOW it. Fading into blackness, it has to: between the background and
# zero lies the whole dark part.
sky = min(col[2:20])
low = min(col)
print("     sky %.1f, darkest place in the frame %.1f" % (sky, low))
check("nowhere darker than the background", low >= sky - 4, True)

# --- AN ORBIT CAMERA HAS NO FADE ---------------------------------------------
o = nashira3d.Session("0.02*x", domain=(-4, 4, -4, 4), quality=50)
o.grid = False
o.axes = False
o.box = (1, 1, 0.3)
o.fit = False
o.camera = (1.5708, 0.22, 3.4, 0.9)
oc = column(o.render(W, H), W // 2)
vals = [v for v in oc if v > 25]
check("with an orbit camera the surface is even",
      (max(vals) - min(vals)) < 45 if vals else False, True)
o.close()
s.close()

print("")
print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
sys.exit(1 if bad else 0)
