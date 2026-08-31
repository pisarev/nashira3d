"""The arithmetic of the camera on the page - BY RUNNING IT, not by reading the
source.

The other checks of the page read its text: is there a call, does it branch by
mode. For connections that will do; for arithmetic it will not. "camH does not
appear in the body of the function" does not mean "the height does not change":
the height can be touched through an intermediary, and can be left alone even
when mentioned. About the formula of the turn the text says nothing at all.

So the functions needed are pulled out of the page by name and run in Node with
the globals supplied. The subject of the check is the NUMBERS that come out.

What is checked:

  turn   - the camera stands still: the standing point and the height do not
           change by any amount, and the direction taken stays exactly under
           the cursor;
  orbit  - the radius to the pivot holds, the pivot stays under the central
           ray, and bringing the cursor back returns the view to exactly the
           same place;
  both of them - with no breaks at a vertical look and at zero height.
"""

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "..", "web", "preview.html")

ok, bad = 0, []


def check(name, got, want):
    global ok
    if got == want:
        ok += 1
        print("  ok   %-52s %s" % (name, got))
    else:
        bad.append(name)
        print("  FAIL %-52s got %r, want %r" % (name, got, want))


with open(PAGE, encoding="utf-8") as f:
    page = f.read()


def func(name):
    """The body of a function by name, from the header to the matching brace."""
    m = re.search(r"\bfunction\s+%s\s*\(" % re.escape(name), page)
    if not m:
        raise SystemExit("the page has no function " + name)
    i = page.index("{", m.end() - 1)
    depth, j = 0, i
    while j < len(page):
        if page[j] == "{":
            depth += 1
        elif page[j] == "}":
            depth -= 1
            if depth == 0:
                return page[m.start():j + 1]
        j += 1
    raise SystemExit("the end of the function was not found: " + name)


NEED = ["camBasis", "screenScale", "rayWorld", "dirToScreen", "turnTo",
        "tiltStand", "orbitPivot", "orbitPlace", "orbitDrag", "panTarget",
        "turnFallback", "panDomain", "stepHeight", "zoomDomain", "wheelStep",
        "groundAt", "camQ", "camFromQ", "focusPoint", "cubeRadius",
        "orbitRate", "orbitClamp", "cubePan", "cubeDolly", "nav_pan"]

