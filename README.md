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

There is a page that runs the real thing in a browser -
**[the live demo](https://pisarev.github.io/nashira3d-live/)**. The mesh you
turn there is built by `core/nsh_surface.pas` from this repository, compiled to
WebAssembly; only the drawing belongs to the browser.

## What makes it different

Plotting libraries take an **array** of samples. This one takes the **function**.

The difference is not cosmetic. Given `f` rather than its samples, a renderer
can sample where the surface actually bends, place a vertex exactly on a peak
instead of near it, and re-evaluate when you zoom instead of interpolating a
mesh that was fixed long ago. None of that is possible once the function has
been thrown away.

Version 0.2 does not use curvature-adaptive sampling on its default path, and
does not hunt for extrema. In a declared
region it uses an even grid; across the view the sampling lines are placed by
screen density, as described below. What it does already is keep the door open:
the interface speaks of `quality`, not of a grid size, so the sampling can
change without a single line changing on your side.

The formula is parsed and **compiled to machine code** before evaluation, so a
grid of sixty-five thousand points - what the top quality asks for - is not
sixty-five thousand interpreted expressions.

## Install

Wheels for Windows and Linux are attached to every entry on the
[releases page](https://github.com/pisarev/nashira3d/releases). Take the one
for your platform and install it:

```
python -m pip install ./nashira3d-<version>-py3-none-win_amd64.whl
```

`python -m pip` rather than `pip`, and not out of pedantry: on a machine with
conda or pyenv the two are often different installations. A plain `pip install`
then reports success while `import nashira3d` answers `ModuleNotFoundError`,
because the package went to an interpreter other than the one you are running.
Written this way, the interpreter that installs is the interpreter that imports.

The version is part of the file name, so copy it from the file you downloaded
rather than from this line: a version written into a README is out of date by
the next release.

The wheel carries the compiled core. There is no compiler, no CMake and no
system package to install. The Linux wheel is tagged `linux_x86_64` rather than
`manylinux`, and it needs a C library no older than the machine it was built
on: Ubuntu 22.04 and newer.

Nashira3D is not on PyPI yet. The name there is taken for good once it is
used, and version 0.2 is still moving, so the registry can wait until the
interface has settled. Once the native core has been built, packaging it into
a wheel takes one command; the whole path is described under
[Building from source](#building-from-source).

## What it needs

- Windows or Linux on x86-64. Those are the two wheels there are
  (`win_amd64` and `linux_x86_64`); ARM64 is not among them
- a driver with **OpenGL 3.3 core**. On Linux the offscreen context is created
  through EGL, so no display, no X server and no desktop session are required.
  That is what makes headless use over SSH and inside a container possible -
  provided a working EGL implementation is there to talk to, whether it is a
  driver or a software renderer.

On a machine with no graphics device of its own, EGL may refuse to start on the
platform it picks by default. Where the surfaceless platform is supported,
naming it may settle the matter:

```
export EGL_PLATFORM=surfaceless
```

It is worth trying whenever `render` answers `ERR_GPU` and the message names
`eglInitialize`. That is the library reporting what EGL told it, not a failure
of its own, and it says so rather than drawing something else.

## What version 0.2 does

- one surface `z = f(x, y)` over a rectangular domain
- sampling set by `quality` from 0 to 100: a declared region gets an even grid,
  a view-derived one redistributes the lines with perspective
- one light, depth testing, and a choice of how the relief is drawn:
  contour lines by default, a height colour ramp, or both together
- a box with ticks and numbered axes, labelled on the edges nearest the viewer
- a frame returned as a `numpy` array, or written straight to PNG

## What it does not do yet

Said plainly, because a list of features is worth less than an honest list of
gaps:

- no window and no mouse: a frame is returned, not shown
- one surface per scene - no overlays, no point clouds, no volumes
- no curvature-adaptive sampling on the default path: a peak between two grid
  nodes is still missed, and the reported extremes are the grid's, not the
  function's. An experimental sampler by curvature is present in the build -
  `core/nsh_adaptive.pas` - but it is switched on by an environment variable,
  is no part of the contract, and is off unless you ask for it
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
where the camera stands and where it looks, and the sampling follows the screen:
lines crowd underfoot and thin out towards the horizon, so the sampling is
denser in world space near the camera, where a given world-space interval
covers more screen pixels. The measurement is in `tests/cam_probe`, which is in this
repository and prints it: with the camera 1.5 above the plane, tilted 0.30 rad
and looking along y, 55 of the 64 lines over the segment from -20 to 5 land in
the quarter nearest the camera. The far edge dissolves into the background because it is the
edge of the sampling and not of the function - and the dissolve is carried all
the way to the background exactly at that edge, so the edge itself never shows.

```python
s.region_mode = "declared"   # default: a cube
s.region_mode = "view"       # an endless plane
```

Everything else is shared. One evaluator, one renderer, one camera, one set of
gestures - what changes is a single answer to a single question: *who decides
the region?* From that answer follow the extent, the fade, and whose edges those
are. Nothing else in the pipeline knows which mode it is in.

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

Hence the viewer offers the two as separate gestures - a switch in the panel
picks which one a drag performs, and <kbd>alt</kbd>-drag is a shortcut for the
second. Neither gesture accumulates: both read the cursor's position, not
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

Where the formula has no finite value at a node - `ln` of a negative number,
`sqrt` of one - the cell is **left out**. The surface gets a hole instead of a
slope that does not exist. Pulling such a point to the edge of the box would
draw a lie, and a plot that hides a singularity is worse than one that shows a
gap. On `ln(x)` over a square domain about the origin about half the cells go,
which is what the domain says they should: half of it has `x` below zero. The
count is reported rather than guessed at - the browser demo prints it under the
plot, and 9,180 cells of 18,225 went on the run this line was written from.

A singularity that falls *between* nodes is a different matter, and the honest
answer is that it is not seen. `1/x` over `(-2, 2)` never lands on zero - the
grid is even and the node count works out so that no node sits there - so
nothing is undefined and nothing is left out. What you get is a very steep
slope, not a gap. The library reports what it found at the nodes; it does not
go looking between them.

## Formula errors are reported immediately

```python
>>> s.formula = "x +* "
nashira3d.Nashira3DError: ERR_FORMULA: the formula did not parse
```

Not three calls later, at render time. A rejected assignment also leaves the
previous formula in place: one typo does not break a session you have already
set up.

Not every refusal can arrive that early. A combination that only becomes
impossible once both halves are set - an orbit camera together with the region
taken from the view - is accepted by each call on its own and refused by
`render`, with `ERR_STATE` naming what is missing.

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
powershell -ExecutionPolicy Bypass -File core/build_windows.ps1
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

If the core came from a wheel rather than from a build of your own, the bridge
will not find it and will say so, naming both places it looked. It searches
next to its own copy of the package - the one in this source tree - while the
wheel put the library in `site-packages`. Put a copy where it looks:

    # Windows
    copy "%CONDA_PREFIX%\Lib\site-packages\nashira3d\nashira3d.dll" python\nashira3d\

    # Linux
    cp "$(python -c 'import nashira3d,os;print(os.path.dirname(nashira3d.__file__))')/libnashira3d.so" python/nashira3d/

Setting `NASHIRA3D_LIB` to that same file works too, and takes precedence over
every other place the binding looks.

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
worth. It cost correctness: on a vocabulary probe the two
disagreed word for word. The page accepted `atan`, `asin`, `log`, `pow`, `mod` and `e`,
which the library does not know under those names, and did not know `if()`,
`x mod 2`, `lg` or `arctan2`, which the library does. A second parser that
agrees on easy formulas and disagrees on the rest is worse than no picture at
all. Without the bridge the page now says so.

## Licence

MIT. See `LICENSE`.

Contributions are welcome under the terms in `CONTRIBUTING.md`: you keep the
copyright to what you wrote, and the project keeps the ability to change its
licence later without hunting down every past contributor.
