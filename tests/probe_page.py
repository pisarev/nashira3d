"""Every function the page CALLS has to be declared somewhere.

The reason. While blocks in preview.html were being rearranged, the function
wantPan disappeared and two calls to it stayed. The syntax was flawless, node
--check said nothing, the battery was green - and on the page EVERY movement of
the mouse threw: dragging did not work at all. It was found only by reading the
browser console by hand.

The parsing here is crude - by pattern, without a real JS parse. That is enough
for the trouble the probe was made for: there is a call, there is no
declaration. It does not catch the subtleties of scope and does not pretend to.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "..", "web", "preview.html")

ok, bad = 0, []


def check(name, got, want):
    global ok
    if got == want:
        ok += 1
        print("  ok   %-46s %s" % (name, got))
    else:
        bad.append(name)
        print("  FAIL %-46s got %r, want %r" % (name, got, want))


with open(PAGE, encoding="utf-8") as f:
    page = f.read()

i = page.find("<script>")
j = page.rfind("</script>")
check("the script was found on the page", i >= 0 and j > i, True)
src = page[i + 8:j]

# Strings and comments are thrown out: inside them "name(" means nothing.
clean = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
clean = re.sub(r"//[^\n]*", " ", clean)
# The string and template patterns are built THROUGH chr(92): in this
# environment a backslash collapses on the way to Python, and a pattern with
# [^`\\] turned into an unclosed character class. Caught at once - the probe
# would not start at all.
BS = chr(92)
clean = re.sub("`(?:" + BS*2 + ".|[^`" + BS*2 + "])*`", '""', clean, flags=re.S)
clean = re.sub("'(?:" + BS*2 + ".|[^'" + BS*2 + BS + "n])*'", '\"\"', clean)
clean = re.sub('"(?:' + BS*2 + '.|[^"' + BS*2 + BS + 'n])*"', '""', clean)

declared = set()
declared |= set(re.findall(r"\bfunction\s+([A-Za-z_$][\w$]*)", clean))
declared |= set(re.findall(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)", clean))
# parsing by pattern: const [a, b] = ...  and  (a, b) => ...
for grp in re.findall(r"\b(?:const|let|var)\s*\[([^\]]*)\]", clean):
    declared |= {n.strip() for n in grp.split(",") if n.strip()}
for grp in re.findall(r"\(([^()]*)\)\s*=>", clean):
    declared |= {n.strip().split("=")[0].strip() for n in grp.split(",") if n.strip()}
declared |= set(re.findall(r"([A-Za-z_$][\w$]*)\s*=>", clean))
for grp in re.findall(r"\bfunction\s*[A-Za-z_$\w$]*\s*\(([^()]*)\)", clean):
    declared |= {n.strip() for n in grp.split(",") if n.strip()}
declared |= set(re.findall(r"\bcatch\s*\(\s*([A-Za-z_$][\w$]*)", clean))
declared |= set(re.findall(r"\bfor\s*\(\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)", clean))

KNOWN = {
    # words of the language that fit the "name(" pattern
    "if", "for", "while", "switch", "catch", "return", "typeof", "function",
    "new", "do", "else", "await", "in", "of", "case", "delete", "void", "throw",
    # built-in and browser names
    "Math", "JSON", "Number", "String", "Array", "Object", "Boolean", "Set", "Map",
    "parseFloat", "parseInt", "isNaN", "isFinite", "Error", "Promise", "fetch",
    "setTimeout", "clearTimeout", "requestAnimationFrame", "addEventListener",
    "encodeURIComponent", "decodeURIComponent", "Uint8ClampedArray", "Uint8Array",
    "Float32Array", "Float64Array", "Uint32Array", "ImageData", "PointerEvent",
    "WheelEvent", "getComputedStyle", "Symbol", "RegExp", "Date",
    "AbortController",
}

called = set()
for m in re.finditer(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(", clean):
    called.add(m.group(1))

missing = sorted(called - declared - KNOWN)
if missing:
    print("     called but not declared: %s" % ", ".join(missing))
check("every function called is declared", missing, [])

# --- HIGHLIGHTING THE CHOSEN SAMPLE ------------------------------------------
# This is a check of the WIRING, not of the behaviour: the page is not run
# here. The behaviour itself was checked in a browser - choosing a sample,
# editing the formula by hand, spaces inside the formula. What is guarded here
# is that the wiring is in place: lose any one of the three calls and the
# highlight quietly stops updating, and that shows statically.

check("the samples have a chosen style", ".chip.on{" in page, True)
check("the highlight does not merge with hover", ".chip.on:hover{" in page, True)
check("a sample carries its formula in the markup", "dataset.formula" in src, True)
check("the highlight is worked out by comparing without spaces",
      "replace(/" in src and "syncPicks" in src, True)
check("the highlight updates when the formula is edited by hand",
      'addEventListener("input", syncPicks)' in src, True)
check("at least three calls to syncPicks: choice, edit, load",
      src.count("syncPicks(") >= 3, True)

# --- THE MODE IS GIVEN BY NAME, NOT BY A FLAG --------------------------------
# The reason: there came to be three modes, while two calls still passed a
# boolean - setNav(true) on load and setNav(!navDomain) on a key. There are two
# modes now, and the check stays: the mistake "an argument of the wrong type"
# does not depend on how many modes there are. Both quietly set a nameless
# mode, and the page opened in the wrong one. That mistake is invisible along
# any reference: the function is declared, the call is there, the argument is
# of another type.

import re as _re

# The text WITHOUT comments is parsed: otherwise the probe catches its own
# explanation, where that very wrong call is quoted as the reason.
_calls = _re.findall(r"setDrawIn\(([^)]*)\)", clean)
_bad = [c for c in _calls if c.strip() in ("true", "false") or "!" in c]
if _bad:
    print("     boolean argument to setDrawIn: %s" % ", ".join(_bad))
check("the drawing mode is given by name everywhere", _bad, [])
# The names are looked for in the ORIGINAL text: in the cleaned one the strings
# have already been thrown out, and setDrawIn("cube") looks there like
# setDrawIn(""). Strings inside comments do not affect this - a comment
# declares no name.
#
# There are TWO modes now instead of three. The earlier height, region and
# camera overlapped: camera is the cube, height is the plane, and region is the
# same plane with the domain led by navigation. Three overlapping models were
# exactly what had to go.
check("there are exactly two modes and both are set", sorted(set(
    _re.findall(r'setDrawIn\("(\w+)"\)', src))), ["cube", "plane"])
check("the earlier three-position switch is gone",
      any(('id="%s"' % i) in page for i in ("nStand", "nDomain", "nCamera")), False)

# --- STATE IS NOT OVERWRITTEN BY SOMEONE WHO KNOWS NOTHING ABOUT IT ----------
# The reason: setDrawIn (setNav at the time) stood INSIDE the frame fetch and
# fired on every frame. The mode button held until the first movement of the
# mouse and then went back. The defect was neither in the button nor in the
# handler - both were sound - but in who touches the state and when. Such a
# thing is invisible along any reference: the call is legitimate, the function
# exists.

def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", " ", text)


def handler_body(marker):
    """The body of a handler, found by the beginning of its text.

    It is looked for in the ORIGINAL text: in the cleaned one the string
    literals have already been thrown out, and addEventListener("wheel" looks
    there like addEventListener("". Comments are stripped from the piece found
    separately - otherwise the probe catches its own explanation, where the
    wrong call is quoted as the reason."""
    i = src.index(marker)
    depth, j, started = 0, i, False
    while j < len(src):
        if src[j] == "{":
            depth += 1
            started = True
        elif src[j] == "}":
            depth -= 1
            if started and depth == 0:
                return strip_comments(src[i:j + 1])
        j += 1
    return strip_comments(src[i:])


def body_of(name):
    """The body of a function by name: from the header to the line where the
    brace closed."""
    return handler_body("function %s(" % name)


_fetch = body_of("coreFetch")
check("the frame fetch does not touch the navigation mode",
      "setNav(" in _fetch, False)
check("the frame fetch does not touch the sample highlight",
      "syncPicks(" in _fetch, False)

# --- THE BRIDGE PARSES -------------------------------------------------------
# The reason: a line landed between an if branch and its else, and the bridge
# stopped starting at all. It was noticed only by a failed connection - that
# is, two commands and a restart later. Parsing costs milliseconds and catches
# it at once.

import ast as _ast

_bridge = os.path.join(HERE, "..", "web", "bridge.py")
try:
    _ast.parse(open(_bridge, encoding="utf-8").read())
    _ok_parse, _why = True, "parses"
except SyntaxError as e:
    _ok_parse, _why = False, "line %s: %s" % (e.lineno, e.msg)
check("the bridge parses as Python", _why, "parses")

# --- GESTURES BRANCH BY MODE, NOT BY AN OLD FLAG -----------------------------
# The reason, as it was reported: the wheel is "as it was". The wheel handler
# branched on navDomain - a flag for TWO modes - while there had come to be
# three. For a standing point navDomain is false, and the wheel went into the
# branch for orbit DISTANCE, which that camera does not have: the height did
# not change, the picture did not change.
#
# The check at the time called zoomDomain directly and noticed nothing: the
# function was checked, not the path the mouse takes. Hence the rule - every
# gesture handler has to know about the mode.

_wheel = handler_body('addEventListener("wheel"')
# The wheel handler now only calls wheelStep - the branching moved in there so
# that a check could CALL the gesture rather than rewrite it for itself. Both
# are checked: the handler calls, and the branching lives in the function.
check("the wheel calls its own step", "wheelStep(" in _wheel, True)
# The wheel now branches on a DIFFERENT question. There is one camera for both
# modes, and in both the wheel means one thing - the distance to the surface.
# It branches only into the second model under Ctrl, which only a declared
# domain has.
check("the wheel branches into the second model",
      "drawIn" in body_of("wheelStep"), True)
check("and it no longer branches on the camera",
      "navMode" in body_of("wheelStep"), False)

_keys = handler_body('addEventListener("keydown"')
check("the arrows do not call panDomain directly", "panDomain(" in _keys, False)

_move = handler_body('addEventListener("pointermove"')
# Dragging used to branch on the KIND OF CAMERA, and for an orbit one "turn on
# the spot" could not be expressed at all: Turn and Orbit in the cube did the
# same thing, and the button lied. There is one camera now, so there is nothing
# to branch on - one gesture for both drawing modes.
check("dragging does not branch on the kind of camera", "navMode" in _move, False)
check("and branches only on the gesture itself",
      ("wantPan" in _move) and ("wantOrbit" in _move), True)

# A tilt has to change ONLY the direction. The page used to keep a target and
# derive the standing point from it - the perpendicular held, while along the
# straight line the camera came four times closer to the surface and more as it
# turned. That was reported plainly. Now the mouse-move handler has no business
# with the height or the standing point: only the wheel and only the move touch
# them, each by its own function.
check("the tilt does not touch the height", "camH" in _move, False)
check("the tilt does not touch the standing point",
      ("camX" in _move) or ("camY" in _move), False)

# The other side of the same contract: the wheel touches NOTHING but the
# height, and the move nothing but the standing point. Checked both by gestures
# on the live page and here by the text: a gesture reaching into a field that
# is not its own would drift away from the model in silence.
check("the wheel does not touch the standing point",
      ("camX" in _wheel) or ("camY" in _wheel), False)
# The domain fields in standing-point mode are not dead input. The domain
# cannot be assigned there, the core will recompute it from the camera anyway
# and what was typed would quietly vanish; and the hint promises "type exact
# numbers when you need them". So what is typed is taken to mean "show me this
# domain".
_rd = body_of("readDomain")
check("typing a domain in height mode does not vanish",
      "frameDomain(" in _rd, True)

_pant = body_of("panTarget")
check("the move does not touch the height", "camH =" in _pant, False)
check("the move does not touch the angles",
      ("az =" in _pant) or ("el =" in _pant), False)

# --- THE DECLARED DOMAIN IS NOT TAKEN FROM THE CORE'S ANSWER -----------------
# The reason, found in use: the formula was wrapped in brackets, changing
# nothing mathematically, and the plane turned into a narrow cone.
#
# The cause: in height mode the core WORKS OUT the domain, the page puts it in
# the fields - and sent that same value back as the declared domain. The
# reference scale comes from the domain, the thickness of the slab from that,
# and the domain from the thickness. The loop, broken in the core, closed
# through the page. Measured through the bridge: over five changes of formula
# in a row the half-width went 14.5, 37.7, 77.2, 144.7, 260.1; after the fix,
# 14.54 all five times.

_q = body_of("coreQuery")
check("the DECLARED domain goes into the request", "declDom[0]" in _q, True)
check("and not the readout", '"&x0=" + dom[0]' in _q, False)

_fetch2 = body_of("coreFetch")
check("the readout does not touch the declared domain",
      "declDom" in _fetch2, False)

check("only a person and a sample change the declared domain",
      src.count("declDom =") >= 3, True)

# --- HOW THE RELIEF IS SHOWN -------------------------------------------------
# The switch has to be on the page, reach the core, and stand on contour lines
# when the page is first opened. That is what was asked for: lines by default,
# colour stays a setting.

# The buttons are looked for in the MARKUP, not in the script: src is only the
# body of <script>, and a check against it would pass on any page where the
# buttons do not exist at all.
check("there are three positions on the page", all(
    ('id="%s"' % i) in page for i in ("sLines", "sColor", "sBoth")), True)
check("the value goes into the request",
      '"&shade=" + shade' in body_of("coreQuery"), True)
check("the default is contour lines", 'let shade = "contours"' in src, True)
check("and the same is set at start-up", 'setShade("contours")' in src, True)

# Changing the shading does NOT rebuild the mesh - otherwise the page would ask
# the core to build the surface again for the sake of colouring. That is
# checked by there being only a request for a frame in the handler.
_sh = body_of("setShade")
check("changing the shading asks for a frame", "coreDirty = true" in _sh, True)
check("and does not touch the domain", "declDom" in _sh, False)

# --- WHAT THE LEFT BUTTON DOES -----------------------------------------------
# Three positions, not two. The earlier first one was called Orbit although it
# was not an orbit: the camera stands still and turns its head. Now Turn is a
# turn, Orbit is a real orbit around a sphere, and Move is a move.

check("the button has three positions", all(
    ('id="%s"' % i) in page for i in ("mTurn", "mOrbit", "mPan")), True)
check("the default is turn", 'mouseDoes = "turn"' in src
      and 'setMode("turn")' in src, True)
check("the orbit is also reachable through alt",
      "altKey" in body_of("wantOrbit"), True)

# An orbit moves the camera - that is its business. A turn does not, and that
# is guarded separately: one has a prohibition and the other a permission, and
# in a single handler they would take the guard off each other. The numbers for
# it are checked by probe_camera_js.
_ob = body_of("orbitDrag")
check("the orbit uses the pivot and radius taken on the press",
      "drag.pivot" in _ob and "drag.radius" in _ob, True)
check("and measures the angles from the press rather than accumulating",
      "drag.az0" in _ob and "drag.el0" in _ob, True)

# --- THE PAGE PARSES AT ALL --------------------------------------------------
# Every check above looks for substrings, and not one of them would notice if
# the script stopped being parsable: a typo in a bracket leaves every needed
# string in place while the page does not start at all and shows nothing. So
# the text of the script is handed to the Node parser - not run, only parsed.
import subprocess
import tempfile

_js = None
try:
    subprocess.run(["node", "--version"], capture_output=True, timeout=20)
    _js = True
except Exception:
    _js = False

if _js:
    fd, _tmp = tempfile.mkstemp(suffix=".js")
    os.close(fd)
    with open(_tmp, "w", encoding="utf-8") as _f:
        # new Function parses the body but does not run it
        _f.write("const s = require('fs').readFileSync(process.argv[2], 'utf8');" +
                 chr(10) + "new Function(s);" + chr(10))
    fd2, _page_js = tempfile.mkstemp(suffix=".pagesrc.js")
    os.close(fd2)
    with open(_page_js, "w", encoding="utf-8") as _f:
        _f.write(src)
    _r = subprocess.run(["node", _tmp, _page_js], capture_output=True,
                        text=True, encoding="utf-8", timeout=60)
    os.remove(_tmp)
    os.remove(_page_js)
    if _r.returncode != 0:
        print("     " + (_r.stderr or "").strip().splitlines()[0][:150])
    check("the page script parses", _r.returncode == 0, True)
else:
    print("     Node was not found - the script parse was NOT CHECKED")

print("")
print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
sys.exit(1 if bad else 0)
