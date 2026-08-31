"""The infinite plane is FROZEN: the behaviour as it stands is the baseline.

The word was plain: in the across the view mode there is nothing to complain
about, and it must not be broken. Words alone are not enough. What is needed is
something that can be compared, or "I shall try not to break anything" is only
ever checked by a complaint - that is, after the breakage.

The baseline was taken BEFORE the cube was reworked: twenty starting cameras
(heights above and below the plane), five elevations including a near-horizon
one, ten trajectories, and wheel sequences on top of that. 3100 camera states
in all.

For the turn it is NOT THE ANGLES that are compared but the promise: the angle
between the world ray grabbed on the press and the ray under the cursor now.
Angles can reach the same view by different roads - whereas the promise made to
a person was about the ray.

A refusal on unreachability is counted SEPARATELY. The |s| <= 1 limit is a real
property of a model with no roll, and there the turn legitimately does not
happen at all. Mixing the two cases gave an invariant of 0.30 rad and nearly
meant deciding the promise was broken; separated, it is 3.3e-8 rad over 960
turns that happened and 40 refusals.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ok, bad = 0, []


def check(name, got, want):
    global ok
    if got == want:
        ok += 1
        print("  ok   %-52s %s" % (name, got))
    else:
        bad.append(name)
        print("  FAIL %-52s got %r, want %r" % (name, got, want))


try:
    r = subprocess.run(["node", os.path.join(HERE, "plane_baseline.js")],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
except FileNotFoundError:
    print("     Node was not found - the plane was NOT CHECKED")
    sys.exit(0)

line = [l for l in (r.stdout or "").strip().splitlines() if l.startswith("{")]
if r.returncode != 0 or not line:
    print("     " + (r.stderr or "").strip()[:300])
    check("the baseline was read and the comparison ran", False, True)
    print("")
    print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
    sys.exit(1)

d = json.loads(line[-1])
print("     states %s, differ %s, largest %s, invariant %s"
      % (d["states"], d["differ"], d["largestDifference"], d["turnInvariant"]))

check("the baseline is there and complete",
      d["inBaseline"] == d["states"] and d["states"] >= 3000, True)
check("the plane did not shift in a single state", d["differ"], 0)
# The promise of the turn: the ray under the cursor. The threshold is not a
# machine zero - the trigonometry goes through arcsine and arctangent - but
# 3e-8 rad is 4e-5 of a screen pixel.
check("the grabbed ray stays under the cursor",
      d["turnInvariant"] < 1e-6, True)
# The other side of it: if the turn had NOT happened at all, the invariant
# would also be small - because there would be nothing to measure. So the turns
# that did happen are counted too.
check("the turns really did happen", d["turnsDone"] > 500, True)
check("and the refusals on unreachability are still there",
      d["refusalsUnreachable"] > 0, True)

print("")
print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
sys.exit(1 if bad else 0)
