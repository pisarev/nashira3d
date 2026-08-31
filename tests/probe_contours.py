"""Contour lines - lines of equal height.

What is checked is not "something dark got drawn" but THREE PROMISES:

  1. the lines stand at the declared step - so their number over a known span
     is known in advance and can be counted;
  2. in colour mode there are NONE at all - otherwise the setting switches
     nothing;
  3. the ink does not flood the surface - neither on level ground nor on a
     steep slope.

The subject is chosen so that the count is exact rather than approximate: the
tilted plane z = y over the domain from -1 to 1. The span is exactly 2, at a
step of 0.2 there are exactly ten lines, and any discrepancy shows at once. On
a hilly formula the lines bend, the number of crossings per row varies, and
there would be nothing to check.

What is counted is NOT dark pixels but DIPS in brightness relative to the
neighbours three pixels away on either side. A threshold on absolute brightness
will not do: the surface is shaded unevenly, and at the far edge the shadow is
deeper than the ink of a line nearby.
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


W, H = 300, 300


def lum(mv, x, y):
    i = (y * W + x) * 4
    return (mv[i] * 2 + mv[i + 1] * 5 + mv[i + 2]) / 8.0


def dips(buf, row):
    """Where the row crossed a line - the positions of the brightness dips,
    left to right."""
    mv = memoryview(buf).cast("B")
    v = [lum(mv, x, row) for x in range(W)]
    out, inside = [], False
    for x in range(3, W - 3):
        dip = v[x] < (v[x - 3] + v[x + 3]) / 2 - 12
        if dip and not inside:
            out.append(x)
        inside = dip
    return out


def crossings(buf, row):
    return len(dips(buf, row))


def spacing(buf, row):
    """The median gap between the lines, in screen pixels.

    The median rather than the mean, and not the exact number of lines: the
    camera has perspective, and on the same row the far gaps are half the width
    of the near ones (measured: from 18 to 40 pixels at a step of 0.2).
    Counting the lines is not enough either - the dip at the EDGE OF THE SHEET
    mixes in with them, and the count comes out one too many. The gap does not
    depend on the edge, so the gap is what is measured."""
    p = dips(buf, row)
    g = sorted(p[i + 1] - p[i] for i in range(len(p) - 1))
    return g[len(g) // 2] if g else 0


def body_mask(buf):
    """The silhouette of the surface, taken in COLOUR mode.

    The silhouette must not be measured by its own brightness, and that cost a
    false "ok". The ink of the lines is almost black (18, 28, 43), and a
    surface flooded with it falls into the background at any brightness
    threshold: the inked share is then computed over zero pixels and comes out
    zero. The probe said "not flooded" on the very picture that was flooded -
    proved by injection, a removed slope cut-off was not caught.

    Colour mode does not look at the contours at all, so the silhouette taken
    from it is truthful whatever breaks in the lines. The mesh and the camera
    are the same, so the silhouette is the same."""
    mv = memoryview(buf).cast("B")
    out = []
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            i = (y * W + x) * 4
            rgb = (mv[i], mv[i + 1], mv[i + 2])
            if max(rgb) - min(rgb) > 30:                # background: even grey-blue
                out.append((x, y))
    return out


def depths(buf, row):
    """The depth of each dip - how much darker the line is than the slope next
    to it."""
    mv = memoryview(buf).cast("B")
    v = [lum(mv, x, row) for x in range(W)]
    out, inside, cur = [], False, 0.0
    for x in range(3, W - 3):
        d = (v[x - 3] + v[x + 3]) / 2 - v[x]
        if d > 12:
            cur = d if not inside else max(cur, d)
            inside = True
        elif inside:
            out.append(cur)
            inside = False
    return out


def ink_share(buf, mask):
    """The inked share within the silhouette."""
    if not mask:
        return 1.0                                     # no silhouette - do not stay silent
    mv = memoryview(buf).cast("B")
    dark = sum(1 for x, y in mask if lum(mv, x, y) < 60)
    return dark / float(len(mask))


def plane(step):
    s = nashira3d.Session("y", domain=(-1, 1, -1, 1), quality=60,
                          camera=(0.0, 1.45, 3.2, 0.7), axes=False)
    s.grid = False
    s.box = (1, 1, 0.9)
    s.fit = False
    s.contour_step = step
    return s


# --- THE NUMBER OF LINES IS SET BY THE STEP ----------------------------------
s = plane(0.2)
s.shading = "contours"
f = s.render(W, H)
rows = [crossings(f, r) for r in (120, 150, 180)]
check("at a step of 0.2 over a span of 2, about ten lines",
      all(9 <= n <= 11 for n in rows), True)

d2 = [spacing(f, r) for r in (120, 150, 180)]
s.contour_step = 0.4
f4 = s.render(W, H)
d4 = [spacing(f4, r) for r in (120, 150, 180)]
ratio = [b / float(a) for a, b in zip(d2, d4)]
print("     gap: %s -> %s, ratio %s"
      % (d2, d4, ["%.2f" % r for r in ratio]))
check("twice the step, twice the gap",
      all(1.6 <= r <= 2.4 for r in ratio), True)

# --- COLOUR DOES NOT DRAW THEM -----------------------------------------------
s.contour_step = 0.2
s.shading = "colour"
fc = s.render(W, H)
check("in colour mode there are no lines",
      [crossings(fc, r) for r in (120, 150, 180)], [0, 0, 0])

s.shading = "both"
fb = s.render(W, H)
check("together with colour the lines are there",
      min(crossings(fb, r) for r in (120, 150, 180)) >= 5, True)

# --- THE INK DOES NOT FLOOD --------------------------------------------------
# EVERY FIFTH ONE IS HEAVIER. Promised both in the label on the page and in the
# header of the core, and a promise without a check is just a phrase. Over a
# span of 2 at a step of 0.2 the heavy ones come out at -1, 0 and 1: their
# indices are multiples of five.
s.shading = "contours"
s.contour_step = 0.2
dd = sorted(depths(s.render(W, H), 150))
mid, top = dd[len(dd) // 2], dd[-1]
print("     depth of the dip: median %.0f, largest %.0f, ratio %.2f"
      % (mid, top, top / mid))
check("every fifth line is noticeably heavier", top / mid >= 1.3, True)

mask = body_mask(fc)                                   # silhouette from the colour frame
s.shading = "contours"
s.contour_step = 0.2
share = ink_share(s.render(W, H), mask)
print("     inked inside the silhouette: %.1f%% (silhouette %d points)"
      % (share * 100, len(mask)))
check("the lines are thin, not a fill", share < 0.25, True)
s.close()

# A STEEP SLOPE WHERE THE LINES ARE DENSER THAN A PIXEL. The second degenerate
# case named: there is nothing to draw there, the lines would merge into
# muddle, and cartographers draw no contours in such a place. The subject is a
# plane with a slope of 14 to 1, seen almost edge on.
steep = nashira3d.Session("14*y", domain=(-1, 1, -1, 1), quality=60,
                          camera=(0.0, 0.18, 3.0, 0.9), axes=False)
steep.grid = False
steep.box = (1, 1, 0.9)
steep.fit = False
steep.contour_step = 0.2
steep.shading = "colour"
smask = body_mask(steep.render(W, H))
steep.shading = "contours"
sshare = ink_share(steep.render(W, H), smask)
print("     inked on the steep slope: %.1f%% (silhouette %d points)"
      % (sshare * 100, len(smask)))
check("the steep slope is not flooded with muddle", sshare < 0.15, True)
steep.close()

# LEVEL GROUND EXACTLY AT THE LEVEL OF A LINE. The degenerate case named in the
# shader: the distance to the line is zero everywhere there, and without a
# slope cut-off the ink would flood the whole patch. The formula z = 0 at a
# step of 1 lands exactly on a level.
flat = nashira3d.Session("0", domain=(-1, 1, -1, 1), quality=40,
                         camera=(0.6, 0.9, 3.2, 0.9), axes=False)
flat.grid = False
flat.contour_step = 1.0
flat.shading = "colour"
fmask = body_mask(flat.render(W, H))
flat.shading = "contours"
fshare = ink_share(flat.render(W, H), fmask)
print("     inked on the level patch: %.1f%% (silhouette %d points)"
      % (fshare * 100, len(fmask)))
check("a plane exactly at the level of a line is not flooded", fshare < 0.02, True)
flat.close()

# --- THE SETTING ACCEPTS ONLY ITS OWN ----------------------------------------
t = nashira3d.Session("x*x+y*y", domain=(-1, 1, -1, 1), quality=30)
check("the default is contour lines", t.shading, "contours")
try:
    t.shading = "rainbow"
    check("a foreign name is refused", False, True)
except ValueError:
    check("a foreign name is refused", True, True)
try:
    t.contour_step = -1
    check("a negative step is refused", False, True)
except Exception:
    check("a negative step is refused", True, True)
t.close()

print("")
print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
sys.exit(1 if bad else 0)
