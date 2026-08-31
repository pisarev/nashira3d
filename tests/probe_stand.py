"""The camera as a standing point - through a real frame.

The arithmetic of the camera is checked by cam_probe in Pascal, without
graphics. What is checked here is what the EYE sees and what the arithmetic
will not prove:

  5.1    the edge of the sheet is not visible AT ANY height. The check is not
         by eye: background pixels are turned back into rays, the ray is
         intersected with the base plane, and the point of intersection has to
         lie INSIDE the computed domain. Background outside the domain is
         exactly the sheet breaking off;
  4.4.5  the surface is visible from BOTH sides. Back-face culling is not
         switched on in the code, but "not switched on today" and "will not be
         switched on tomorrow" are different things, and the difference is
         caught only by measurement;
  4.3    the colour by height is THE SAME from below: one height, one colour
         from either side.

The background is told from the relief by saturation, not by darkness: the
trough of the ramp is (33, 46, 133) - dark, but blue, and by darkness alone it
would count as background. That has already happened once: the background share
came out at 10.8 per cent where there was no background at all.
"""

import math
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
        print("  ok   %-50s %s" % (name, got))
    else:
        bad.append(name)
        print("  FAIL %-50s got %r, want %r" % (name, got, want))


W, H = 300, 200
AZ, FOV = 0.9, 0.9


def is_bg(p):
    return p[0] < 45 and p[1] < 50 and p[2] < 70


def frame(s):
    return bytes(memoryview(s.render(W, H)).cast("B"))


def pix(buf, x, y):
    i = (y * W + x) * 4
    return (buf[i], buf[i + 1], buf[i + 2])


def basis(el, az=AZ):
    f = (-math.cos(el) * math.cos(az), -math.cos(el) * math.sin(az), -math.sin(el))
    r = (-math.sin(az), math.cos(az), 0.0)
    u = (r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2],
         r[0] * f[1] - r[1] * f[0])
    return f, r, u


def stand_at(s, h, el):
    """The camera is placed so that the central ray strikes the origin:
    otherwise it looks AWAY from the relief and an empty field is measured."""
    d = h / math.tan(el)
    s.stand(d * math.cos(AZ), d * math.sin(AZ), h, AZ, el, FOV)
    return d * math.cos(AZ), d * math.sin(AZ)


def bg_outside(s, h, el):
    """How many background pixels fall OUTSIDE the computed domain."""
    cx, cy = stand_at(s, h, el)
    x0, x1, y0, y1 = s.region(W, H)
    buf = frame(s)
    f, r, u = basis(el)
    tv = math.tan(FOV / 2)
    th = tv * (W / H)
    total = outside = 0
    for j in range(0, H, 2):
        for i in range(0, W, 2):
            if not is_bg(pix(buf, i, j)):
                continue
            total += 1
            uu = 2 * (i + 0.5) / W - 1
            vv = 1 - 2 * (j + 0.5) / H
            d = [f[k] + u[k] * tv * vv + r[k] * th * uu for k in range(3)]
            if d[2] >= -1e-9:
                outside += 1        # the ray goes up: there is no ground there
                continue
            t = -h / d[2]
            px_, py_ = cx + d[0] * t, cy + d[1] * t
            if px_ < x0 or px_ > x1 or py_ < y0 or py_ > y1:
                outside += 1
    return total, outside


# THE PREMISE IS NAMED OUT LOUD. The subject of this probe is the camera as a
# standing point ON AN INFINITE PLANE: a sheet with no edges, the domain worked
# out by the library from the view. One used to follow from the other by
# itself; now they are two different questions, and the probe has to say which
# of the answers it needs rather than lean on a default.
s = nashira3d.Session("sin(3*x)*cos(3*y)*exp(-(x*x+y*y))", quality=60)
s.domain = (-2, 2, -2, 2)
s.grid = False
s.axes = False
s.render(120, 90)          # the first build freezes the scale and the exaggeration
# The switch comes AFTER the warm-up: the frame above was taken with an orbit
# camera, while a view-based domain needs a point camera, and the core refuses
# that combination.
s.region_mode = "view"

# --- 5.1: THE EDGE OF THE SHEET IS NOT VISIBLE -------------------------------
worst = 0
seen = 0
for h in (4.0, 3.0, 1.2, 0.6, 0.35, 0.1):
    total, outside = bg_outside(s, h, 0.9)
    seen += total
    worst = max(worst, outside)
