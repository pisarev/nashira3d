// THE BASELINE OF THE PLANE AS IT IS. Taken BEFORE the cube was reworked and
// compared against AFTER.
//
// The word was plain: in the across the view mode there is nothing to complain
// about, and it must not be broken. Words alone are not enough here - what is
// needed is something that can be compared. The review asked for the same and
// named the contents: twenty starting cameras, heights above and below the
// plane, five elevations including a near-horizon one, ten trajectories, and
// sequences of the wheel and of the move.
//
// For the turn it is NOT THE ANGLES that are compared but an invariant: the
// angle between the world ray grabbed on the press and the ray under the
// cursor now. Angles can reach the same view by different roads; the invariant
// is the very promise that was made to a person.
const fs = require("fs");
const page = fs.readFileSync(__dirname + "/../web/preview.html", "utf8");
function func(n) {
  const s0 = page.indexOf("function " + n + "(");
  let i = page.indexOf("{", s0), d = 0, j = i;
  for (; j < page.length; j++) { if (page[j] === "{") d++; else if (page[j] === "}") { d--; if (!d) break; } }
  return page.slice(s0, j + 1);
}
let az = 0, el = 0, camX = 0, camY = 0, camH = 0, fov = 0.9, drawIn = "plane";
let dom = [-2, 2, -2, 2], declDom = [-2, 2, -2, 2];
let drag = null;
const H_SOFT = 0.09, H_LIMIT = 1e5, HORIZON = 8, MIN_SIN = 1 / HORIZON;
const view = { clientWidth: 1200, clientHeight: 700 };
const $ = () => ({ set textContent(v) {}, get value() { return "0.9"; } });
const domainNow = () => dom.slice();
function showDomain() {}
function setDomain(a, b, c, d) { dom = [a, b, c, d]; }
eval(["camBasis", "screenScale", "rayWorld", "dirToScreen", "turnTo", "tiltStand",
      "orbitPivot", "orbitPlace", "orbitDrag", "panTarget", "turnFallback",
      "stepHeight", "panDomain", "zoomDomain", "wheelStep"].map(func).join("\n"));

function put(s) { az = s[0]; el = s[1]; camX = s[2]; camY = s[3]; camH = s[4]; }
function state() { return [az, el, camX, camY, camH].map(v => +v.toFixed(12)); }
function ang(a, b) {
  const d = Math.max(-1, Math.min(1, a[0]*b[0] + a[1]*b[1] + a[2]*b[2]));
  return Math.acos(d);
}

const CAMS = [];
for (const a of [0, 1.2, 2.4, 3.6, 4.8]) for (const h of [2.5, -2.5])
  for (const e of [0.12, 0.9]) CAMS.push([a, Math.sign(h) * e, 0.4, -0.7, h]);
const ELS = [0.12, 0.35, 0.6, 0.9, 1.3];
const TRAJ = [[150,0],[-150,0],[0,120],[0,-120],[120,90],[-90,140],
              [200,-60],[-40,-180],[300,30],[-260,-25]];

const out = { turnInvariant: 0, turnDone: 0, turnRefused: 0, states: [] };
for (const c of CAMS) {
  for (const e of ELS) {
    const base = [c[0], Math.sign(c[4]) * e, c[2], c[3], c[4]];
    for (const t of TRAJ) {
      // TURN: grab the ray and check the promise
      put(base);
      const sx0 = -0.3, sy0 = 0.2;
      const grab = rayWorld(sx0, sy0, az, el);
      const sx1 = sx0 + 2 * t[0] / view.clientWidth;
      const sy1 = sy0 - 2 * t[1] / view.clientHeight;
      const was = state();
      turnTo(grab, sx1, sy1);
      const moved = state().some((v, i) => v !== was[i]);
      if (moved) {
        // The promise is checked ONLY where the turn actually happened. A
        // refusal on unreachability is a legitimate property of a model with
        // no roll: not every world direction can be placed at every point of
        // the screen, and turnTo then does not move the camera at all. Mixing
        // the two cases gave an invariant of 0.30 rad and would have meant
        // deciding the promise was broken.
        const now = rayWorld(sx1, sy1, az, el);
        out.turnInvariant = Math.max(out.turnInvariant, ang(grab, now));
        out.turnDone++;
      } else out.turnRefused++;
      out.states.push(["turn", ...state()]);
      // ORBIT
      put(base);
      const ob = orbitPivot();
      drag = { pivot: ob.p, radius: ob.r, az0: az, el0: el, x0: 0, y0: 0 };
      orbitDrag(t[0], t[1]);
      out.states.push(["orbit", ...state()]);
      // MOVE
      put(base); panTarget(t[0], t[1]);
      out.states.push(["move", ...state()]);
    }
    // WHEEL: a forwards-and-back sequence
    put(base);
    // The sequence is ASYMMETRIC on purpose. At first it was [1,1,1,-1,-1,
    // 1,-1,-1,-1,1] - zero in total - and the asinh step is reversible:
    // forwards and back cancel exactly. The baseline then did not check the
    // wheel AT ALL, and an injected fault - "a step of 0.12 instead of 0.1201"
    // - went straight past. The total here is +4.
    for (const d of [1,1,1,-1,1,1,-1,1,1,1]) stepHeight(d);
    out.states.push(["wheel", ...state()]);
  }
}
// Taking the baseline is a SEPARATE action, behind an explicit --write
// argument. Without it the comparison would quietly overwrite the baseline
// with itself and would always be green: such a check is not a guard but a
// mirror.
const json = JSON.stringify(out);
const file = __dirname + "/plane_baseline.json";
const write = process.argv.includes("--write");
if (write) {
  fs.writeFileSync(file, json);
  console.log(JSON.stringify({ written: out.states.length,
    turnsDone: out.turnDone, refusals: out.turnRefused,
    invariant: out.turnInvariant }));
} else {
  if (!fs.existsSync(file)) {
    console.log(JSON.stringify({ error: "no baseline, take one with --write" }));
    process.exit(2);
  }
  const was = JSON.parse(fs.readFileSync(file, "utf8"));
  let diff = 0, worst = 0, where = "";
  const n = Math.min(was.states.length, out.states.length);
  for (let i = 0; i < n; i++) {
    const a = was.states[i], b = out.states[i];
    if (a[0] !== b[0]) { diff++; continue; }
    for (let k = 1; k < a.length; k++) {
      const d = Math.abs(a[k] - b[k]);
      if (d > 1e-12) { diff++; if (d > worst) { worst = d; where = a[0] + " #" + i; } break; }
    }
  }
  console.log(JSON.stringify({
    states: out.states.length,
    inBaseline: was.states.length,
    differ: diff,
    largestDifference: worst,
    where: where,
    turnInvariant: out.turnInvariant,
    turnsDone: out.turnDone,
    refusalsUnreachable: out.turnRefused
  }));
}
