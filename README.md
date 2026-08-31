# Nashira3D

Three-dimensional surface plots straight from a formula, drawn on the GPU,
without opening a window.

```python
import nashira3d

with nashira3d.Session("sin(3*x) * cos(3*y)", domain=(-2, 2, -2, 2)) as s:
    s.save_png("wave.png", 800, 600)
```

That is the whole program. There is no figure, no backend to choose, no event
loop, and nothing to close.

## What makes it different

Plotting libraries take an **array** of samples. This one takes the **function**.

The difference is not cosmetic. Given `f` rather than its samples, a renderer
can sample where the surface actually bends, place a vertex exactly on a peak
instead of near it, and re-evaluate when you zoom instead of interpolating a
mesh that was fixed long ago. None of that is possible once the function has
been thrown away.

Version 0.2 does not do any of it yet - it samples a uniform grid like everyone
else. What it does already is keep the door open: the interface speaks of
`quality`, not of a grid size, so the sampling can grow up without a single
line changing on your side.

The formula is parsed and **compiled to machine code** before evaluation, so a
grid of a quarter of a million points is not a quarter of a million interpreted
expressions.

## Install

Take the wheel for your platform from the
[releases page](https://github.com/pisarev/nashira3d/releases) and install it:

```
pip install nashira3d-0.2.0-py3-none-win_amd64.whl
```

The wheel carries the compiled core. There is no compiler, no CMake and no
system package to install.

Nashira3D is not on PyPI yet. The name there is taken for good once it is
used, and version 0.2 is still moving, so the registry can wait until the
interface has settled. Building the wheel yourself takes one command and is
described under [Building from source](#building-from-source).

## What it needs

- Windows or Linux, 64-bit
- a driver with **OpenGL 3.3 core**. On Linux the offscreen context is created
  through EGL, so no display, no X server and no desktop session are required -
  it works in a container and over SSH.

## What version 0.2 does

- one surface `z = f(x, y)` over a rectangular domain
- a uniform grid, its density set by `quality` from 0 to 100
- one light, depth testing, and a choice of how the relief is drawn:
  contour lines by default, a height colour ramp, or both together
- a box with ticks and numbered axes, labelled on the edges nearest the viewer
- a frame returned as a `numpy` array, or written straight to PNG

## What it does not do yet

Said plainly, because a list of features is worth less than an honest list of
gaps:

- no window and no mouse: a frame is returned, not shown
- one surface per scene - no overlays, no point clouds, no volumes
- no adaptive sampling: a peak between two grid nodes is still missed, and the
  reported extremes are the grid's, not the function's
- no legends, no themes, no export beyond PNG
- `numpy` is optional. Without it `render` returns a flat `memoryview` of
  `height*width*4` bytes instead of an array; `save_png` works either way

## In a cube, or across the whole view

Two ways to draw the same function, and one switch between them.

**In a cube** (the default) the formula is evaluated over the rectangle you
type, and the plot is drawn inside a box with that rectangle as its floor. The
edges are real - they are where you said the picture ends - so nothing is hidden
and nothing dissolves. Sampling is even across the region.

**Across the view** the plot has no edges at all. The region is worked out from
where the camera stands and where it looks, sampling follows the screen (dense
underfoot, sparse towards the horizon), and the far edge dissolves into the
background because it is the edge of the sampling, not of the function.

```python
s.region_mode = "declared"   # default: a cube
s.region_mode = "view"       # an endless plane
```

Everything else is shared. One evaluator, one renderer, one camera, one set of
gestures - what changes is a single answer to a single question: *who decides
the region?* From that answer follow the sampling, the fade, and whose edges
those are. Nothing else in the pipeline knows which mode it is in.

The endless plane needs a camera given as a point in problem coordinates
(`set_camera_at`): its region is a frustum cut, and an orbit camera has no such
point - it stands relative to a box, the box comes from the region, and the
region would come from the camera. The library refuses that combination rather
than guessing.

## Turning and orbiting are two gestures, not one

The camera in the viewer is a person standing on the ground: it has a spot it
stands on and a height above the plane. **Turning** moves neither - it only
changes where that person looks.

**Orbiting** is the other thing: circling the plot while keeping your distance
from it. It cannot be the same gesture, and not for want of trying. Circling at
a *constant height* forces the distance to change, because that distance is
`h / sin(tilt)`: drop your gaze toward the horizon and the radius balloons;
raise it and the camera drifts into the surface. So an orbit holds the *radius*
and lets the height follow - the exact opposite of what turning does.

Hence two positions on the control, and <kbd>alt</kbd>-drag as a shortcut for
the second. Neither gesture accumulates: both read the cursor's position, not
the path it travelled, so returning the cursor returns the view.

## Contours, because a shade is not a number

By default the relief is drawn the way a map draws hills and gullies: lines of
equal height, spaced by a round number, with every fifth line heavier.

```python
s.shading = "contours"     # default
s.shading = "colour"       # the height ramp alone
s.shading = "both"         # ramp for the shape, lines for the numbers
s.contour_step = 0.5       # 0 means "pick a round one for me"
```

Colour shows the shape instantly, which is why it is still there. What it
cannot do is let you *count*: no one reads a value off a shade. A contour is a
number you can put a finger on, and the scale beside the plot shows the very
same lines at the very same heights, so the two never disagree.

Lines keep a constant thickness on the screen rather than in the world, and two
degenerate cases are left blank on purpose: ground so steep that the lines
would run closer than a pixel, and a plateau lying exactly on a contour level.
Maps leave both blank too.

## Holes are holes

Where the formula has no finite value - `1/x` at zero, `ln` of a negative
number - the cell is **left out**. The surface gets a hole instead of a slope
that does not exist. Pulling such a point to the edge of the box would draw a
lie, and a plot that hides a singularity is worse than one that shows a gap.

## Errors arrive where the mistake was made

```python
>>> s.formula = "x +* "
nashira3d.Nashira3DError: ERR_FORMULA: the formula did not parse
```

Not three calls later, at render time. A rejected assignment also leaves the
previous formula in place: one typo does not break a session you have already
set up.

## Building from source

You need Free Pascal 3.2.2 and the parser, cloned at the tag the release was
built against:

```
git clone --branch v1.3.4 --depth 1     https://github.com/pisarev/pascal-mathparser.git thirdparty/pascal-mathparser
```

Then, on Linux:

```
sudo apt-get install -y fpc libegl-dev
core/build_linux.sh
```

On Windows:

```
powershell -ExecutionPolicy Bypass -File coreuild_windows.ps1
```

`-ExecutionPolicy Bypass` is what lets a downloaded script run under the default
policy, and it holds for that one run only. Typing the script name on its own
does nothing: `cmd` hands a `.ps1` to whatever program is associated with the
extension, usually an editor, and there is no error to explain it.

Set `FPC_EXE` if the compiler is not on the path.

To build the wheel afterwards:

```
python build_wheel.py
```

It copies the compiled library into the package first. Skipping that step
produces a wheel that installs and then fails on the first call.

## Looking at it

There is a browser viewer in `web/`. It is a development tool, not part of the
wheel.

    python web/bridge.py
    # then open http://localhost:8770/

The page sends the formula and the camera to the bridge and displays the frame
the library rendered - the same bytes `render` hands to any other host. The
parsing is done by the library, not by the page.

Drag to rotate, wheel to zoom, right-drag (or shift-drag) to move the plot
anywhere in the frame. The box the surface is drawn in is not fixed: set its
width, depth and height separately to stretch a shallow ripple into something
you can actually see, or to flatten the base into a wide plate. Quality during
motion is a setting, not a rule - it can be kept at full. Frame resolution is a setting: the default follows the
screen's own pixel density, and the top setting renders at twice that and lets
the browser scale it down, which is where the smooth edges come from.

The page computes nothing. It once carried a small JavaScript parser so it
could draw without the bridge; that was removed after measuring what it was
worth. It bought no speed - 0.227 microseconds per grid node against the
library's 0.245 - and it cost correctness: a 31-item vocabulary probe found
nine divergences. The page accepted `atan`, `asin`, `log`, `pow`, `mod` and `e`,
which the library does not know under those names, and did not know `if()`,
`x mod 2`, `lg` or `arctan2`, which the library does. A second parser that
agrees on easy formulas and disagrees on the rest is worse than no picture at
all. Without the bridge the page now says so.

## Licence

MIT. See `LICENSE`.

Contributions are welcome under the terms in `CONTRIBUTING.md`: you keep the
copyright to what you wrote, and the project keeps the ability to change its
licence later without hunting down every past contributor.
