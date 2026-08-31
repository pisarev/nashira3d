"""The page STARTS UP, rather than merely parsing.

The reason. A let declaration ended up BELOW the first call that reads it. Such
a script parses perfectly, every substring needed is in place, and every check
of the page was green - while in the browser the very first line of execution
fell over with "Cannot access before initialization" and the page showed
nothing. Only the browser caught it, by eye.

Here the same start-up is done without a browser: the page script is run in
Node with a stub environment. The stub answers anything and does nothing - the
subject of the check is not the behaviour but the plain fact that execution
reaches the end.

What the probe does NOT check, and does not pretend to check: how the picture
looks, whether frames arrive, whether the layout is right. Those are still
looked at by eye.
"""

import collections
import json
import os
import re
import subprocess
import sys
import tempfile

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
i, j = page.find("<script>"), page.rfind("</script>")
src = page[i + 8:j]

# A stub built on a proxy: it answers ANY access and serves as its own value.
# That way there is no need to list everything the page touches on start-up -
# and such a list would live a life of its own and fall behind.
STUB = r"""
const seen = { frames: 0, fetches: 0 };
function yes(name) {
  const f = function () { return yes(name + "()"); };
  f.__n = name;
  return new Proxy(f, {
    get(t, k) {
      if (k === Symbol.toPrimitive) return () => 0;
      if (k === "then") return undefined;            // do not pose as a promise
      if (k === "length") return 0;
      if (k === "toString") return () => name;
      if (k === "classList") return yes(name + ".classList");
      if (k === "style") return yes(name + ".style");
      if (k === "textContent" || k === "innerHTML" || k === "value")
        return stash[name + "." + String(k)] || "";
      if (k === "checked") return false;
      if (k === "clientWidth" || k === "width") return 900;
      if (k === "clientHeight" || k === "height") return 560;
      if (k === "getBoundingClientRect")
        return () => ({ left: 0, top: 0, width: 900, height: 560 });
      return yes(name + "." + String(k));
    },
    set(t, k, v) { stash[name + "." + String(k)] = v; return true; },
    apply() { return yes(name + "()"); },
    construct() { return yes("new " + name); },
    has() { return true; },
  });
}
const stash = {};
const document = yes("document");
const window = yes("window");
const navigator = yes("navigator");
const location = yes("location");
const devicePixelRatio = 1;
const performance = { now: () => 0 };
function requestAnimationFrame() { seen.frames++; return 1; }   // no call back
function addEventListener() {}
function fetch() { seen.fetches++; return new Promise(() => {}); }  // hangs forever
const Image = function () { return yes("Image"); };
const localStorage = yes("localStorage");
const alert = () => {};
"""

TAIL = ("\nlet boxFits = null, pivotScreen = null;"
  "try {"
  "  const P = focusPoint();"
  "  const hx = (declDom[1] - declDom[0]) / 2, hy = (declDom[3] - declDom[2]) / 2;"
  "  const hz = Math.max(1e-6, +($('bz').value) || 0.3) * Math.max(hx, hy);"
  "  const cx = (declDom[0] + declDom[1]) / 2, cy = (declDom[2] + declDom[3]) / 2;"
  "  const at = Q => { const d = [Q[0]-camX, Q[1]-camY, Q[2]-camH];"
  "    const L = Math.hypot(d[0], d[1], d[2]) || 1;"
  "    return dirToScreen([d[0]/L, d[1]/L, d[2]/L], az, el); };"
  "  const pts = [];"
  "  for (const sx of [-1,1]) for (const sy of [-1,1]) for (const sz of [-1,1])"
  "    pts.push([cx + sx*hx, cy + sy*hy, sz*hz]);"
  "  const pr = pts.map(at);"
  "  boxFits = pr.every(q => q && Math.abs(q[0]) <= 1 && Math.abs(q[1]) <= 1);"
  "  pivotScreen = at(P);"
  "} catch (e) { boxFits = String(e); }"
  "\nconsole.log(JSON.stringify({ ok: true, frames: seen.frames,"
  " fetches: seen.fetches, drawIn: drawIn, mouseCube: mouseCube,"
  " mousePlane: mousePlane, boxFits: boxFits, pivotScreen: pivotScreen }));\n")

