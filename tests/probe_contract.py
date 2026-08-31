"""The contract between the header, the binding and the versions. A check of
TEXTS, not of pictures.

Why. The nsh_api_v1 table is described TWICE: in include/nashira3d.h for those
calling from C, and in python/nashira3d/_binding.py for cffi. A disagreement
here gives neither a build error nor a complaint: cffi simply works out the
offsets from its own description and goes off to call the wrong place. A
missing field shifts EVERY field after it.

_binding.py carried an honest line about this: for now it rests on attention.
Attention is not a check. This is a check.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "python"))

from nashira3d import _binding as b

ok, bad = 0, []


def check(name, got, want):
    global ok
    if got == want:
        ok += 1
        print("  ok   %-46s %s" % (name, got))
    else:
        bad.append(name)
        print("  FAIL %-46s" % name)
        print("       got:  %r" % (got,))
        print("       want: %r" % (want,))


MEMBER = re.compile(r"\(\s*\*\s*(\w+)\s*\)\s*\(([^;]*)\)\s*;")


KEYWORDS = {"int", "char", "double", "float", "void", "long", "short",
            "unsigned", "signed", "const"}


def strip_name(arg):
    """Drop the argument's NAME, keeping the type.

    In the header the arguments are named - "double x0" - while in the cdef
    there are no names, nor should there be: cffi does not need them. The first
    version of this probe compared the strings whole and went red on correct
    code. A check too strict about its subject catches its own fussiness rather
    than a defect.

    The name is dropped only if the last word is an ordinary identifier and is
    not one of the type words: otherwise "unsigned int" would lose its "int".
    """
    parts = arg.split()
    if len(parts) > 1 and re.fullmatch(r"[A-Za-z_]\w*", parts[-1]) and parts[-1] not in KEYWORDS:
        parts = parts[:-1]
    return " ".join(parts)


def members(text):
    """The names of the table fields and the types of their arguments, in
    order. RETURN types are not compared: nsh_status in the header and int in
    the cdef are the same number, and demanding a literal match would forbid
    cffi to do without the enumeration."""
    body = text[text.index("typedef struct {"):]
    body = body[:body.index("} nsh_api_v1;")]
    out = []
    for m in MEMBER.finditer(body):
        args = re.sub(r"\s+", " ", m.group(2)).strip()
        args = args.replace("nsh_session*", "nsh_session *")
        args = ", ".join(strip_name(a.strip()) for a in args.split(","))
        out.append((m.group(1), args))
    return out


header = open(os.path.join(ROOT, "include", "nashira3d.h"), encoding="utf-8").read()
h_members = members(header)
c_members = members(b.CDEF)

check("the header has as many fields as the cdef", len(c_members), len(h_members))
check("the order and the arguments match exactly", c_members, h_members)
check("more than zero fields - the parse did not miss", len(h_members) > 5, True)

# --- error codes
enum = header[header.index("typedef enum {"):]
enum = enum[:enum.index("} nsh_status;")]
h_codes = {}
for name, value in re.findall(r"(NSH_\w+)\s*=\s*(\d+)", enum):
    h_codes[name.replace("NSH_", "")] = int(value)
py_codes = {k: v for k, v in vars(b).items() if k in h_codes}
check("the error codes match the header", py_codes, h_codes)

# --- versions
lpr = open(os.path.join(ROOT, "core", "nashira3d.lpr"), encoding="utf-8").read()
core_ver = re.search(r"NSH_VERSION\s*=\s*'([^']+)'", lpr).group(1)
proj = open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8").read()
proj_ver = re.search(r'^version\s*=\s*"([^"]+)"', proj, re.M).group(1)

core_num = core_ver.split("-")[0]
check("the package version continues the core version",
      proj_ver.startswith(core_num), True)
check("and the built library says the same thing",
      __import__("nashira3d").version(), core_ver)

# --- IS IT ONE LIBRARY -------------------------------------------------------
# The reason, which cost an evening. The binding looks for the library in the
# package directory first and only then in build. The wheel build used to put a
# copy there and not remove it; a minute later the copy was older than the
# freshly built one, and everything run from the source tree quietly took it.
# The edit looked as if it had done nothing: the shader in build/win64 was new,
# and the picture was the old one, down to the last byte.
#
# What is checked is not the presence of copies but their AGREEMENT: two
# identical copies are harmless, two different ones mean that what runs is not
# what was built.

import hashlib

from nashira3d import _binding as _b

seen = [(p, hashlib.sha256(open(p, "rb").read()).hexdigest()[:16])
        for p in _b._candidates() if os.path.isfile(p)]

check("at least one library was found", len(seen) > 0, True)
digests = set(d for _, d in seen)
if len(digests) > 1:
    for p, d in seen:
        print("     %s  %s" % (d, p))
check("every copy of the library found is identical", len(digests) <= 1, True)

print("")
print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
for n in bad:
    print("   %s" % n)
sys.exit(1 if bad else 0)