check("at six heights there is no background outside the domain", worst, 0)
check("and background WAS met: the check did not run empty", seen > 200, True)

# An injection by the same means: a domain narrowed by hand has to produce
# background outside it. Without this the check above is green even when there
# is no background at all.
stand_at(s, 0.6, 0.9)
s.max_extent = 0.35
total, outside = bg_outside(s, 0.6, 0.9)
check("a narrowed extent cuts the sheet off - and it shows", outside > 0, True)
s.max_extent = 0

# --- 4.4.5: VISIBLE FROM BOTH SIDES ------------------------------------------
def cover(h, el):
    stand_at(s, h, el)
    buf = frame(s)
    n = sum(1 for y in range(H) for x in range(W) if not is_bg(pix(buf, x, y)))
    return 100.0 * n / (W * H)


top = cover(2.0, 0.80)
bottom = cover(-2.0, -0.80)
check("from above the surface fills nearly the whole frame", top > 90, True)
check("from below too: the back faces are not culled", bottom > 90, True)
check("the difference between above and below is small", abs(top - bottom) < 8, True)

# --- 4.3: THE COLOUR BY HEIGHT IS THE SAME FROM BELOW ------------------------
# The summit of the function is the same from either side, and the yellow end
# of the ramp has to be found in both frames. The colour does NOT turn over
# with the point of view.
def warmest(h, el):
    """The warmest pixel: the one with the largest red minus blue."""
    stand_at(s, h, el)
    buf = frame(s)
    best = (0, 0, 0)
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            p = pix(buf, x, y)
            if p[0] - p[2] > best[0] - best[2]:
                best = p
    return best


# Two-sided lighting is checked by the WARMEST pixel, that is by colour. The
# colour is asked for explicitly: under contour lines there is no warm end of
# the ramp.
s.shading = "colour"
hot_top = warmest(2.0, 0.80)
hot_bot = warmest(-2.0, -0.80)
check("from above the yellow end of the ramp is visible",
      hot_top[0] > 200 and hot_top[2] < 130, True)
check("from below the same end is visible",
      hot_bot[0] > 200 and hot_bot[2] < 130, True)

# The brightness is compared BY NUMBER, not by eye. It used to be forty per
# cent of the upper one from below - the light shone only from above, and a
# normal turned towards the viewer always faced away from the source. Now the
# source is mirrored along with the normal.
share = 100.0 * sum(hot_bot) / max(1, sum(hot_top))
check("from below it is no darker than above: %d%% of the brightness"
      % round(share), share > 80, True)

# --- THE EXAGGERATION DOES NOT CLOSE A LOOP ON THE DOMAIN --------------------
# The reason: the vertical exaggeration was computed from the CURRENT domain,
# and the domain depends on the thickness of the slab, that is on the
# exaggeration. That made a loop with gain: with the camera STANDING STILL the
# half-width of the domain went 8.6, 15.9, 17.7, 90.9, 408, 1788, 7782 - more
# than fourfold per step. Pressing Fit Z a few times in a row was enough.
#
# The reference half-size is now taken ONCE, when the formula changes. The
# consequence is what is checked: with a standing camera, repeated
# recomputations do not move the domain.

sl = nashira3d.Session("x*x-y*y", quality=50)
sl.domain = (-1, 1, -1, 1)
sl.box = (1, 1, 0.9)
sl.fit = False
sl.grid = True
sl.axes = False
sl.render(120, 90)
sl.stand(1.1, 1.4, 1.6, AZ, 0.85, FOV)
sl.region_mode = "view"
first = sl.region(W, H)
sl.auto_z = True
widths = []
for _ in range(8):
    sl.fit_z()
    sl.render(W, H)
    r = sl.region(W, H)
    widths.append(max(r[1] - r[0], r[3] - r[2]))
check("eight recomputations in a row did not inflate the domain",
      max(widths) <= min(widths) * 1.05, True)
check("and it stayed at its own order of magnitude",
      abs(max(widths) - max(first[1] - first[0], first[3] - first[2]))
      < max(first[1] - first[0], first[3] - first[2]) * 0.5, True)
sl.close()

s.close()

