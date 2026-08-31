"""Measurement 5.15: what the bounding rectangle costs.

The mesh of nodes is FIXED by the quality setting: 256 by 256 is 65536 nodes
both for a domain two units across and for one twenty units across. So the
price of a wide domain is not time but spatial resolution. The measurement has
to name that number.

How the error is worked out. The library builds the surface on a uniform mesh
within the domain; between the nodes it is stretched linearly - on the screen
and in the labels alike. So the error of representation is the difference
between the true function and its linear stretch over the nodes. Here it is
computed on a mesh four times as fine, because side in the library tops out at
256 and a quality=512 reference is out of its reach entirely.

What the criterion checks: the mean absolute error of the normalised height is
no more than 2 per cent of the full frozen z span.

Run by hand: minutes, not seconds. It is not part of the battery.
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "python"))
import numpy as np
import nashira3d

# Six harmonics, as the criterion asks: such a function has something to lose.
HARM = [(3, 3, 1.0), (7, 5, 0.5), (11, 13, 0.3),
        (17, 19, 0.2), (23, 29, 0.15), (31, 37, 0.1)]
FORMULA = " + ".join("%g*sin(%d*x)*cos(%d*y)" % (a, kx, ky) for kx, ky, a in HARM)


def f(x, y):
    z = np.zeros_like(x)
    for kx, ky, a in HARM:
        z += a * np.sin(kx * x) * np.cos(ky * y)
    return z


def sampling_error(x0, x1, y0, y1, side, dense):
    """The mean and the largest error of the linear stretch over a side by side
    mesh.

    Computed on a dense by dense mesh inside the same domain: the true value
    against the bilinear stretch between the nodes."""
    gx = np.linspace(x0, x1, side)
    gy = np.linspace(y0, y1, side)
    node = f(*np.meshgrid(gx, gy, indexing="ij"))

    dx = np.linspace(x0, x1, dense)
    dy = np.linspace(y0, y1, dense)
    truth = f(*np.meshgrid(dx, dy, indexing="ij"))

    # where the dense-mesh points sit, measured in nodes
    u = (dx - x0) / (x1 - x0) * (side - 1)
    v = (dy - y0) / (y1 - y0) * (side - 1)
    i0 = np.clip(np.floor(u).astype(int), 0, side - 2)
    j0 = np.clip(np.floor(v).astype(int), 0, side - 2)
    fu = (u - i0)[:, None]
    fv = (v - j0)[None, :]

    a = node[i0][:, j0]
    b = node[i0 + 1][:, j0]
    c = node[i0][:, j0 + 1]
    d = node[i0 + 1][:, j0 + 1]
    lerp = (a * (1 - fu) * (1 - fv) + b * fu * (1 - fv) +
            c * (1 - fu) * fv + d * fu * fv)
    err = np.abs(truth - lerp)
    return float(err.mean()), float(err.max())


def main():
    W, H = 1180, 760
    s = nashira3d.Session(FORMULA, quality=100)
    s.domain = (-2, 2, -2, 2)
    s.grid = True
    s.axes = False
    s.render(200, 140)                     # freeze the scale

    span = None
    el, h = 1.0, 2.2

    print("formula: %s" % FORMULA)
    print("nodes per side: %d, reference: %d" % (256, 1024))
    print()
    print("%8s %9s %9s %11s %11s" % ("azimuth", "dx", "dy", "mean err", "max err"))

    worst_mean = 0.0
    worst_max = 0.0
    rows = []
    for deg in range(0, 181, 5):
        az = math.radians(deg)
        d = h / math.tan(el)
        s.stand(d * math.cos(az), d * math.sin(az), h, az, el, 0.9)
        x0, x1, y0, y1 = s.region(W, H)
        if span is None:
            # The full frozen z span is taken from THE FUNCTION ITSELF: for a
            # sum of harmonics it is known and does not depend on the domain.
            gx = np.linspace(-4, 4, 2000)
            zz = f(*np.meshgrid(gx, gx, indexing="ij"))
            span = float(zz.max() - zz.min())
        m, mx = sampling_error(x0, x1, y0, y1, 256, 1024)
        rows.append((deg, x1 - x0, y1 - y0, m / span, mx / span))
        worst_mean = max(worst_mean, m / span)
        worst_max = max(worst_max, mx / span)

    for deg, dx, dy, m, mx in rows:
        print("%7d° %9.3f %9.3f %10.2f%% %10.2f%%" % (deg, dx, dy, 100 * m, 100 * mx))

    print()
    print("full frozen z span:        %.4f" % span)
    print("LARGEST mean error:        %.2f%%  (threshold of criterion 5.15: 2%%)"
          % (100 * worst_mean))
    print("largest error at a point:  %.2f%%" % (100 * worst_max))
    print()
    print("criterion 5.15 %s" % ("MET" if worst_mean <= 0.02
                                 else "BROKEN - LOD becomes a task of its own"))

    # The criterion fixes the elevation, and at the fixed one all is well. But
    # the price of the domain grows precisely at a SHALLOW look: the upper ray
    # of the frustum runs off towards the horizon and the domain swells. That
    # is outside the criterion, but saying nothing about it would mean
    # reporting the best case as if it were all of them.
    print()
    print("beyond the criterion: the same check at other elevations")
    print("%9s %9s %11s %11s" % ("elevation", "domain", "mean err", "max"))
    for el2 in (1.30, 1.00, 0.80, 0.70, 0.60, 0.55):
        d = h / math.tan(el2)
        s.stand(d * math.cos(0.9), d * math.sin(0.9), h, 0.9, el2, 0.9)
        x0, x1, y0, y1 = s.region(W, H)
        m, mx = sampling_error(x0, x1, y0, y1, 256, 1024)
        print("%9.2f %9.1f %10.2f%% %10.2f%%"
              % (el2, max(x1 - x0, y1 - y0), 100 * m / span, 100 * mx / span))
    s.close()


if __name__ == "__main__":
    main()