HARNESS = r"""
// The globals these functions take from the page.
let az = 0.9, el = 0.85, camX = 0, camY = 0, camH = 2.0, fov = 0.9;
/* This probe is about the INFINITE PLANE: there the gestures have to follow
   the hand at any view. The cube is checked separately, by the contract probe,
   because it has a different law of control - and that was a decision, not an
   oversight. */
let drawIn = "plane";
let cubeFocus = null;
const ORBIT_EL_LIMIT = (89.5 * Math.PI) / 180;
let dom = [-1, 1, -1, 1], declDom = [-1, 1, -1, 1];
let zoom = 1.4, navDomain = false, coreDirty = false;
const H_SOFT = 0.09, H_LIMIT = 1e5;
const domainNow = () => dom.slice();
function showDomain() {}
function setDomain(x0, x1, y0, y1) { dom = [x0, x1, y0, y1]; }
const HORIZON = 40, MIN_SIN = 1 / HORIZON;
let drag = null;
const view = { clientWidth: 900, clientHeight: 560 };
// $("mo") is the offset readout; nobody needs it here, but the function
// touches it.
const $ = () => ({ set textContent(v) {}, get value() { return "1"; } });

%s

const out = { checks: [] };
function say(name, value) { out.checks.push([name, value]); }

// --- TURN: the camera has to stand still ------------------------------------
function screenAt(sx, sy) { return [sx, sy]; }
{
  az = 0.9; el = 0.85; camX = 1.3; camY = -0.7; camH = 2.2;
  const before = [camX, camY, camH];
  const grab = rayWorld(-0.4, 0.2, az, el);
  let worst = 0, held = 0;
  for (const [sx, sy] of [[-0.2, 0.1], [0.3, -0.25], [0.0, 0.4], [-0.45, -0.3]]) {
    turnTo(grab, sx, sy);
    worst = Math.max(worst,
      Math.abs(camX - before[0]), Math.abs(camY - before[1]), Math.abs(camH - before[2]));
    // the direction taken has to land exactly on the point asked for
    const p = dirToScreen(grab, az, el);
    if (p) held = Math.max(held, Math.hypot(p[0] - sx, p[1] - sy));
  }
  say("turn_moved", worst);
  say("turn_held", held);
}

// --- ORBIT: the radius holds, the pivot stays under the central ray ---------
{
  az = 0.9; el = 0.85; camX = 1.3; camY = -0.7; camH = 2.2;
  const ob = orbitPivot();
  drag = { pivot: ob.p, radius: ob.r, planeSide: (camH < 0 ? -1 : 1), az0: az, el0: el, x0: 0, y0: 0 };
  let dR = 0, dAim = 0;
  for (const [dx, dy] of [[120, 0], [-300, 40], [0, -90], [450, 130], [-40, -200]]) {
    orbitDrag(dx, dy);
    const v = [ob.p[0] - camX, ob.p[1] - camY, ob.p[2] - camH];
    dR = Math.max(dR, Math.abs(Math.hypot(v[0], v[1], v[2]) - ob.r));
    // the central ray still has to look at the pivot
    const c = rayWorld(0, 0, az, el);
    const L = Math.hypot(v[0], v[1], v[2]) || 1;
    const cosang = (c[0]*v[0] + c[1]*v[1] + c[2]*v[2]) / L;
    dAim = Math.max(dAim, Math.abs(1 - cosang));
  }
  say("orbit_radius", dR);
  say("orbit_aim", dAim);
}

// --- ORBIT BY POSITION, NOT BY PATH -----------------------------------------
{
  az = 0.9; el = 0.85; camX = 1.3; camY = -0.7; camH = 2.2;
  const ob = orbitPivot();
  drag = { pivot: ob.p, radius: ob.r, planeSide: (camH < 0 ? -1 : 1), az0: az, el0: el, x0: 0, y0: 0 };
  orbitDrag(200, -60);
  const there = [camX, camY, camH, az, el];
  // a long roundabout path and a return to THE SAME cursor point
  for (const [dx, dy] of [[-500, 300], [700, -400], [10, 10], [200, -60]]) orbitDrag(dx, dy);
  let worst = 0;
  const now = [camX, camY, camH, az, el];
  for (let i = 0; i < 5; i++) worst = Math.max(worst, Math.abs(now[i] - there[i]));
  say("orbit_path", worst);
}

// --- WHERE THE PICTURE GOES: A SWEEP OF VIEWS -------------------------------
// The signs are checked NOT by a number in the state but by where a point of
// the ground goes on the screen: the numbers in the state were correct with
// the signs reversed as well, and the inversion was caught by hand three
// times.
//
// A SWEEP, not one view. There used to be exactly one here: azimuth pi,
// elevation 0.85, a point off to the side. It passed - and it missed the
// inversion of the orbit, because the point happened to lie on the FAR side of
// the pivot. In an orbit the camera moves, so there is parallax: points nearer
// than the pivot and farther than it travel in DIFFERENT directions, and one
// point proves nothing. Measured on a real scene with the pivot 22.6 units
// away: at 5 units -0.38, at 200 units +0.45.
//
// A near point is taken, and a VISIBLE one: under a ray through the lower part
// of the frame. A quarter of the way to the pivot would not do - at a steep
// look it goes below the bottom edge, where there is nothing to check (the
// measurement gave 0.001 and eight false failures out of forty).
{
  const AZS = [0, 0.79, 1.57, 2.36, 3.14, 3.93, 4.71, 5.50];
  const ELS = [0.12, 0.3, 0.55, 0.85, 1.2];
  const wrong = { orbitX: 0, orbitY: 0, turnX: 0, turnY: 0 };
  const weak = { orbitX: 0, orbitY: 0, turnX: 0, turnY: 0 };
  let tried = 0, triedStrong = 0;

  function seen(p) {
    const v = [p[0] - camX, p[1] - camY, p[2] - camH];
    const L = Math.hypot(v[0], v[1], v[2]) || 1;
    return dirToScreen([v[0] / L, v[1] / L, v[2] / L], az, el);
  }
  function groundUnder(sy) {
    const d = rayWorld(0, sy, az, el);
    if (Math.abs(d[2]) < 1e-9) return null;
    const t = -camH / d[2];
    if (!(t > 0) || t > 1e6) return null;
    return [camX + d[0] * t, camY + d[1] * t, 0];
  }

  // TWO SIDES OF THE PLANE, not one. The ground is visible only when the sign
  // of the height matches the sign of the elevation: the ray z = h - t*sin(el)
  // reaches zero at t = h/sin(el) > 0. So there are exactly two cases - from
  // above looking down and from below looking up - and both have to behave the
  // same under the hand.
  //
  // From above the sweep existed before; from below it did not, and there the
  // orbit again went against the hand: eight cases out of twenty-four,
  // dx=-0.172, dy=+0.213. Found by an investigation AFTER the signs above had
  // already been fixed.
  for (const a0 of AZS) for (const e0 of ELS) for (const sd of [1, -1]) {
    const S = { az: a0, el: e0 * sd, camX: 0, camY: 0, camH: 2.5 * sd };
    const put = () => { az = S.az; el = S.el; camX = S.camX; camY = S.camY; camH = S.camH; };

    put();
    const mark = groundUnder(-0.6);
    if (!mark) continue;
    tried++;
    const strong = e0 <= 0.85;
    void strong;
    if (strong) triedStrong++;

    // ORBIT
    put();
    const ob = orbitPivot();
    const o0 = seen(mark);
    put(); drag = { pivot: ob.p, radius: ob.r, planeSide: (camH < 0 ? -1 : 1), az0: S.az, el0: S.el, x0: 0, y0: 0 };
    orbitDrag(150, 0);
    const ox = seen(mark);
    put(); drag = { pivot: ob.p, radius: ob.r, planeSide: (camH < 0 ? -1 : 1), az0: S.az, el0: S.el, x0: 0, y0: 0 };
    orbitDrag(0, 120);
    const oy = seen(mark);
    if (o0 && ox && ox[0] - o0[0] < -0.005) wrong.orbitX++;
    if (o0 && oy && oy[1] - o0[1] > 0.005) wrong.orbitY++;
    if (strong) {
      if (!(o0 && ox && ox[0] - o0[0] > 0.02)) weak.orbitX++;
      if (!(o0 && oy && oy[1] - o0[1] < -0.02)) weak.orbitY++;
    }
    void 0;

    // TURN
    put();
    const grab = rayWorld(0, -0.3, az, el);
    const tm = [camX + grab[0] * 8, camY + grab[1] * 8, camH + grab[2] * 8];
    const t0 = seen(tm);
    put(); turnTo(grab, 0.3, -0.3);
    const tx = seen(tm);
    put(); turnTo(grab, 0.0, -0.6);
    const ty = seen(tm);
    if (t0 && tx && tx[0] - t0[0] < -0.005) wrong.turnX++;
    if (t0 && ty && ty[1] - t0[1] > 0.005) wrong.turnY++;
    if (strong) {
      if (!(t0 && tx && tx[0] - t0[0] > 0.02)) weak.turnX++;
      if (!(t0 && ty && ty[1] - t0[1] < -0.02)) weak.turnY++;
    }
  }
  say("sweep_tried", tried);
  say("sweep_wrong", wrong.orbitX + wrong.orbitY + wrong.turnX + wrong.turnY);
  say("sweep_weak", weak.orbitX + weak.orbitY + weak.turnX + weak.turnY);
  say("sweep_detail", JSON.stringify(wrong) + " weak " + JSON.stringify(weak));
}

// --- THE REMAINING GESTURES, BY THE SAME SWEEP ------------------------------
// There is now ONE camera for both drawing modes, and one of each gesture as
// well. A second, orbit camera used to be checked here: it had a turn of its
// own and a move of its own. It is gone - for an orbit camera "turn on the
// spot" cannot be expressed at all, and Turn and Orbit in the cube did the
// same thing.
//
// What remains to be checked is the move of the DOMAIN: in the cube it lives
// under Ctrl and moves not the view but the place where the function is
// computed.
{
  const AZS = [0, 0.79, 1.57, 2.36, 3.14, 3.93, 4.71, 5.50];
  const ELS = [0.15, 0.35, 0.6, 0.9, 1.2];
  let wrong = 0, tried = 0;
  const detail = {};
  function note(k, ok) { if (!ok) { wrong++; detail[k] = (detail[k] || 0) + 1; } }
  function seenFrom(e, p) {
    const v = [p[0] - e[0], p[1] - e[1], p[2] - e[2]];
    const L = Math.hypot(v[0], v[1], v[2]) || 1;
    return dirToScreen([v[0] / L, v[1] / L, v[2] / L], az, el);
  }
  for (const a0 of AZS) for (const e0 of ELS) {
    tried++;
    az = a0; el = e0; camX = 0; camY = 0; camH = 2.5;
    const d = rayWorld(0, -0.4, az, el);
    if (Math.abs(d[2]) < 1e-9) continue;
    const t = -camH / d[2];
    if (!(t > 0) || t > 1e6) continue;
    // a world point taken by ITS PLACE IN THE DOMAIN: move the domain and the
    // place moves with it, while the camera stays where it stood
    const world = [camX + d[0] * t * 0.6, camY + d[1] * t * 0.6];
    const D0 = [-4, 4, -4, 4];
    const box = (dd) => {
      const h = Math.max((dd[1] - dd[0]) / 2, (dd[3] - dd[2]) / 2);
      return [(world[0] - (dd[0] + dd[1]) / 2) / h,
              (world[1] - (dd[2] + dd[3]) / 2) / h, 0];
    };
    const eye = [camX, camY, camH];
    dom = D0.slice(); const r0 = seenFrom(eye, box(dom));
    // The step is SMALL for the same reason as with the camera move: at an
    // elevation of 0.15, thirty pixels vertically move the domain by 4.1
    // units, and the mark flies behind the camera - dirToScreen returns null
    // and the check goes red on a sound move. Measured, eight views out of
    // forty.
    dom = D0.slice(); panDomain(10, 0);  const rx = seenFrom(eye, box(dom));
    dom = D0.slice(); panDomain(0, 8);   const ry = seenFrom(eye, box(dom));
    note("regionPanX", r0 && rx && rx[0] - r0[0] > 0.002);
    note("regionPanY", r0 && ry && ry[1] - r0[1] < -0.002);
  }
  say("others_tried", tried);
  say("others_wrong", wrong);
  say("others_detail", JSON.stringify(detail));
}

// --- THE WHEEL ---------------------------------------------------------------
// One contract for three modes: AWAY FROM YOU means come closer. What changes
// while it happens differs between the modes, so each has its own thing
// checked: the height of the camera, the factor of the domain, the distance to
// the box. This does not replace the picture - that a lower height gives a
// smaller domain is checked by the core separately.
{
  const w = {};
  drawIn = "plane"; camH = 2.5;
  wheelStep(false, false); w.standFwd = camH;
  camH = 2.5; wheelStep(true, false); w.standBack = camH;

  // In the cube, Ctrl gives a second model: the wheel widens the DOMAIN itself.
  drawIn = "cube"; dom = [-2, 2, -2, 2];
  wheelStep(false, true); w.regionFwd = dom[1] - dom[0];
  dom = [-2, 2, -2, 2]; wheelStep(true, true); w.regionBack = dom[1] - dom[0];

  // And without Ctrl - the same as on the plane: the distance to the surface.
  drawIn = "cube"; camH = 2.5;
  wheelStep(false, false); w.camFwd = camH;
  camH = 2.5; wheelStep(true, false); w.camBack = camH;
  // The mode is put back: the PLANE checks come next, and a cube left behind
  // led them into the wrong branch - the orbit fell over on an uninitialised
  // q.
  drawIn = "plane";

  // Below the plane the wheel has to work THE SAME WAY. It used to turn the
  // signed height, and at -5.6 a step "away from you" led to -6.4, that is
  // farther from the surface. The word was plain: wherever I am, the wheel is
  // the same. TWO promises have to be guarded, not one. An injected fault -
  // "side = 1" - leaves the distance decreasing, and a check on the distance
  // alone lets it through, but the camera JUMPS to the other side of the
  // plane: from -8 to +7.1.
  let sym = true, sideKept = true;
  for (const h0 of [8, 3, 0.5, 0.05, -0.05, -0.5, -3, -8]) {
    camH = h0; stepHeight(1);  const f = camH;
    camH = h0; stepHeight(-1); const b = camH;
    if (!(Math.abs(f) < Math.abs(h0) && Math.abs(b) > Math.abs(h0))) sym = false;
    if (f * h0 < 0 || b * h0 < 0) sideKept = false;
  }
  camH = 0; stepHeight(1);
  const zeroStays = camH === 0;             // nothing is closer than the plane
  say("wheel_sym", sym);
  say("wheel_side", sideKept);
  say("wheel_zero", zeroStays);

  say("wheel_stand", w.standFwd < 2.5 && w.standBack > 2.5);
  say("wheel_region", w.regionFwd < 4 && w.regionBack > 4);
  say("wheel_camera", w.camFwd < 2.5 && w.camBack > 2.5);
  say("wheel_nums", "height " + w.standFwd.toFixed(3) + "/" + w.standBack.toFixed(3)
    + ", domain " + w.regionFwd.toFixed(3) + "/" + w.regionBack.toFixed(3)
    + ", distance " + w.camFwd.toFixed(3) + "/" + w.camBack.toFixed(3));
}

// --- DEGENERATE: a look along the plane, and zero height --------------------
{
  let finite = true;
  for (const st of [[0.0, 2.0], [1.5707, 2.0], [-1.5707, 2.0], [0.85, 0.0], [0.85, -2.0]]) {
    el = st[0]; camH = st[1]; az = 0.4; camX = 0; camY = 0;
    const ob = orbitPivot();
    drag = { pivot: ob.p, radius: ob.r, planeSide: (camH < 0 ? -1 : 1), az0: az, el0: el, x0: 0, y0: 0 };
    orbitDrag(150, -80);
    for (const v of [camX, camY, camH, az, el, ob.r])
      if (!Number.isFinite(v)) finite = false;
  }
  say("finite", finite);
}

console.log(JSON.stringify(out));
"""

