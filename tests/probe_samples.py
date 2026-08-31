"""The sample formulas on the page have to WORK in the library.

Why a separate probe. The page and the library speak different dialects right
up to the moment someone compares them. While the viewer carried its own parser
in JS, the samples were written in the names JS is used to - atan, log, pow,
mod - and some of them the library would not have accepted at all. The parser
is gone, but the list of samples is still text in the HTML, and nothing stops
anyone from writing whatever they like into it.

One broken sample in plain sight is worse than no samples at all: a person
presses a button, gets a refusal, and decides the library is broken. That is
exactly how one was caught, by hand: 'x mod 0.5' parsed but produced no finite
values, because mod in the Pascal parser is integer.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "python"))
import nashira3d

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
    text = f.read()

start = text.find("const SAMPLES = [")
check("the list of samples was found on the page", start >= 0, True)

rows = []
if start >= 0:
    block = text[start:text.index("];", start)]
    rows = re.findall(
        r'\{\s*n:"([^"]+)",\s*g:"([^"]+)",\s*z:([-\d.]+),\s*d:\[([^\]]+)\],\s*'
        r'f:"([^"]+)"\s*\}', block, re.S)

# An empty list would go through in silence and prove nothing: zero samples
# checked is not "all is well", it is "nothing was looked at".
check("more than five samples", len(rows) > 5, True)

# The families are declared in a separate list, and a sample assigned to a
# family that does not exist simply never reaches the gallery: it disappears in
# silence, and silence here is indistinguishable from "it was never there".
fams = set(re.findall(r'\["(\w+)",\s*"[^"]+"\]',
                      text[text.find("const SAMPLE_FAMILIES"):
                           text.find("];", text.find("const SAMPLE_FAMILIES"))]))
check("the families are declared", len(fams) > 0, True)
check("every sample is in a declared family",
      sorted({g for _, g, _, _, _ in rows} - fams), [])

s = nashira3d.Session(formula="x", quality=30)
for name, group, z, dom, formula in rows:
    try:
        box = [float(v) for v in dom.split(",")]
        s.formula = formula
        s.domain = (box[0], box[1], box[2], box[3])
        s.box = (1.0, 1.0, float(z))
        s.render(80, 60)
        check("the sample %s draws" % name, True, True)
    except Exception as e:
        check("the sample %s draws" % name, str(e)[:40], True)
s.close()

print("")
print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
for n in bad:
    print("   %s" % n)
sys.exit(1 if bad else 0)
