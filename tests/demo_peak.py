"""A demonstration of the difference. WITH A CHECK that the difference comes
from the method and not from luck.

The first attempt at this demonstration was worthless: quality 0 gives 16
lines, and curvature sampling never drops below seventeen - so it refined
NOTHING. The pictures differed by one extra line. A demonstration that does not
test its own premise proves the wrong thing.
"""

import os
import struct
import subprocess
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "python"))

PEAK = "exp(-400*((x-0.137)*(x-0.137) + (y+0.211)*(y+0.211)))"
QUALITY = 12          # 16 + 29 = 45 lines

# The peak is NARROW on purpose. On a wide one a uniform mesh gets away with
# luck, and the difference stays in the numbers alone: at 64 lines both
# pictures gave the same height for the summit. Measured on a narrow one: at 45
# lines the uniform mesh loses 10% of the height, at 25 lines sixty-two per
# cent. The case worth showing is the one where the difference exists - and it
# should be said that the case was chosen deliberately.
SIZE = 460


def png(path, img):
    h, w, _ = img.shape
    raw = b"".join(b"\x00" + img[y].tobytes() for y in range(h))

    def ch(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n"
                + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                + ch(b"IDAT", zlib.compress(raw, 6)) + ch(b"IEND", b""))


def render(mode):
    import nashira3d
    with nashira3d.Session(PEAK, domain=(-1, 1, -1, 1), quality=QUALITY,
                         camera=(0.9, 0.5, 3.0, 0.9), light=(2.2, 0.9),
                         axes=True) as s:
        img = s.render(SIZE, SIZE)
        png(os.path.join(HERE, "peak_%s.png" % mode), img)
        return int(img[..., 1].max())


if len(sys.argv) > 1:
    print(render(sys.argv[1]))
else:
    out = {}
    for mode, flag in (("uniform", "0"), ("adaptive", "1")):
        env = dict(os.environ, NASHIRA3D_ADAPTIVE=flag)
        r = subprocess.run([sys.executable, __file__, mode], env=env,
                           capture_output=True, text=True)
        out[mode] = r.stdout.strip()
        print("%-9s green at the summit %s" % (mode, out[mode]))
    a = os.path.getsize(os.path.join(HERE, "peak_uniform.png"))
    b = os.path.getsize(os.path.join(HERE, "peak_adaptive.png"))
    print("png sizes: %d and %d" % (a, b))
    print("the pictures differ:", a != b)
