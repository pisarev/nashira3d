"""The colour bar.

The bar has to be NOT A PICTURE BESIDE THE SCENE but a second face of the same
scene state.

An important distinction, which was stated wrongly at first: the COLOURS of the
bar do not depend on the range at all - the bar always shows the whole ramp,
from zero to one. What depends on the frozen range are the NUMBERS beside it.
So two different areas of the frame are checked, and in different ways.

There are two formulas as well, and both are chosen for a reason rather than
for variety:

  sin*cos*exp   - it decays, the surface does not reach the left edge of the
                  frame, so the BOUNDS of the bar and the colours of its ends
                  are measured on it;
  x*x+y*y       - its span grows as the square of the domain, so THE FREEZING
                  is checked on it. On the decaying one that check is useless:
                  its span does not depend on the domain, and an injected fault
                  - "the scale from the current sample again" - goes unnoticed;
                  checked, and the probe stayed silent.

The bounds of the bar depend only on the size of the frame, not on the formula,
so they are measured once on the first and used on the second.
"""

import os
import re
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


def ramp_ends():
    """The ends of the ramp, read FROM THE SHADER SOURCE. A private copy of the
    numbers would drift away from the shader at the first change of colour, and
    the probe would guard not what is drawn but what was once written in
    here."""
    src = open(os.path.join(HERE, "..", "core", "nsh_render.pas"),
               encoding="utf-8").read()
    blk = src[src.index("RAMP_SRC ="):src.index("RAMP_SRC =") + 900]
    got = re.findall(r"vec3 ([abc]) = vec3\(([\d.]+), ([\d.]+), ([\d.]+)\)", blk)
    d = {n: tuple(round(float(v) * 255) for v in (r, g, bl)) for n, r, g, bl in got}
    return d["a"], d["c"]


W, H = 640, 480
BX, BW = 22, 13

# The colour of a glyph. The text is snapped to whole pixels and produces no
# half-tones, so a glyph pixel is exactly one value and a glyph is recognised by
# it exactly.
TXT = (217, 224, 240)


def frame(s):
    return bytes(memoryview(s.render(W, H)).cast("B"))


def pix(buf, x, y):
    i = (y * W + x) * 4
    return (buf[i], buf[i + 1], buf[i + 2])


