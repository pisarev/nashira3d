// THE CUBE ORBIT CONTRACT - checked by the measurements the review named.
// The measurements below are the contract: there is no other copy of it.
const fs = require("fs");
const page = fs.readFileSync(__dirname + "/../web/preview.html", "utf8");
function func(n) {
  const s0 = page.indexOf("function " + n + "(");
  let i = page.indexOf("{", s0), d = 0, j = i;
  for (; j < page.length; j++) { if (page[j] === "{") d++; else if (page[j] === "}") { d--; if (!d) break; } }
  return page.slice(s0, j + 1);
}
let az = 0.9, el = 0.85, camX = 0, camY = 0, camH = 2.5, fov = 0.9, drawIn = "cube";
let dom = [-1, 1, -1, 1], declDom = [-1, 1, -1, 1], cubeFocus = null;
let drag = null, coreDirty = false;
// Constants of the page that the extracted functions do not carry. They are
// taken FROM THE SOURCE rather than copied here as a number: a private copy
// would drift apart at the first edit.
const ORBIT_EL_LIMIT = (() => {
  const m = /const ORBIT_EL_LIMIT = \(([\d.]+) \* Math\.PI\) \/ 180;/.exec(page);
  if (!m) throw new Error("ORBIT_EL_LIMIT was not found on the page");
  return (parseFloat(m[1]) * Math.PI) / 180;
})();
const view = { clientWidth: 1912, clientHeight: 940 };
const $ = () => ({ set textContent(v) {}, get value() { return "0.3"; } });
function flash() {}
function tiltStand(v) { const l = Math.PI/2 - 1e-3; return Math.max(-l, Math.min(l, v)); }
eval(["camBasis", "screenScale", "rayWorld", "dirToScreen", "groundAt", "camQ",
      "camFromQ", "focusPoint", "cubeRadius", "orbitRate", "orbitClamp",
      "orbitDrag", "cubePan", "cubeDolly"].map(func).join("\n"));

const W = view.clientWidth, H = view.clientHeight;
function proj(P) {
  const v = [P[0]-camX, P[1]-camY, P[2]-camH];
  const L = Math.hypot(v[0],v[1],v[2]) || 1;
  const s = dirToScreen([v[0]/L,v[1]/L,v[2]/L], az, el);
  return s ? [s[0]*W/2, s[1]*H/2] : null;   // in screen pixels
}
function home() { az = 0.9; el = 0.85; camX = 0; camY = 0; camH = 2.5; cubeFocus = null; }
function press(sx, sy) {
  const P = focusPoint(), q = camQ(P);
  drag = { pivot: P, q: q, az0: az, el0: el, x0: 0, y0: 0,
           radius: Math.hypot(q[0],q[1],q[2]) };
}
const out = {};

// B. THE PIVOT DOES NOT MOVE ON THE SCREEN. 1000 random drags.
let seed = 12345;
const rnd = () => { seed = (seed*1103515245 + 12345) & 0x3fffffff; return seed/0x40000000; };
let worstPivot = 0;
for (let i = 0; i < 1000; i++) {
  home();
  az = rnd()*6.28; el = (rnd()-0.5)*2.6; camH = 0.5 + rnd()*6;
  camX = (rnd()-0.5)*4; camY = (rnd()-0.5)*4;
  const P = focusPoint();
  const before = proj(P);
  press();
  if (drag.q[0] <= 0.002) continue;            // pivot not ahead - no gesture starts
  orbitDrag((rnd()-0.5)*1600, (rnd()-0.5)*800);
  const after = proj(P);
  if (before && after) worstPivot = Math.max(worstPivot, Math.hypot(after[0]-before[0], after[1]-before[1]));
}
out.pivotDriftPx = worstPivot;

// C. THE RADIUS DOES NOT DRIFT.
let worstR = 0;
for (let i = 0; i < 200; i++) {
  home(); az = rnd()*6.28; el = (rnd()-0.5)*2.4; camH = 0.5 + rnd()*5;
  const P = focusPoint();
  const r0 = Math.hypot(P[0]-camX, P[1]-camY, P[2]-camH);
  press();
  if (drag.q[0] <= 0.002) continue;
  orbitDrag((rnd()-0.5)*1200, (rnd()-0.5)*600);
  const r1 = Math.hypot(P[0]-camX, P[1]-camY, P[2]-camH);
  worstR = Math.max(worstR, Math.abs(r1-r0)/r0);
}
out.radiusDrift = worstR;

