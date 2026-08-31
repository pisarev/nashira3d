"""Nashira3D - three-dimensional plots from a formula.

    import nashira3d

    with nashira3d.Session("sin(3*x) * cos(3*y)", domain=(-2, 2, -2, 2)) as s:
        s.save_png("wave.png", 800, 600)

The frame is drawn without a window: the library needs neither a screen nor a
window manager, and it works the same in a notebook, on a server, and in a
container.

numpy is NOT required. If it is there, render hands back an (H, W, 4) array;
if it is not, a memoryview of the same shape over the same memory. The price of
making it optional is one check, and the gain is that the library can be
installed where numpy is not wanted.
"""

import struct
import zlib

from . import _binding as _b

__all__ = ["Session", "Nashira3DError", "version"]

try:
    import numpy as _np
except ImportError:
    _np = None


class Nashira3DError(RuntimeError):
    """A refusal from the core. The text comes from the core itself and is not
    made up here."""


_LIB = None
_API = None
_FFI = _b.ffi


def _ensure():
    """Load the core ON FIRST USE, not on import.

    The load used to sit at module level, and "import nashira3d" failed for
    anyone without a graphics card or without the library - even for someone
    importing the package only to read __version__ or to build documentation.
    An import has no right to demand hardware.

    Found by the contract probe: it could not even report a mismatch, because
    it died on its own import.
    """
    global _LIB, _API
    if _API is None:
        _LIB, _API = _b.load()
    return _API


def _check(session, code):
    if code == _b.OK:
        return
    text = ""
    if session is not None:
        raw = _API.last_error(session)
        if raw != _FFI.NULL:
            text = _FFI.string(raw).decode("utf-8", "replace")
    name = _b.NAMES.get(code, str(code))
    raise Nashira3DError("%s: %s" % (name, text) if text else name)


def version():
    """The version of the core, not of the wrapper: the library is asked."""
    return _FFI.string(_ensure().version()).decode()


# Names in words rather than numbers. A number in a call reads as a riddle:
# seeing shading=2, nobody can say it means "colour and lines both", and seeing
# "both", everybody can. Both spellings of colour are accepted.
# The domain is either declared by a person (a cube) or worked out from the
# point of view (a plane). Words for the same reason: 1 in a call reads as a
# riddle, "view" reads as a word.
_REGION = {
    "declared": 0, "domain": 0, "cube": 0,
    "view": 1, "camera": 1, "plane": 1,
}

_SHADING = {
    "contours": 0, "lines": 0,
    "color": 1, "colour": 1,
    "both": 2,
}