def bar(buf, y0, y1):
    return [pix(buf, BX + BW // 2, y) for y in range(y0 + 3, y1 - 2)]


def nums(buf, y0, y1):
    """The glyph pixels in the column of numbers. The colours of the whole area
    must not be compared: behind the text stands the surface, and it changes
    with the camera by right. What matters is WHERE the glyphs stand, not what
    is behind them.

    The bounds are taken exactly along the bar. Taking them wider is not
    allowed: past it the labels of the coordinate grid legitimately appear, and
    the probe would become flaky - measured, it disagreed at one camera
    position out of twelve."""
    return frozenset((x, y)
                     for y in range(y0, y1 + 1)
                     for x in range(BX + BW + 4, BX + BW + 56)
                     if pix(buf, x, y) == TXT)


def setup(formula, quality=70):
    s = nashira3d.Session(formula, quality=quality)
    # The subject of the probe is the COLOUR BAR, so colour is what has to be
    # asked for. Under contour lines the bar stops being a colour one by
    # design, not by mistake.
    s.shading = "colour"
    s.domain = (-2, 2, -2, 2)
    s.box = (2, 2, 0.6)
    s.fit = False
    s.grid = True
    s.axes = False
    s.camera = (0.85, 0.42, 3.4, 0.9)
    return s


# --- BOUNDS AND COLOURS, on the decaying one ---------------------------------
s = setup("sin(3*x)*cos(3*y)*exp(-(x*x+y*y))")
f0 = frame(s)

# The bounds are found from TWO CASES: the same frame without the bar is
# subtracted from the frame with it. Working out the placement here would be a
# second place where this arithmetic has to be edited, and the first place
# where it would drift apart.
s.grid = False
s.axes = True
f_no = frame(s)
s.grid = True
s.axes = False

x = BX + BW // 2
diff = [y for y in range(H) if pix(f0, x, y) != pix(f_no, x, y)]
runs, cur = [], []
for y in diff:
    if cur and y == cur[-1] + 1:
        cur.append(y)
    else:
        if cur:
            runs.append(cur)
        cur = [y]
if cur:
    runs.append(cur)
runs.sort(key=len)
check("the bar was found as the difference from a frame without it", bool(runs), True)
if not runs:
    print("")
    print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
    sys.exit(1)
Y0, Y1 = runs[-1][0], runs[-1][-1]
check("the height of the bar is within reason", 100 <= Y1 - Y0 <= 270, True)

lo_want, hi_want = ramp_ends()
# Three pixels in from the edge: a one-pixel border, once multisampling is
# resolved, smears over two rows, and right at the edge the probe would catch a
# mixture of border and ramp - measured, (227, 209, 109) came out instead of
# (250, 219, 77).
hi_got = pix(f0, x, Y0 + 3)
lo_got = pix(f0, x, Y1 - 3)


def near(a, b):
    """A tolerance of two levels out of two hundred and fifty-six is the price
    of those three pixels of inset: over them the ramp already moves slightly
    away from its end."""
    return all(abs(u - v) <= 2 for u, v in zip(a, b))


check("the top of the bar is the end of the ramp from the source %s" % (hi_want,),
      near(hi_got, hi_want), True)
check("the bottom of the bar is the start of the ramp from the source %s" % (lo_want,),
      near(lo_got, lo_want), True)
check("the middle of the bar matched neither end",
      pix(f0, x, (Y0 + Y1) // 2) not in (lo_got, hi_got), True)
s.close()

# --- THE FREEZING, on the growing one ----------------------------------------
s = setup("x*x + y*y - 4")
f1 = frame(s)
base_bar, base_num = bar(f1, Y0, Y1), nums(f1, Y0, Y1)
check("the glyphs in the column of numbers were found", len(base_num) > 40, True)

# The camera TOGETHER with the domain. The camera alone would prove nothing:
# the mesh is not recomputed from it, and the old behaviour would pass this
# check straight through - which is what happened under injection. In use the
# page works the domain out FROM the camera, so here it changes together with
# it, as it does on the page.
moved_bar = moved_num = 0
for i in range(12):
    d = 1.4 + i * 0.31
    s.camera = (0.2 + i * 0.13, 0.25 + (i % 5) * 0.08, 3.0 + i * 0.1, 0.9)
    s.domain = (-d, d, -d, d)
    s.box = (d, d, 0.3 * d)
    f = frame(s)
    if bar(f, Y0, Y1) != base_bar:
        moved_bar += 1
    if nums(f, Y0, Y1) != base_num:
        moved_num += 1
check("twelve views with their own domains: the bar is intact", moved_bar, 0)
check("twelve views with their own domains: the numbers are intact", moved_num, 0)

s.camera = (0.85, 0.42, 3.4, 0.9)
s.domain = (-2, 2, -2, 2)
s.box = (2, 2, 0.6)
s.pan = (0.4, -0.3)
check("shifting the domain did not change the numbers",
      nums(frame(s), Y0, Y1) == base_num, True)
s.pan = (0.0, 0.0)

# --- BUT A CHANGE OF SPAN DOES TOUCH THEM ------------------------------------
# The injection: numbers drawn on their own would survive this too.
s.formula = "(x*x + y*y - 4) * 4"
check("a span four times greater changed the numbers",
      nums(frame(s), Y0, Y1) != base_num, True)
check("but did not change the bar itself: the ramp is always whole",
      bar(frame(s), Y0, Y1) == base_bar, True)

s.formula = "x*x + y*y - 4"
check("putting the formula back brought the earlier numbers back",
      nums(frame(s), Y0, Y1) == base_num, True)

# --- THE BAR LOOKS FOR A GAP BETWEEN THE PANELS ------------------------------
# The reason: at first the bar stood in the middle on the left, and if there
# was a panel on the left, on the right. On the real page the panels stand in
# the corners on BOTH sides, both middles are taken, and the bar stayed under a
# panel - measured, 90 pixels of its own numbers lay under the panels. The
# layout here is the same as on the page.

s.grid = True
s.axes = False
s.formula = "sin(3*x)*cos(3*y)*exp(-(x*x+y*y))"
s.domain = (-1.4, 1.4, -1.4, 1.4)
s.box = (1.4, 1.4, 0.42)
s.camera = (0.9, 0.45, 3.4, 0.9)

# The layout of the real 1440x900 page, scaled down to the probe's frame. At a
# frame of 640 the right-hand pair has to stay INSIDE THE FRAME, or the right
# side turns out empty and the probe checks the wrong thing - which is what
# happened the first time round.
PANELS = [(7, 9, 151, 126), (528, 9, 105, 210),
          (7, 233, 151, 238), (528, 376, 105, 95)]

# The gap on the right is worked out FROM THE PANELS THEMSELVES rather than
# written in as a number: a written-in number would drift away from the layout
# at its first edit.
RGAP0 = PANELS[1][1] + PANELS[1][3]     # bottom of the upper right panel
RGAP1 = PANELS[3][1]                    # top of the lower right panel


def glyphs_under(buf):
    n = 0
    for px0, py0, pw, ph in PANELS:
        for y in range(py0, min(H, py0 + ph)):
            for xx in range(px0, min(W, px0 + pw)):
                if pix(buf, xx, y) == TXT:
                    n += 1
    return n


def bar_rows(buf, xx):
    """The rows where the colour of the ramp stands in column xx."""
    out = []
    for y in range(H):
        r, g, bl = pix(buf, xx, y)
        if (bl > 120 and r < 70) or (r > 200 and g > 180 and bl < 130):
            out.append(y)
    return out


s.obstacles = []
free = frame(s)
check("with no panels there are labels where they would stand",
      glyphs_under(free) > 50, True)

s.obstacles = PANELS
held = frame(s)
check("with the panels not one pixel is left under them", glyphs_under(held), 0)

rows = bar_rows(held, W - 22 - 13 + 6)
check("the bar moved to the right side", len(rows) > 80, True)
if rows:
    check("the bar stood in the gap between the panels %d..%d" % (RGAP0, RGAP1),
          rows[0] >= RGAP0 and rows[-1] <= RGAP1, True)

s.obstacles = []

# --- WITHOUT THE GRID THERE IS NO BAR ----------------------------------------
# The bar came in place of the edges of the box and lives in the same mode as
# the grid.
s.grid = False
s.axes = True
check("in box mode there is no bar", bar(frame(s), Y0, Y1) != base_bar, True)

s.close()

print("")
print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
sys.exit(1 if bad else 0)
