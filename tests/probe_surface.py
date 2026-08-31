"""A surface from a formula. What is checked is not that 'something got drawn'
but that the picture DEPENDS on the formula and on the camera: an image that
does not change with them would prove only that the memory has been filled."""

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
        print("  ok   %-44s %s" % (name, got))
    else:
        bad.append(name)
        print("  FAIL %-44s got %r, want %r" % (name, got, want))


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


def frame(s):
    rc = api.render(s, W, H, buf)
    if rc != b.OK:
        raise RuntimeError("%s: %s" % (b.NAMES.get(rc, rc),
                                       ffi.string(api.last_error(s)).decode()))
    return np.frombuffer(ffi.buffer(buf, W * H * 4), dtype=np.uint8).reshape(H, W, 4).copy()


pp = ffi.new("nsh_session**")
api.create(pp)
s = pp[0]

check("the formula is accepted", api.set_formula(s, b"x*x + y*y"), b.OK)
check("the domain is accepted", api.set_domain(s, -1.0, 1.0, -1.0, 1.0), b.OK)
check("the quality is accepted", api.set_quality(s, 60), b.OK)
check("the camera is accepted", api.set_camera(s, 0.9, 0.55, 3.2, 0.9), b.OK)
check("the light is accepted", api.set_light(s, 2.2, 0.9), b.OK)

img = frame(s)
write_png(os.path.join(HERE, "surface_bowl.png"), img)

colors = len(np.unique(img.reshape(-1, 4), axis=0))
check("many colours, not a flat fill", colors > 500, True)
check("the background is there: the corner is dark", int(img[3, 3, 0]) < 40, True)
check("there is a lit ridge", int(img[..., 1].max()) > 150, True)
check("opaque everywhere", int(img[..., 3].min()), 255)

# the camera has to matter
api.set_camera(s, 2.4, 0.55, 3.2, 0.9)
img2 = frame(s)
check("turning the camera changes the picture", bool((img != img2).any()), True)

# the formula has to matter
api.set_camera(s, 0.9, 0.55, 3.2, 0.9)
api.set_formula(s, b"sin(3*x) * cos(3*y)")
img3 = frame(s)
write_png(os.path.join(HERE, "surface_waves.png"), img3)
check("a new formula changes the picture", bool((img != img3).any()), True)
diff = int(np.abs(img.astype(int) - img3.astype(int)).mean())
check("and changes it A LOT, not by a pixel", diff > 5, True)

# a formula without a single finite value has to REFUSE rather than draw a void
api.set_formula(s, b"1/0")
rc = api.render(s, W, H, buf)
check("a hopeless formula is rejected", rc in (b.ERR_FORMULA, b.ERR_ARG), True)
check("and is named in words", len(ffi.string(api.last_error(s))) > 0, True)

api.destroy(s)
print("")
print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
for n in bad:
    print("   %s" % n)
print("pictures: tests/surface_bowl.png, tests/surface_waves.png")
sys.exit(1 if bad else 0)
