"""Every probe at once. One number instead of six, and one exit code.

The order is deliberate: from the seam outwards to the user. If the seam leaks
there is no sense in reading the rest, and the very first failure shows it.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

PY_PROBES = [
    ("contract: header, cdef, versions", "probe_contract.py"),
    ("the C seam and the table", "probe_abi.py"),
    ("reading a frame, and orientation", "probe_frame.py"),
    ("a surface from a formula", "probe_surface.py"),
    ("axes", "probe_axes.py"),
    ("the public Python interface", "probe_public.py"),
    ("the colour bar", "probe_colorbar.py"),
    ("contour lines", "probe_contours.py"),
    ("fading with distance", "probe_fade.py"),
    ("the camera as a standing point", "probe_stand.py"),
    ("where the region comes from", "probe_region.py"),
    ("the plane is frozen", "probe_plane_frozen.py"),
    ("the cube rotation contract", "probe_cube_contract.py"),
    ("the samples on the page", "probe_samples.py"),
    ("the calls on the page", "probe_page.py"),
    ("the page camera, by running it", "probe_camera_js.py"),
    ("page start-up", "probe_page_boot.py"),
    # A run through the FROZEN acceptance criteria. Until 2026-08-31 nobody ran
    # it: the battery printed "346 checks, 0 failures", and that was true - but
    # true about the probes, not about the criteria. The run itself lay in the
    # tree all the while and went out to the user red. A check left out of the
    # run guards nothing; it goes last because it is long.
    ("the acceptance criteria", "acceptance.py"),
]


# The battery has no right to be narrower than the set of probes. What is
# listed here is NOT what was meant to exist but what lies in the directory:
# any probe_*.py and the run through the criteria are required to stand in the
# list above. Otherwise a new probe quietly stays a file nobody needs, and the
# result of the run is incomplete.
def _every_probe_is_listed():
    listed = set(n for _, n in PY_PROBES)
    found = sorted(n for n in os.listdir(HERE)
                   if (n.startswith("probe_") or n == "acceptance.py")
                   and n.endswith(".py"))
    return [n for n in found if n not in listed]


_orphans = _every_probe_is_listed()
if _orphans:
    print("  FAIL the battery is narrower than the set of probes: in the "
          "directory but not in the run: %s" % ", ".join(_orphans))

# The name of a built probe depends on the platform, and the extension must not
# be written into the code. There used to be "mesh_probe.exe" here, and under
# Linux, where the file has no extension, the battery did not find the Pascal
# probes AT ALL - and recorded them as a FAILURE. A false red is worse than a
# skip: it says "broken" where the truth is "not built". Caught by the very
# first run under Linux.
EXE = ".exe" if sys.platform == "win32" else ""

PAS_PROBES = [
    ("mesh, Pascal", "mesh_probe" + EXE),
    ("camera, Pascal", "cam_probe" + EXE),
]

# An outside consumer of the seam in plain C. It stands apart from the Pascal
# probes for two reasons: a FOREIGN compiler builds it (cl or cc, not fpc), and
# it needs the path to the library itself as an argument.
#
# Why it was set up. Until now the seam was only ever exercised through our own
# cffi binding. A mistake about the layout of the table, made in the core and in
# the binding alike, cancels itself out, and hundreds of checks pass in
# agreement. A foreign program that knows nothing but include/nashira3d.h breaks
# that symmetry: it matches the sizeof of the table on its own side against the
# number that arrived from the other.
C_PROBES = [("the seam through outside eyes, in C", "c_consumer" + EXE)]

LIBS = [os.path.join(ROOT, "build", "win64", "nashira3d.dll"),
        os.path.join(ROOT, "build", "linux64", "libnashira3d.so")]

total = len(_orphans)
failed = len(_orphans)
rows = []
missing = []
unchecked = []

for title, name in PY_PROBES:
    r = subprocess.run([sys.executable, os.path.join(HERE, name)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = r.stdout or ""
    n_ok = out.count("  ok ")
    n_bad = out.count("  FAIL")
    total += n_ok + n_bad
    failed += n_bad
    rows.append((title, n_ok + n_bad, n_bad, r.returncode))
    # Code 2 means "NOT EVERYTHING was checked", and that is not a failure.
    # That is what the run through the criteria answers when some of them
    # cannot be judged on this machine: the performance baseline was taken on
    # other hardware. To count that as a breakage is to go red over somebody
    # else's processor; to count it as passed is to pass a skip off as a check.
    if r.returncode == 2:
        for ln in out.splitlines():
            if "NOT CHECKED:" in ln and ln.startswith("   "):
                unchecked.append((title, ln.strip()))
    elif r.returncode != 0 and n_bad == 0:
        failed += 1

for title, exe in PAS_PROBES:
    path = os.path.join(ROOT, "build", "probe", exe)
    if not os.path.isfile(path):
        # NOT a failure and NOT green. A probe that was not built is something
        # NOT CHECKED, and that has to be said aloud on a line of its own.
        # Recording a failure here would lie about a breakage; saying nothing
        # would pass a skip off as something that ran. Neither.
        missing.append((title, exe))
        continue
    r = subprocess.run([path], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = r.stdout or ""
    n_ok = out.count("  ok ")
    n_bad = out.count("  FAIL")
    total += n_ok + n_bad
    failed += n_bad
    rows.append((title, n_ok + n_bad, n_bad, r.returncode))

lib = next((p for p in LIBS if os.path.isfile(p)), None)
for title, exe in C_PROBES:
    path = os.path.join(ROOT, "build", "probe", exe)
    if not os.path.isfile(path) or lib is None:
        missing.append((title, exe if lib else exe + " (no library was built)"))
        continue
    r = subprocess.run([path, lib], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = r.stdout or ""
    n_ok = out.count("  ok ")
    n_bad = out.count("  FAIL")
    total += n_ok + n_bad
    failed += n_bad
    rows.append((title, n_ok + n_bad, n_bad, r.returncode))

print("%-34s %8s %8s %6s" % ("probe", "checks", "failed", "code"))
print("-" * 60)
for title, n, f, code in rows:
    print("%-34s %8d %8d %6d" % (title, n, f, code))
print("-" * 60)
print("TOTAL: checks %d, failures %d, probes not built %d, not checked %d"
      % (total, failed, len(missing), len(unchecked)))
for title, exe in missing:
    print("   NOT BUILT, therefore NOT CHECKED: %s (%s) - see tests/build_probes"
          % (title, exe))
for title, why in unchecked:
    print("   %s: %s" % (title, why))
# Zero checks is not "all is well", it is "nothing was looked at". Such a run
# has to go red, or an empty battery reads as a green one.
if not total:
    print("   NOT A SINGLE check was carried out")
# THREE outcomes, not two. Zero - everything was checked and everything is
# green. One - there is a failure. Two - no failures, but NOT EVERYTHING was
# checked, and passing that off as zero is not allowed: whoever looks only at
# the exit code would read an incomplete run as a complete one. A skip is not a
# breakage, but neither is it "all is well".
if failed or not total:
    sys.exit(1)
sys.exit(2 if (missing or unchecked) else 0)