fd, tmp = tempfile.mkstemp(suffix=".boot.js")
os.close(fd)
with open(tmp, "w", encoding="utf-8") as f:
    f.write(STUB + "\n" + src + TAIL)

try:
    r = subprocess.run(["node", tmp], capture_output=True, text=True,
                       encoding="utf-8", timeout=90)
finally:
    os.remove(tmp)

line = ""
for ln in (r.stdout or "").strip().splitlines():
    if ln.startswith("{"):
        line = ln
if r.returncode != 0 or not line:
    first = (r.stderr or "").strip().splitlines()
    for ln in first[:6]:
        print("     " + ln[:160])

check("the page script runs to the end", r.returncode == 0 and bool(line), True)

if line:
    got = json.loads(line)
    check("it reached the last line", got.get("ok"), True)
    # A frame is asked for through requestAnimationFrame; if it was never
    # asked for, execution broke off before the page came to life.
    check("the page asked for a first frame", got.get("frames", 0) >= 1, True)

    # THE REASON. In the markup of the bottom panel Turn was lit, while the
    # default for the cube was orbit. What disagrees here is not one letter
    # with another but two independent products: what a person sees before the
    # first line of the script, and what the script actually switches on. The
    # first frame of the page showed the wrong gesture.
    seg = page[page.find('id="pMode"'):]
    seg = seg[:seg.find('</div>', seg.find('id="mousehint"'))]
    lit = re.findall('<button id="(\\w+)"[^>]*class="on"', seg)
    BUTTON = {"dCube": "cube", "dPlane": "plane",
              "mTurn": "turn", "mOrbit": "orbit", "mPan": "move"}
    check("exactly two switches are lit in the markup", len(lit), 2)
    mode = [BUTTON.get(b) for b in lit if b.startswith("d")]
    gesture = [BUTTON.get(b) for b in lit if b.startswith("m")]
    check("the lit mode = the default in the code", mode, [got.get("drawIn")])
    want = got.get("mouseCube") if got.get("drawIn") == "cube" else got.get("mousePlane")
    check("the lit gesture = the default of that mode", gesture, [want])

    # THE REASON. Rebuilding the bottom panel replaced the markup up to the
    # FIRST </div>, and that was the closing tag of the first group, not of the
    # panel. The tail of the old markup stayed in the body of the page: a
    # second mousehint, a second views, and nine more buttons with the same
    # names. getElementById hands back whichever comes first, so the page
    # worked, the measurements looked only at elements with the panel class,
    # and nobody saw the leftover. A repeated name is a trait that shows
    # without running anything and cannot be explained by anything legitimate.
    body = re.sub('<(style|script)[^>]*>.*?</\\1>', "", page,
                  flags=re.S)
    names = re.findall('\\sid="([^"]+)"', body)
    repeats = sorted(k for k, v in collections.Counter(names).items() if v > 1)
    check("names inspected in the markup", len(names) > 30, True)
    check("there are no repeated names", repeats, [])

    # THE REASON. The cube is the default mode, while the initial camX, camY
    # and camH are the standing point of the PLANE. From there the box is not
    # visible in the cube: measured, its centre projected to -1.267 against a
    # visible band from -1 to 1, and only the top edge fell inside. The battery
    # did not catch this - the defect was visible only by eye, on the first
    # frame.
    check("at start-up the box fits entirely in the frame", got.get("boxFits"), True)
    pivot = got.get("pivotScreen") or [9, 9]
    check("at start-up the pivot is in the middle of the frame",
          [round(v, 6) for v in pivot[:2]], [0.0, 0.0])

print("")
print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
sys.exit(1 if bad else 0)