src = "\n\n".join(func(n) for n in NEED)
js = HARNESS % src
tmp = os.path.join(HERE, "_camera_js.tmp.js")
with open(tmp, "w", encoding="utf-8") as f:
    f.write(js)
try:
    r = subprocess.run(["node", tmp], capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
finally:
    os.remove(tmp)

if r.returncode != 0:
    print(r.stderr.strip()[:2000])
    raise SystemExit("Node did not run")

res = dict(json.loads(r.stdout.strip().splitlines()[-1])["checks"])

LABEL = [
    ("turn_moved", "the turn moved the camera by"),
    ("turn_held", "the point taken left the cursor by"),
    ("orbit_radius", "the orbit radius drifted by"),
    ("orbit_aim", "the pivot left the ray by"),
    ("orbit_path", "the cursor path changed the view by"),
    ("sweep_tried", "views checked"),
    ("sweep_wrong", "gestures against the hand"),
    ("sweep_weak", "gestures with no noticeable travel"),
    ("sweep_detail", "by kind"),
    ("others_tried", "other gestures: views"),
    ("others_wrong", "other gestures against the hand"),
    ("others_detail", "by kind"),
    ("wheel_nums", "wheel away/towards"),
    ("wheel_stand", "wheel: height"),
    ("wheel_sym", "the wheel is symmetric across the sides"),
    ("wheel_side", "the side is kept"),
    ("wheel_zero", "at the plane the wheel stops"),
    ("wheel_region", "wheel: domain"),
    ("wheel_camera", "wheel: distance"),
    ("finite", "degenerate views are finite"),
]
for k, label in LABEL:
    if k not in res:
        raise SystemExit("the measurement %s did not come back from Node" % k)
    print("     %-40s %s" % (label, res[k]))

check("the turn does not move the camera", res["turn_moved"] == 0, True)
check("the point taken stays under the cursor", res["turn_held"] < 1e-9, True)
check("the orbit holds the radius", res["orbit_radius"] < 1e-9, True)
check("the orbit looks at the pivot", res["orbit_aim"] < 1e-12, True)
check("the orbit goes by position, not by path", res["orbit_path"] < 1e-12, True)
check("the sweep of views took place", res["sweep_tried"] >= 70, True)
check("not one gesture goes AGAINST the hand", res["sweep_wrong"], 0)
check("and the travel is noticeable where it has to be", res["sweep_weak"], 0)
check("the remaining gestures were swept too", res["others_tried"] >= 35, True)
check("and not one of them goes against the hand", res["others_wrong"], 0)
check("the wheel away from you lowers the camera", res["wheel_stand"], True)
check("the wheel is the same on both sides of the plane", res["wheel_sym"], True)
check("and it does not throw the camera to the other side", res["wheel_side"], True)
check("at the plane itself it gets no closer", res["wheel_zero"], True)
check("the wheel with Ctrl in the cube narrows the domain", res["wheel_region"], True)
check("the wheel in the cube brings the camera closer", res["wheel_camera"], True)
check("degenerate views are finite", res["finite"], True)

print("")
print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
sys.exit(1 if bad else 0)