class Session:
    """One scene: a formula, a domain, a camera, a light.

    A session is NOT thread-safe - one thread at a time. There can be many
    sessions.
    """

    def __init__(self, formula=None, domain=(-1.0, 1.0, -1.0, 1.0), quality=50,
                 camera=(0.9, 0.45, 3.4, 0.9), pan=(0.0, 0.0),
                 box=(1.0, 1.0, 0.3), fit=True, grid=True, fill=2.4,
                 light=(2.2, 0.9), axes=False):
        api = _ensure()
        pp = _FFI.new("nsh_session**")
        _check(None, api.create(pp))
        self._s = pp[0]
        self._closed = False
        self.domain = domain
        self.quality = quality
        self.camera = camera
        self.pan = pan
        self.box = box
        self.fit = fit
        self.grid = grid
        self.fill = fill
        self.light = light
        self.axes = axes
        if formula is not None:
            self.formula = formula

    def _alive(self):
        if self._closed:
            raise Nashira3DError("session is closed")

    @property
    def formula(self):
        return self._formula

    @formula.setter
    def formula(self, text):
        self._alive()
        _check(self._s, _API.set_formula(self._s, text.encode("utf-8")))
        self._formula = text

    @property
    def domain(self):
        return self._domain

    @domain.setter
    def domain(self, box):
        self._alive()
        x0, x1, y0, y1 = (float(v) for v in box)
        _check(self._s, _API.set_domain(self._s, x0, x1, y0, y1))
        self._domain = (x0, x1, y0, y1)

    @property
    def quality(self):
        return self._quality

    @quality.setter
    def quality(self, value):
        self._alive()
        _check(self._s, _API.set_quality(self._s, int(value)))
        self._quality = int(value)

    @property
    def camera(self):
        return self._camera

    @camera.setter
    def camera(self, value):
        self._alive()
        az, el, dist, fov = (float(v) for v in value)
        _check(self._s, _API.set_camera(self._s, az, el, dist, fov))
        self._camera = (az, el, dist, fov)

    @property
    def pan(self):
        """Move the point the camera looks at, in the plane of the frame, in
        fractions of the box: (right, up).

        (0, 0) puts the surface in the middle. The amount is not limited:
        taking the plot past the edge of the frame is a fair wish, not a
        mistake.
        """
        return self._pan

    @pan.setter
    def pan(self, value):
        self._alive()
        dx, dy = (float(v) for v in value)
        _check(self._s, _API.set_pan(self._s, dx, dy))
        self._pan = (dx, dy)

    @property
    def box(self):
        """The proportions of the box the plot is fitted into: a half-size
        along each axis.

        The default (1, 1, 0.3) gives a square floor three times wider than the
        height. This is NOT the range of values: the domain sets that, and here
        only the shape of the box is decided. Stretching z to see a shallow
        ripple, or flattening the floor into a wide slab, are ordinary wishes.
        """
        return self._box

    @box.setter
    def box(self, value):
        self._alive()
        sx, sy, sz = (float(v) for v in value)
        _check(self._s, _API.set_box(self._s, sx, sy, sz))
        self._box = (sx, sy, sz)

    @property
    def fit(self):
        """Whether to choose the distance of the camera so the box fills the
        frame.

        On by default. While it is on, the distance in camera serves only as a
        starting guess: the real distance is worked out on every frame. Turning
        it off makes sense when a person is driving the distance.
        """
        return self._fit

    @fit.setter
    def fit(self, value):
        self._alive()
        on = bool(value)
        _check(self._s, _API.set_fit(self._s, 1 if on else 0))
        self._fit = on

    @property
    def grid(self):
        """The mesh laid on the surface: lines along constant x and constant y.

        On by default. It takes over from the wireframe box as the thing that
        shows which way round the plot is, and it shows the shape of the relief
        between the nodes as well.
        """
        return self._grid

    @grid.setter
    def grid(self, value):
        self._alive()
        on = bool(value)
        _check(self._s, _API.set_grid(self._s, 1 if on else 0))
        self._grid = on

    @property
    def fill(self):
        """How large the sheet sits in the frame: 1 fits it whole, above that
        it runs past the edges. 2.4 by default."""
        return self._fill

    @fill.setter
    def fill(self, value):
        self._alive()
        k = float(value)
        _check(self._s, _API.set_fill(self._s, k))
        self._fill = k

    def fit_z(self):
        """Recompute the vertical scale from what is in view right now.

        The scale in height is a property of the scene, not a consequence of
        the frame: it is computed once when the formula changes and frozen
        after that, and moving the camera does not touch it. This call is the
        only way to recompute it by hand.
        """
        self._alive()
        _check(self._s, _API.fit_z(self._s))

    def stand(self, cx, cy, h, azimuth, elevation, fov=0.9):
        """Put the camera at a STANDING POINT with a signed height.

        Drop a perpendicular from the camera to the reference plane, and it is
        that height which holds as the camera tilts. Tilting changes only the
        direction, panning only the point, the wheel only the height.

        h is signed: above zero is above the plane, zero puts the camera IN it,
        below zero is underneath. Zero is allowed, and there is no forbidden
        neighbourhood around it.

        The call cancels the orbiting camera: this one has no distance at all.
        The domain is worked out by the library and is available from region().
        """
        self._alive()
        _check(self._s, _API.set_camera_at(self._s, float(cx), float(cy),
                                           float(h), float(azimuth),
                                           float(elevation), float(fov)))
        self._stand = (float(cx), float(cy), float(h),
                       float(azimuth), float(elevation), float(fov))

    def region(self, width, height):
        """The domain in view at the current point of view: (x0, x1, y0, y1)."""
        self._alive()
        out = _FFI.new("double[4]")
        _check(self._s, _API.view_region(self._s, int(width), int(height), out))
        return (out[0], out[1], out[2], out[3])

    @property
    def auto_z(self):
        """Whether to refit the scale in z by itself once the range doubles.

        OFF by default. Refitting all the time makes the geometry a consequence
        of the camera: the surface sinks the moment a new peak enters the
        domain."""
        return self._autoz

    @auto_z.setter
    def auto_z(self, value):
        self._alive()
        _check(self._s, _API.set_auto_z(self._s, 1 if value else 0))
        self._autoz = bool(value)

    def auto_z_fired(self):
        """Whether the automatic refit fired on the last frame.

        Reading it clears it: a short notice is shown once."""
        self._alive()
        return _API.auto_z_fired(self._s) != 0

    @property
    def region_mode(self):
        """Where the domain comes from: "declared" or "view".

        The only difference between the two ways of drawing. In a declared
        domain a person set the edges - that is a cube, and the edges show. In
        a computed one the domain follows from the point of view - that is an
        endless plane, its sampling lines are placed by the density on screen,
        and the far edge dissolves into the background: the dissolve is carried
        all the way to the background exactly at the edge of the mesh, which is
        why that edge never shows in the frame.

        The computation and the drawing are the same either way."""
        return self._region

    @region_mode.setter
    def region_mode(self, value):
        self._alive()
        mode = _REGION.get(str(value).strip().lower())
        if mode is None:
            raise ValueError(
                'region_mode must be one of %s, got %r'
                % (", ".join(sorted(_REGION)), value))
        _check(self._s, _API.set_region_mode(self._s, mode))
        self._region = "view" if mode else "declared"

    @property
    def shading(self):
        """How the relief is shown: "contours", "color", or "both".

        Contour lines by default. Colour gives the shape at once, but you
        cannot count with it: the eye does not turn a shade into a number. A
        line of equal height is a number, and it shows the way it does on a
        map."""
        return self._shade

    @shading.setter
    def shading(self, value):
        self._alive()
        mode = _SHADING.get(str(value).strip().lower())
        if mode is None:
            raise ValueError(
                'shading must be one of %s, got %r'
                % (", ".join(sorted(_SHADING)), value))
        _check(self._s, _API.set_shading(self._s, mode, self._cstep))
        self._shade = str(value).strip().lower()

    @property
    def contour_step(self):
        """The distance in height between contour lines. Zero chooses one."""
        return self._cstep

    @contour_step.setter
    def contour_step(self, value):
        self._alive()
        step = float(value)
        _check(self._s, _API.set_shading(self._s, _SHADING[self._shade], step))
        self._cstep = step

    @property
    def max_extent(self):
        """The furthest distance, in the units of the problem. Zero takes the
        default."""
        return self._extent

    @max_extent.setter
    def max_extent(self, value):
        self._alive()
        _check(self._s, _API.set_max_extent(self._s, float(value)))
        self._extent = float(value)

    @property
    def z_exaggeration(self):
        """A multiplier on the frozen vertical exaggeration."""
        return self._zexag

    @z_exaggeration.setter
    def z_exaggeration(self, value):
        self._alive()
        _check(self._s, _API.set_z_exaggeration(self._s, float(value)))
        self._zexag = float(value)

    @property
    def obstacles(self):
        """Parts of the frame that are taken: a list of (x, y, w, h) in points.

        Labels are placed where there is room, and only the caller knows where
        there is room: their panels lie OVER the frame and the library cannot
        see them. The hint is optional - without it the frame comes out a
        little worse, but it comes out."""
        return list(self._obst)

    @obstacles.setter
    def obstacles(self, value):
        self._alive()
        flat = []
        for r in (value or []):
            if isinstance(r, (int, float)):
                flat.append(int(r))
            else:
                flat.extend(int(v) for v in r)
        arr = _FFI.new("int32_t[]", flat) if flat else _FFI.NULL
        _check(self._s, _API.set_obstacles(self._s, arr, len(flat)))
        self._obst = tuple(flat)

    @property
    def light(self):
        return self._light

    @light.setter
    def light(self, value):
        self._alive()
        az, el = (float(v) for v in value)
        _check(self._s, _API.set_light(self._s, az, el))
        self._obst = ()
        self._stand = None
        self._extent = 0.0
        self._zexag = 1.0
        self._autoz = False
        self._shade = "contours"
        self._region = "declared"
        self._cstep = 0.0
        self._light = (az, el)

    @property
    def axes(self):
        return self._axes

    @axes.setter
    def axes(self, value):
        self._alive()
        _check(self._s, _API.set_axes(self._s, 1 if value else 0))
        self._axes = bool(value)

    def _render_bytes(self, w, h):
        """The flat buffer of the frame. Everything else is built FROM IT.

        The separate layer is not decoration: save_png by way of an array
        failed for anyone without numpy, because a three-dimensional memoryview
        will not hand back a row by index. Found by installing the wheel into a
        clean environment, not by reasoning about it.
        """
        self._alive()
        buf = _FFI.new("uint8_t[]", w * h * 4)
        _check(self._s, _API.render(self._s, w, h, buf))
        return bytes(_FFI.buffer(buf, w * h * 4))

    def render(self, width=800, height=600):
        """The frame. With numpy, a (height, width, 4) array, RGBA, eight bits
        per channel.

        Without numpy, a FLAT memoryview of length height*width*4, rows one
        after another. Flat on purpose: a three-dimensional one looks usable
        and then will not hand back a row by index, which is worse than an
        honest flat buffer.
        """
        w, h = int(width), int(height)
        raw = self._render_bytes(w, h)
        if _np is not None:
            return _np.frombuffer(raw, dtype=_np.uint8).reshape(h, w, 4).copy()
        return memoryview(raw)

    def save_png(self, path, width=800, height=600):
        """The frame straight to a file. A PNG writer of our own on the zlib
        that ships with Python: there is no reason to drag in a whole imaging
        library for one picture."""
        w, h = int(width), int(height)
        flat = self._render_bytes(w, h)
        stride = w * 4
        raw = b"".join(b"\x00" + flat[y * stride:(y + 1) * stride]
                       for y in range(h))

        def chunk(tag, data):
            return (struct.pack(">I", len(data)) + tag + data
                    + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

        png = b"\x89PNG\r\n\x1a\n"
        png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        png += chunk(b"IDAT", zlib.compress(raw, 6))
        png += chunk(b"IEND", b"")
        with open(path, "wb") as f:
            f.write(png)
        return path

    def close(self):
        if not self._closed:
            _API.destroy(self._s)
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
