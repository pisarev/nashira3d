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
]

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

total = 0
failed = 0
rows = []
missing = []

for title, name in PY_PROBES:
    r = subprocess.run([sys.executable, os.path.join(HERE, name)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = r.stdout or ""
    n_ok = out.count("  ok ")
    n_bad = out.count("  FAIL")
    total += n_ok + n_bad
    failed += n_bad
    rows.append((title, n_ok + n_bad, n_bad, r.returncode))
    if r.returncode != 0 and n_bad == 0:
        rows[-1] = (title, n_ok + n_bad, n_bad, r.returncode)
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

print("%-34s %8s %8s %6s" % ("probe", "checks", "failed", "code"))
print("-" * 60)
for title, n, f, code in rows:
    print("%-34s %8d %8d %6d" % (title, n, f, code))
print("-" * 60)
print("TOTAL: checks %d, failures %d, probes not built %d"
      % (total, failed, len(missing)))
for title, exe in missing:
    print("   NOT BUILT, therefore NOT CHECKED: %s (%s) - see tests/build_probes"
          % (title, exe))
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
sys.exit(2 if missing else 0)
