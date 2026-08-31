"""Reading a frame, and ITS ORIENTATION.

Why a separate probe. Flipping the rows is the one place where the mistake is
invisible on any symmetrical picture: the image simply stands on its head while
every number still adds up. So the surface taken here is NOT symmetrical, and
which half of the frame is lighter is nailed down.

The direction comes from a MEASUREMENT on a correct picture, not from the
OpenGL conventions. That is legitimate: the probe's job is to catch a future
flip, not to derive the convention again.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "python"))
import numpy as np
import nashira3d

ok, bad = 0, []


def check(name, got, want):
    global ok
    if got == want:
        ok += 1
        print("  ok   %-46s %s" % (name, got))
    else:
        bad.append(name)
        print("  FAIL %-46s got %r, want %r" % (name, got, want))


# A DOME, not a tilted plane. The first attempt took z = y at azimuth 0 - and
# was worthless: at that azimuth the camera stands on the x axis, world y lies
# across the screen HORIZONTALLY, and there is no asymmetry in the vertical at
# all. The measurement said as much: 50.0 against 47.5, which is noise.
#
# A dome has a high crest, and height here is colour: the crest lands at the
# light end of the scale. So the top of the frame has to be brighter than the
# bottom at ANY azimuth, and flipped rows would break that at once. Measured:
# 90.9 against 47.4, a difference of 43.5 - fourfold headroom.
# THE PREMISE IS NAMED OUT LOUD. The subject here is the colour ramp: the
# surface is separated from the background BY SATURATION, and under contour
# lines it is neutral and has no saturation at all. The default shading changed
# to lines, and the probe has to say what it wants rather than lean on a
# default.
s = nashira3d.Session("-(x*x + y*y)", domain=(-1, 1, -1, 1), quality=40,
                    camera=(0.0, 0.45, 3.2, 0.9), axes=False)
s.shading = "colour"
img = s.render(200, 200)

def surface_mean(part):
    """The mean over the SURFACE ITSELF, not over the frame. The background
    takes up more than half of it and dilutes both halves equally, so the
    difference drowns: the first measurement gave 25.6 against 30.8 at a
    threshold of 6, and the probe went red on a correct picture. What has to be
    measured is the subject, not what surrounds it.

    The subject is separated by SATURATION, not by brightness. A threshold on
    the sum of the channels worked while the background was an almost black
    fill; as soon as the background became a gradient, its upper part crossed
    the threshold and started counting as surface - and the probe went red on a
    correct picture a second time. The trait was a proxy: "light" does not mean
    "subject". Saturation does: the background is grey-blue, its max-min across
    the channels is about 15, and the surface is past 60."""
    rgb = part[:, :, :3].astype(int)
    sat = rgb.max(axis=2) - rgb.min(axis=2)
    mask = sat > 30
    if mask.sum() == 0:
        return 0.0
    return float(rgb[mask].mean())


mt = surface_mean(img[:100])
mb = surface_mean(img[100:])
print("mean brightness of the surface: top %.1f, bottom %.1f" % (mt, mb))

check("the halves differ noticeably", abs(mt - mb) > 25, True)
check("the crest of the dome is ON TOP, so the top is brighter", mt > mb, True)

check("the frame is the size that was asked for", tuple(img.shape), (200, 200, 4))
check("opaque everywhere", int(img[..., 3].min()), 255)

# another size - the buffer has to be rebuilt while the picture stays the same
img2 = s.render(120, 90)
check("another size works", tuple(img2.shape), (90, 120, 4))
t2 = surface_mean(img2[:45])
b2 = surface_mean(img2[45:])
check("and the orientation is the same", t2 > b2, True)

s.close()
print("")
print("checks: %d, failures: %d" % (ok + len(bad), len(bad)))
for n in bad:
    print("   %s" % n)
sys.exit(1 if bad else 0)
