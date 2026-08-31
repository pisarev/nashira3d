"""Axes. A check with BOTH cases: with axes and without them the picture has to
DIFFER. Otherwise the flag is accepted and not acted on."""

import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "python"))
import numpy as np
from nashira3d import _binding as b

HERE = os.path.dirname(os.path.abspath(__file__))
ok, bad = 0, []


def check(name, got, want):
    global ok
    if got == want:
        ok += 1
        print("  ok   %-46s %s" % (name, got))
    else:
        bad.append(name)
        print("  FAIL %-46s got %r, want %r" % (name, got, want))


def write_png(path, img):
    h, w, _ = img.shape
    raw = b"".join(b"\x00" + img[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


lib, api = b.load()
ffi = b.ffi
W = H = 320
buf = ffi.new("uint8_t[]", W * H * 4)
pp = ffi.new("nsh_session**")
api.create(pp)
s = pp[0]
api.set_formula(s, b"sin(3*x) * cos(3*y)")
api.set_domain(s, -1.0, 1.0, -1.0, 1.0)
api.set_quality(s, 60)
api.set_camera(s, 0.9, 0.45, 3.4, 0.9)
api.set_light(s, 2.2, 0.9)


def frame():
    rc = api.render(s, W, H, buf)
    assert rc == b.OK, ffi.string(api.last_error(s)).decode()
    return np.frombuffer(ffi.buffer(buf, W * H * 4), dtype=np.uint8).reshape(H, W, 4).copy()


api.set_axes(s, 0)
off = frame()
api.set_axes(s, 1)
on = frame()
write_png(os.path.join(HERE, "surface_axes.png"), on)

check("without axes and with them - DIFFERENT pictures", bool((off != on).any()), True)

diff = (np.abs(off.astype(int) - on.astype(int)).sum(axis=2) > 12)
check("the lines added pixels, not one pixel", int(diff.sum()) > 300, True)

# the lines have to be OUTSIDE the surface as well: the box goes past its edge
frame_mask = diff.copy()
edge = frame_mask[:, :40].sum() + frame_mask[:, -40:].sum()
check("the frame is visible at the edges too", int(edge) > 20, True)
check("but it did not flood the frame", int(diff.sum()) < W * H // 3, True)

api.destroy(s)
print("")
print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
for n in bad:
    print("   %s" % n)
print("picture: tests/surface_axes.png")
sys.exit(1 if bad else 0)
