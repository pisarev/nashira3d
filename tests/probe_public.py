"""Acceptance THROUGH THE USER'S EYES: the public interface only, not a single
call into _binding. If something here is awkward or silent, it is awkward and
silent for them."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "python"))
import nashira3d

HERE = os.path.dirname(os.path.abspath(__file__))
ok, bad = 0, []


def check(name, got, want):
    global ok
    if got == want:
        ok += 1
        print("  ok   %-48s %s" % (name, got))
    else:
        bad.append(name)
        print("  FAIL %-48s got %r, want %r" % (name, got, want))


def raises(name, fn):
    global ok
    try:
        fn()
    except nashira3d.Nashira3DError as e:
        ok += 1
        print("  ok   %-48s %s" % (name, str(e)[:44]))
        return
    except Exception as e:
        bad.append(name)
        print("  FAIL %-48s a foreign exception: %r" % (name, e))
        return
    bad.append(name)
    print("  FAIL %-48s it went through in silence" % name)


check("the core version is not empty", len(nashira3d.version()) > 0, True)

with nashira3d.Session("x*x + y*y", domain=(-1, 1, -1, 1), quality=55) as s:
    img = s.render(240, 180)
    check("the shape of the frame", tuple(img.shape), (180, 240, 4))
    check("the pixel type", str(img.dtype), "uint8")
    check("the properties read back", s.formula, "x*x + y*y")
    check("the domain reads back", s.domain, (-1.0, 1.0, -1.0, 1.0))

    p = s.save_png(os.path.join(HERE, "public_bowl.png"), 240, 180)
    head = open(p, "rb").read(8)
    check("the PNG is written with the right header", head, b"\x89PNG\r\n\x1a\n")
    check("and it is not empty", os.path.getsize(p) > 1000, True)

    raises("nonsense instead of a formula - an exception",
           lambda: setattr(s, "formula", "x +* "))
    raises("an inverted domain - an exception",
           lambda: setattr(s, "domain", (1, -1, -1, 1)))
    raises("quality 101 - an exception", lambda: setattr(s, "quality", 101))
    raises("a zero distance - an exception",
           lambda: setattr(s, "camera", (0, 0, 0, 1)))

# TWO SESSIONS IN TURN. There is one renderer in the library, and without a
# memory of whose mesh is on the card now, the second session would draw
# somebody else's surface.
a = nashira3d.Session("x*x + y*y", domain=(-1, 1, -1, 1), quality=40)
b2 = nashira3d.Session("x*x - y*y", domain=(-1, 1, -1, 1), quality=40)
ia1 = a.render(160, 120)
ib1 = b2.render(160, 120)
ia2 = a.render(160, 120)
check("two sessions give DIFFERENT pictures", bool((ia1 != ib1).any()), True)
check("and the first was not spoiled by the second", bool((ia1 == ia2).all()), True)
a.close()
b2.close()

s2 = nashira3d.Session("x")
s2.close()
raises("a closed session answers with a refusal", lambda: s2.render(8, 8))

# --- SHIFTING THE POINT OF VIEW ----------------------------------------------
# The reason: before it the plot was nailed to the middle of the frame, and
# there was no way to move it aside. What is checked is not the presence of the
# field but that the frame MOVES, and that returning to zero gives THE SAME
# frame - otherwise the shift could accumulate error.

sp = nashira3d.Session("sin(3*x)*cos(3*y)", quality=20)
check("the shift is zero by default", sp.pan, (0.0, 0.0))

home = bytes(memoryview(sp.render(120, 90)).cast("B"))

sp.pan = (0.5, 0.0)
right = bytes(memoryview(sp.render(120, 90)).cast("B"))
check("a shift to the right changes the frame", right != home, True)

sp.pan = (0.0, -0.4)
down = bytes(memoryview(sp.render(120, 90)).cast("B"))
check("a shift downwards changes the frame", down != home, True)
check("right and down are different frames", right != down, True)

sp.pan = (0.0, 0.0)
back = bytes(memoryview(sp.render(120, 90)).cast("B"))
check("returning to zero gives the original frame", back == home, True)

raises("a NaN shift is refused", lambda: setattr(sp, "pan", (float("nan"), 0.0)))
raises("an inf shift is refused", lambda: setattr(sp, "pan", (0.0, float("inf"))))
check("after the refusal the shift is as it was", sp.pan, (0.0, 0.0))

# A large move past the edge of the frame is a LEGITIMATE action, not an error:
# the user has every right to look at a corner of the surface from close up.
sp.pan = (12.0, -9.0)
far = bytes(memoryview(sp.render(120, 90)).cast("B"))
check("a large move is accepted", sp.pan, (12.0, -9.0))
check("the moved frame differs from the original", far != home, True)
sp.close()

# --- THE PROPORTIONS OF THE BOX ----------------------------------------------
# The reason: the box was hard-wired with constants, the base always square,
# the height always three times lower. There was no way to make out a fine
# ripple - it was flattened along with everything else. What is checked is that
# each axis ACTS on its own: "the picture changed" alone is not enough, it
# would pass even if all three axes were glued into one factor.

sb = nashira3d.Session("sin(4*x)*cos(4*y)", quality=25)
check("the box by default", sb.box, (1.0, 1.0, 0.3))

def shot(w=110, h=90):
    return bytes(memoryview(sb.render(w, h)).cast("B"))

home = shot()
sb.box = (1.0, 1.0, 0.9);  taller = shot()
sb.box = (1.7, 1.0, 0.3);  wider  = shot()
sb.box = (1.0, 1.7, 0.3);  deeper = shot()
check("the height acts", taller != home, True)
check("the width acts", wider != home, True)
check("the depth acts", deeper != home, True)
check("width and depth are different axes", wider != deeper, True)
check("height is not the same as width", taller != wider, True)

sb.box = (1.0, 1.0, 0.3)
check("putting it back gives the original frame", shot() == home, True)

raises("a zero height is refused", lambda: setattr(sb, "box", (1.0, 1.0, 0.0)))
raises("a negative width is refused", lambda: setattr(sb, "box", (-1.0, 1.0, 0.3)))
raises("NaN is refused", lambda: setattr(sb, "box", (1.0, float("nan"), 0.3)))
check("after the refusals the box is as it was", sb.box, (1.0, 1.0, 0.3))
sb.close()

# --- THE FROZEN VERTICAL SCALE -----------------------------------------------
# The reason: the scale was taken from the minimum and maximum of the CURRENT
# sample, and the sample changes with every movement of the camera - which
# means the camera changed the geometry of the plot. Move away, let a new peak
# enter the domain, and the whole of the earlier surface sagged.
#
# What is checked is NOT "going back to the earlier domain gives the earlier
# frame" - that would have passed before the fix too. What is checked is that
# the frame on a NEW domain does NOT DEPEND on that domain's own span: the
# frozen and the recomputed frames on one and the same domain have to differ.
# x*x+y*y is used, whose span grows as the square of the domain.

_closed = nashira3d.Session("x")
_closed.close()
def closed_fit():
    _closed.fit_z()

sz = nashira3d.Session("x*x+y*y", quality=25)
sz.fit = False
sz.camera = (0.85, 0.45, 3.4, 0.9)

def shot(half):
    sz.domain = (-half, half, -half, half)
    sz.box = (half, half, 0.3 * half)
    return bytes(memoryview(sz.render(120, 90)).cast("B"))

narrow = shot(1.5)          # the first build freezes the scale: a span of 4.5
wide_frozen = shot(10.0)    # here the true span is 200, but the scale is the old one
sz.fit_z()
wide_fitted = shot(10.0)

check("the frozen and the recomputed frames differ", wide_frozen != wide_fitted, True)

sz.fit_z()
sz.formula = "x*x+y*y"
again_narrow = shot(1.5)
check("after a change of formula the scale is computed anew",
      len(again_narrow) == len(narrow), True)

# camera movements do not touch the scale: a hundred domain changes and back
sz.formula = "sin(3*x)*cos(3*y)"
home = shot(2.0)
for i in range(25):
    shot(2.0 + i * 0.37)
    shot(2.0 + i * 0.11)
    sz.camera = (0.3 + i * 0.05, 0.4 + (i % 7) * 0.05, 3.4, 0.9)
    sz.pan = (i * 0.01, -i * 0.01)
sz.camera = (0.85, 0.45, 3.4, 0.9)
sz.pan = (0.0, 0.0)
check("a hundred camera operations did not move the scale", shot(2.0) == home, True)

# --- TWO SESSIONS, ONE RENDERER ----------------------------------------------
# There is ONE renderer in the library, and there can be any number of
# sessions. There is one mesh on the card, and whose it is, LastUploader
# remembers. Until now that rested on a comment in the source, and a comment
# guards nothing.
#
# What is checked is the alternation: two sessions with DIFFERENT formulas draw
# in turn, and each has to get its own frame rather than its neighbour's.

import hashlib as _hl


def _h(buf):
    return _hl.sha256(bytes(memoryview(buf).cast("B"))).hexdigest()


s1 = nashira3d.Session("sin(3*x)*cos(3*y)", quality=40)
s2 = nashira3d.Session("x*x-y*y", quality=40)
for _s in (s1, s2):
    _s.domain = (-1, 1, -1, 1)
    _s.box = (1, 1, 0.3)
    _s.fit = False
    _s.grid = True
    _s.axes = False
    _s.camera = (0.9, 0.6, 3.4, 0.9)

h1 = _h(s1.render(200, 150))
h2 = _h(s2.render(200, 150))
check("two sessions have different frames", h1 != h2, True)

mixed = all(_h(s1.render(200, 150)) == h1 and _h(s2.render(200, 150)) == h2
            for _ in range(4))
check("alternating sessions do not confuse the meshes", mixed, True)

# One of them moves to a camera as a standing point - that must not touch the
# neighbour.
s1.stand(0.5, 0.5, 2.0, 0.9, 0.85)
check("the move by one session changed ITS frame",
      _h(s1.render(200, 150)) != h1, True)
check("and did not touch the neighbour's frame", _h(s2.render(200, 150)) == h2, True)

# An unsound formula: the previous one has to stay alive rather than be wiped.
before = _h(s2.render(200, 150))
raises("an unsound formula is refused", lambda: setattr(s2, "formula", "x +* "))
check("after the refusal the previous formula is alive",
      _h(s2.render(200, 150)) == before, True)

s1.close()
s2.close()

# --- THE SAME FORMULA IS NOT A CHANGE OF FORMULA -----------------------------
# The reason: the caller has every right to send the whole state every frame,
# and the page does exactly that. While each such send counted as a change of
# formula, the frozen scale was unfrozen on EVERY frame, and there was no
# freezing at all. Measured through the bridge: fit_z changed nothing, because
# the scale was being recomputed anyway.
#
# The check goes by the picture, not by a flag: the flag is not exposed, and it
# is the behaviour that shows.

sr = nashira3d.Session("x*x+y*y", quality=25)
sr.fit = False
sr.camera = (0.85, 0.45, 3.4, 0.9)


def shot_r(half):
    sr.domain = (-half, half, -half, half)
    sr.box = (half, half, 0.3 * half)
    return bytes(memoryview(sr.render(120, 90)).cast("B"))


shot_r(1.5)                       # freeze on the narrow domain
wide_once = shot_r(10.0)
for _ in range(5):                # the same formula five more times, as the page sends it
    sr.formula = "x*x+y*y"
check("repeating the same formula did not unfreeze the scale",
      shot_r(10.0) == wide_once, True)

sr.formula = "x*x + y*y"          # DIFFERENT text, the same function - that is a change
check("a different formula text recomputed the scale",
      shot_r(10.0) != wide_once, True)
sr.close()

# --- AUTO Z WITH HYSTERESIS --------------------------------------------------
# OFF by default, and that is a decision rather than caution: constant
# auto-fitting makes the geometry a consequence of the camera, and the surface
# sags as soon as a new peak enters the domain.
#
# The formula is chosen for a reason: for x*x+y*y the span over the domain ±a
# is exactly 2*a*a, and the ratio can be worked out on paper. For the decaying
# sin*cos*exp the span does NOT DEPEND on the domain at all - measured, 1.5885
# at ±0.4 against 1.5969 at ±2 - and on it the probe would always stay silent,
# checking nothing.

sa = nashira3d.Session("x*x+y*y", quality=40)
sa.fit = False
sa.grid = False
sa.axes = False


def at(half):
    sa.domain = (-half, half, -half, half)
    sa.box = (half, half, 0.3 * half)
    sa.render(160, 120)
    return sa.auto_z_fired()


at(1.0)                       # freeze: a span of 2
check("off by default", sa.auto_z, False)
check("switched off, it stays silent even at a fivefold growth", at(2.24), False)

sa.auto_z = True
sa.auto_z_fired()             # clear the trace left by switching it on
check("switching on shows in the property", sa.auto_z, True)

# The series is chosen so that every ratio can be worked out on paper: 2*a*a to
# the current span. The entry threshold is 2.0, the latch clears below 1.5.
seq = [(1.34, False),         # 3.59 / 2.00 = 1.80 - below the threshold
       (1.60, True),          # 5.12 / 2.00 = 2.56 - entry
       (2.00, False),         # 8.00 / 5.12 = 1.56 - below the threshold
       (2.60, True),          # 13.52 / 5.12 = 2.64 - entry
       (2.70, False),         # 14.58 / 13.52 = 1.08
       (3.80, True)]          # 28.88 / 13.52 = 2.14 - entry
wrong = [a for a, want in seq if at(a) != want]
check("six positions: it fires exactly at the threshold", wrong, [])

check("the flag reads ONCE and goes out", sa.auto_z_fired(), False)
sa.close()

# --- THE TAKEN PLACES OF THE FRAME -------------------------------------------
# The caller's panels lie OVER the frame, and the library cannot see them. The
# hint about them has to be not merely accepted but ACTED ON: not one pixel of
# a label should be left under a panel.

so = nashira3d.Session("sin(3*x)*cos(3*y)*exp(-(x*x+y*y))", quality=70)
so.domain = (-2, 2, -2, 2)
so.box = (2, 2, 0.6)
so.fit = False
so.grid = True
so.axes = False
so.camera = (0.85, 0.42, 3.4, 0.9)

OW, OH = 800, 560
PANEL = (OW - 260, 0, 260, OH)
TXT = (217, 224, 240)


def glyphs_in_panel():
    buf = bytes(memoryview(so.render(OW, OH)).cast("B"))
    n = 0
    for y in range(PANEL[1], PANEL[1] + PANEL[3]):
        row = (y * OW) * 4
        for x in range(PANEL[0], PANEL[0] + PANEL[2]):
            i = row + x * 4
            if (buf[i], buf[i + 1], buf[i + 2]) == TXT:
                n += 1
    return n


before = glyphs_in_panel()
check("without the hint there are labels in the right-hand strip", before > 100, True)
so.obstacles = [PANEL]
check("with the hint not one is left under the panel", glyphs_in_panel(), 0)
so.obstacles = []
check("the hint removed - the labels came back", glyphs_in_panel(), before)

raises("a triple instead of a quadruple is refused",
       lambda: setattr(so, "obstacles", [(0, 0, 10)]))
so.close()

raises("fit_z on a closed session is refused", lambda: closed_fit())
sz.close()

print("")
print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
for n in bad:
    print("   %s" % n)
sys.exit(1 if bad else 0)