# --- THE FIRST FRAME AFTER A SAMPLE IS ALREADY SETTLED -----------------------
# The domain is computed from the slab, and the slab appears only when the
# scale is frozen. So on a change of formula the first pass inevitably runs on
# the declared domain. While the second pass was put off until the next frame,
# this is what came out: click a sample and the sheet hangs as a piece in the
# middle of emptiness, then unfolds to the whole view at the first movement of
# the mouse. Nobody had asked for that frame.
#
# What is checked is not the domain (that converges anyway) but THE PICTURE:
# the first frame has to match the second byte for byte. The picture is what
# the user sees.
#
# The injection that caught this: remove "if FrozeNow and S^.CamStand then
# Again := True" in DoRender. Measured on such a build - 20.3% of the frame
# taken against 51.4% on the second, and the same for all four samples.

import hashlib as _hl


def _hash(buf):
    return _hl.sha256(bytes(memoryview(buf).cast("B"))).hexdigest()


sf = nashira3d.Session("x*x+y*y", quality=60)
sf.region_mode = "view"
sf.grid = True
sf.axes = False
firstframe = []
for _f, _a, _b in (("x*x+y*y", -1, 1), ("sin(3*x)*cos(3*y)", -3.1416, 3.1416),
                   ("x*x-y*y", -1, 1), ("exp(-4*(x*x+y*y))", -1.2, 1.2)):
    sf.formula = _f                     # the order as on the page: formula,
    sf.domain = (_a, _b, _a, _b)        # the sample's domain, then the camera
    _want = (_b - _a) / 2
    sf.stand(0.0, -1.6 * _want, 1.6 * _want, 1.5708, 0.85)
    firstframe.append(_hash(sf.render(400, 300)) == _hash(sf.render(400, 300)))
check("the first frame after a sample matched the second", all(firstframe), True)

# The cost of the second pass is bounded not by a promise but by the code:
# Pass >= 2 closes the loop. The parser counters are not exposed, and there is
# nothing here to check that with - said plainly, so that nobody takes it for
# checked.
sf.close()

# --- GOING BACK TO ORBIT -----------------------------------------------------
# A standing camera used to cancel orbit for the rest of the session's life -
# that was written in the header as well. The word was kept, and the price came
# out in practice: the viewer has ONE session, and the height mode is the
# default, so opening the page was enough to leave the other two modes dead.
# The buttons switched, the hint changed, the picture stayed a standing camera.
#
# Measured at the time: camera dist=3.4 and dist=8 gave DIFFERENT frames; after
# one frame in height mode both became byte-equal to the last height frame.

import hashlib as _h2


def _fr(sess, w=200, h=150):
    return _h2.sha256(bytes(memoryview(sess.render(w, h)).cast("B"))).hexdigest()


sw = nashira3d.Session("sin(1.2*x)*cos(1.2*y)", quality=50)
sw.domain = (-2, 2, -2, 2)
sw.box = (1, 1, 0.3)
sw.grid = True
sw.axes = False
sw.camera = (0.9, 0.6, 3.4, 0.9)
orb34 = _fr(sw)
sw.camera = (0.9, 0.6, 8.0, 0.9)
orb80 = _fr(sw)
check("with orbit, the distance changes the frame", orb34 != orb80, True)

sw.stand(0.0, 0.0, 2.5, 0.9, 0.6, 0.9)
stood = _fr(sw)
check("moving to a standing camera changed the frame", stood != orb80, True)

# The domain has to be DECLARED again, and that is not a slip in the probe. The
# core has one domain field for two meanings: the declared domain and the
# computed region. A standing camera writes its own result there, and a return
# to orbit finds something other than what the caller declared. The viewer does
# not suffer from this - it sends the domain every frame - but in the contract
# it is a muddle, and it is named here rather than passed over.
sw.domain = (-2, 2, -2, 2)
sw.camera = (0.9, 0.6, 3.4, 0.9)
check("going back to orbit brought back THE SAME frame", _fr(sw) == orb34, True)
sw.camera = (0.9, 0.6, 8.0, 0.9)
check("and the distance works again", _fr(sw) == orb80, True)
sw.stand(0.0, 0.0, 2.5, 0.9, 0.6, 0.9)
check("and back to standing - the same one again", _fr(sw) == stood, True)
sw.close()

print("")
print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
sys.exit(1 if bad else 0)