// D. NO HIDDEN SIDE: the sign of the azimuth increment is the same above and
// below. BOTH axes have to be guarded. At first only the azimuth stood here,
// and a fault injected into the elevation - "side put back" - went straight
// through: the check was looking the wrong way.
const signs = [], signsY = [];
for (const e0 of [0.52, 0.017, -0.017, -0.52]) {
  home(); el = e0; camH = e0 > 0 ? 2.5 : -2.5;
  press();
  const a0 = az; orbitDrag(100, 0);
  signs.push(Math.sign(az - a0));
  home(); el = e0; camH = e0 > 0 ? 2.5 : -2.5;
  press();
  const b0 = el; orbitDrag(0, 100);
  signsY.push(Math.sign(el - b0));
}
out.sideSigns = signs.join(",");
out.sideSignsY = signsY.join(",");

// E. ISOTROPY: 100 pixels diagonally give the same amount of control.
home(); press(); let a0 = az, e0 = el;
orbitDrag(100, 0); const dHor = Math.hypot(az-a0, el-e0);
home(); press(); a0 = az; e0 = el;
orbitDrag(0, 100); const dVer = Math.hypot(az-a0, el-e0);
home(); press(); a0 = az; e0 = el;
orbitDrag(100/Math.SQRT2, 100/Math.SQRT2); const dDia = Math.hypot(az-a0, el-e0);
out.isotropy = { hor: +dHor.toFixed(9), ver: +dVer.toFixed(9), dia: +dDia.toFixed(9) };

// The rate: how many degrees across the short side of the frame.
home(); press(); a0 = az; orbitDrag(H, 0);
out.degPerShortSide = Math.abs((az - a0) * 180 / Math.PI);

// F. THE WHEEL: the screen place of the focus does not change, and there and
//    back brings the camera home.
home();
const P = focusPoint();
let wheelDrift = 0;
const b0 = proj(P);
for (let i = 0; i < 8; i++) { cubeDolly(false); const b = proj(P);
  if (b0 && b) wheelDrift = Math.max(wheelDrift, Math.hypot(b[0]-b0[0], b[1]-b0[1])); }
const midCam = [camX, camY, camH];
for (let i = 0; i < 8; i++) cubeDolly(true);
out.wheelFocusDriftPx = wheelDrift;
home(); const c0 = [camX, camY, camH];
for (let i = 0; i < 8; i++) cubeDolly(false);
for (let i = 0; i < 8; i++) cubeDolly(true);
out.wheelRoundTrip = Math.hypot(camX-c0[0], camY-c0[1], camH-c0[2]);

// G. THE ELEVATION CLAMP: 89.5 degrees, no more.
home(); press(); orbitDrag(0, 100000);
out.elMaxDeg = Math.abs(el * 180 / Math.PI);
home(); press(); orbitDrag(0, -100000);
out.elMinDeg = -Math.abs(el * 180 / Math.PI);

// H. ORBIT IS NOT MOVE: in an orbit the pivot stands still and the orientation
//    changes; in a move the orientation stays put.
home(); press(); const or0 = [az, el]; const pb = proj(P);
orbitDrag(150, 80);
const orbitTurned = Math.hypot(az-or0[0], el-or0[1]) > 1e-6;
const pa = proj(P);
const orbitPivotFixed = pb && pa && Math.hypot(pa[0]-pb[0], pa[1]-pb[1]) < 0.01;
home(); const mv0 = [az, el]; const mb = proj(P);
cubePan(150, 80);
const moveKeptOrientation = Math.hypot(az-mv0[0], el-mv0[1]) < 1e-12;
const ma = proj(P);
const moveMovedPivot = mb && ma && Math.hypot(ma[0]-mb[0], ma[1]-mb[1]) > 50;
out.orbitTurned = orbitTurned;
out.orbitPivotFixed = orbitPivotFixed;
out.moveKeptOrientation = moveKeptOrientation;
out.moveMovedPivot = moveMovedPivot;

// I. THE MOVE FOLLOWS THE HAND: a point grabbed at the depth of the object
//    follows the mouse.
home();
const Q = focusPoint();
const q0 = proj(Q);
cubePan(200, -100);
const q1 = proj(Q);
out.movePivotFollow = (q0 && q1) ? [+(q1[0]-q0[0]).toFixed(1), +(q1[1]-q0[1]).toFixed(1)] : null;

console.log(JSON.stringify(out, null, 1));
