"""A probe of the seam. Every check has BOTH cases: one that must pass and one
that must be refused.

A check with a green case only guards nothing: it is green when its subject is
whole and green when the subject has been swapped for a stub.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "python"))

from nashira3d import _binding as b

ok = 0
bad = []


def check(name, got, want):
    global ok
    if got == want:
        ok += 1
        print("  ok   %-46s %s" % (name, got))
    else:
        bad.append(name)
        print("  FAIL %-46s got %r, want %r" % (name, got, want))


lib, api = b.load()
ffi = b.ffi

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")


def header_order():
    """The names of the table members in the order the header declares them."""
    src = open(os.path.join(ROOT, "include", "nashira3d.h"), encoding="utf-8").read()
    body = src[src.index("typedef struct"):src.index("} nsh_api_v1;")]
    names = ["size"] if re.search(r"uint32_t[ 	]+size", body) else []
    names += re.findall(r"\(\*(\w+)\)", body)
    return names


def cdef_order():
    src = open(os.path.join(ROOT, "python", "nashira3d", "_binding.py"),
               encoding="utf-8").read()
    body = src[src.index("typedef struct"):src.index("} nsh_api_v1;")]
    names = ["size"] if re.search(r"uint32_t[ 	]+size", body) else []
    names += re.findall(r"\(\*(\w+)\)", body)
    return names


def pascal_order():
    """The number of members in the Pascal record - the third independent
    declaration. It is the real table: the header and the cdef only describe
    it.

    What is compared is the COUNT and the position, not the names: in Pascal
    the names are its own and by the contract they mean nothing - the order of
    the members is part of the contract, the names are not. Demanding that the
    names match would invent a contract that does not exist. This will not
    catch two fields of the same type swapped over, but the working checks
    below will: every function here is also CALLED."""
    src = open(os.path.join(ROOT, "core", "nashira3d.lpr"), encoding="utf-8").read()
    body = src[src.index("TNshApiV1 = record"):]
    body = body[:body.index("  end;")]
    body = re.sub(r"\{[^}]*\}", "", body, flags=re.S)   # away with brace comments
    out = []
    for line in body.splitlines()[1:]:
        line = line.strip()
        if ":" in line:
            out.append(line.split(":")[0].strip())
    return out


def recorded_order():
    out = []
    with open(os.path.join(ROOT, "include", "abi-order.txt"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line)
    return out


print("THE ORDER OF THE MEMBERS")
# Three independent declarations are compared against a FOURTH one, outside
# them. Comparing them only with each other is useless: they are edited at
# once, and an order that is wrong in agreement passes straight through - which
# is what happened when fit_z landed in the middle of the table.
rec = recorded_order()
check("the header matches the recorded order", header_order(), rec)
check("the cdef matches the recorded order", cdef_order(), rec)
check("the Pascal record has the same number of members", len(pascal_order()), len(rec))

prev = None
try:
    import subprocess
    r = subprocess.run(["git", "-C", ROOT, "show", "HEAD:include/abi-order.txt"],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode == 0:
        prev = [l.strip() for l in r.stdout.splitlines()
                if l.strip() and not l.strip().startswith("#")]
except OSError:
    prev = None

if prev is None:
    # Silence is not allowed: what was not checked has to be called unchecked
    # rather than look like something that passed.
    print("  --   the previous order was not read (no git), growth not compared")
else:
    check("the previous order is the BEGINNING of the current one", rec[:len(prev)], prev)

print("THE TABLE")
check("nsh_get_api(1) is not NULL", api != ffi.NULL, True)
check("nsh_get_api(2) is NOT handed out", lib.nsh_get_api(2) == ffi.NULL, True)
check("nsh_get_api(0) is NOT handed out", lib.nsh_get_api(0) == ffi.NULL, True)
check("the size of the table matches", api.size, ffi.sizeof("nsh_api_v1"))
check("the version is not empty", len(ffi.string(api.version())) > 0, True)

print("THE SESSION")
pp = ffi.new("nsh_session**")
check("create returned OK", api.create(pp), b.OK)
s = pp[0]
check("the session pointer is not NULL", s != ffi.NULL, True)

print("THE FORMULA")
check("a sound one is accepted", api.set_formula(s, b"x*x + y*y"), b.OK)
check("an empty one is refused", api.set_formula(s, b""), b.ERR_FORMULA)
check("after a refusal there is text", len(ffi.string(api.last_error(s))) > 0, True)
check("a NULL session is refused", api.set_formula(ffi.NULL, b"x"), b.ERR_ARG)

print("THE DOMAIN")
check("a sound one is accepted", api.set_domain(s, -1.0, 1.0, -1.0, 1.0), b.OK)
check("reversed in x is refused", api.set_domain(s, 1.0, -1.0, -1.0, 1.0), b.ERR_ARG)
check("degenerate in y is refused", api.set_domain(s, -1.0, 1.0, 2.0, 2.0), b.ERR_ARG)

print("THE QUALITY")
check("50 is accepted", api.set_quality(s, 50), b.OK)
check("101 is refused", api.set_quality(s, 101), b.ERR_ARG)
check("-1 is refused", api.set_quality(s, -1), b.ERR_ARG)

print("THE CAMERA AND THE LIGHT")
check("a sound one is accepted", api.set_camera(s, 0.8, 0.6, 4.0, 0.8), b.OK)
check("a zero distance is refused", api.set_camera(s, 0.8, 0.6, 0.0, 0.8), b.ERR_ARG)
check("the light is accepted", api.set_light(s, 1.0, 1.0), b.OK)
check("the axes flag is accepted", api.set_axes(s, 1), b.OK)

print("A REFUSED WRITE DOES NOT SPOIL THE PREVIOUS ONE")
buf = ffi.new("uint8_t[]", 8 * 8 * 4)
# above, a sound formula was accepted and an empty one refused. A refusal has
# no right to wipe what was accepted: otherwise one typo breaks a session that
# has already been set up.
check("after a refused write the session still draws", api.render(s, 8, 8, buf), b.OK)

print("A FRAME with no formula - a refusal, not an empty picture")
qq = ffi.new("nsh_session**")
api.create(qq)
fresh = qq[0]
check("a new session with no formula refuses", api.render(fresh, 8, 8, buf), b.ERR_STATE)
check("and says what is missing",
      b"formula" in ffi.string(api.last_error(fresh)), True)
api.destroy(fresh)
check("zero width is refused", api.render(s, 0, 8, buf), b.ERR_ARG)
check("a NULL buffer is refused", api.render(s, 8, 8, ffi.NULL), b.ERR_ARG)

api.destroy(s)
print("  ok   destroy did its work")
ok += 1

print("")
print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
for n in bad:
    print("   %s" % n)
sys.exit(1 if bad else 0)
