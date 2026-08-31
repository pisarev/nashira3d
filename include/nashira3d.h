/* nashira3d.h - Nashira3D. The flat C interface. Table version: 1.
 *
 * WHAT CROSSES THE SEAM: the formula, the domain, the quality, the camera.
 * Not the mesh and not the pixels. As long as no mesh has crossed it, anything
 * behind the seam can change: a uniform grid for an adaptive one, work on the
 * processor for work on the card.
 *
 * WHAT IS DELIBERATELY ABSENT: OpenGL objects, structures with a layout,
 * exceptions. An exception that crosses the seam cannot be debugged.
 *
 * THREADS: every call must come from ONE AND THE SAME thread, the one that
 * called render first. Not "one at a time" - the same one. An OpenGL context
 * belongs to the thread that created it, and on any other thread the card
 * refuses in silence. A lock around the calls does not help.
 *
 * The first caller outside the library ran into this, and the wording here
 * changed as a result:
 * web/bridge.py handed requests out across threads and held its lock honestly,
 * and got ERR_GPU with status 0 from glCheckFramebufferStatus - the sign that
 * there is no current context on the thread at all. There can still be many
 * sessions, but one thread serves them all. This rule may be relaxed later;
 * it may not be tightened.
 */
#ifndef NASHIRA3D_H
#define NASHIRA3D_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct nsh_session nsh_session;   /* opaque on purpose */

typedef enum {
  NSH_OK              = 0,
  NSH_ERR_ARG         = 1,   /* an argument is out of range */
  NSH_ERR_FORMULA     = 2,   /* the formula did not parse */
  NSH_ERR_GPU         = 3,   /* the context or the drawing refused */
  NSH_ERR_MEMORY      = 4,
  NSH_ERR_STATE       = 5,   /* the calls came in the wrong order */
  NSH_ERR_UNSUPPORTED = 6
} nsh_status;

typedef struct {
  uint32_t size;             /* sizeof(nsh_api_v1): guards against a mismatch */

  /* THE ORDER OF THE MEMBERS IS PART OF THE CONTRACT. Anything new is APPENDED
     AT THE END, before the closing brace. An insertion in the middle shifts
     everything below it, and a build made elsewhere starts calling the
     neighbouring function - silently, without a single build error. That is
     what happened once: fit_z landed before set_light and had to be moved back
     to the end. The order is written down in include/abi-order.txt and a probe
     checks it. */

  nsh_status  (*create)(nsh_session** out);
  void        (*destroy)(nsh_session*);

  /* the source: a formula in UTF-8, with x and y as the variables */
  nsh_status  (*set_formula)(nsh_session*, const char* utf8);
  nsh_status  (*set_domain)(nsh_session*, double x0, double x1,
                                          double y0, double y1);

  /* QUALITY, not a node count: 0 to 100. Today it turns into a uniform grid;
     tomorrow into a curvature threshold that puts vertices exactly on the
     extrema. Your code does not change by a single letter. */
  nsh_status  (*set_quality)(nsh_session*, int32_t quality);

  /* the camera: spherical around the POINT IT LOOKS AT, angles in radians */
  nsh_status  (*set_camera)(nsh_session*, double azimuth, double elevation,
                                          double distance, double fov);

  /* MOVE the point the camera looks at, in the plane of the frame, in
     fractions of the normalised box: dx to the right, dy up the screen.
     (0,0) puts the surface in the middle.

     Why in the plane of the frame rather than in the coordinates of the
     domain: the mouse is dragged ACROSS THE SCREEN, and the movement has to go
     where the hand goes. Converting that into world axes depends on the
     rotation of the camera, so it lives here rather than in your code. */
  nsh_status  (*set_pan)(nsh_session*, double dx, double dy);

  /* THE PROPORTIONS OF THE BOX the plot is fitted into: a half-size along each
     axis. The default (1, 1, 0.3) gives a square floor and a third of that in
     height.

     This is NOT the range of values: the domain comes from set_domain, and
     this only says what shape the drawn box will have. Stretching z twofold to
     see a shallow ripple, or flattening the floor into a wide slab, are
     ordinary wishes, and until now there was nothing to grant them with. */
  nsh_status  (*set_box)(nsh_session*, double sx, double sy, double sz);

  /* FIT TO THE FRAME. While it is on, and it is on by default, the distance of
     the camera is chosen on every frame so that the box and its labels fill
     the frame. The distance passed to set_camera then serves only as a
     starting guess.

     Turning it off makes sense when a person is driving the distance: the
     fitting would undo their movement at once. */
  nsh_status  (*set_fit)(nsh_session*, int32_t on);

  /* THE MESH laid on the surface itself: lines along constant x and constant
     y, about twelve to a side. On by default.

     It does what the wireframe box used to do, and does it better: the box
     says where the edges are, the mesh says where the axes run and how the
     relief lies between them. No segment is drawn across a hole: a line pulled
     over a gap would claim there is surface where there is none. */
  nsh_status  (*set_grid)(nsh_session*, int32_t on);

  /* HOW LARGE the sheet sits in the frame. One means the enclosing sphere is
     exactly fitted vertically; above one the surface runs past the edges and
     no emptiness is left around it.

     The number comes from outside, and not out of laziness. The scale must not
     depend on the point of view, or the picture jumps as the camera turns. But
     a flat sheet foreshortens as it tilts, and one number cannot both hold
     still through a rotation and fill the frame at any tilt. The choice stays
     with whoever is looking. */
  nsh_status  (*set_fill)(nsh_session*, double k);

  nsh_status  (*set_light)(nsh_session*, double azimuth, double elevation);
  nsh_status  (*set_axes)(nsh_session*, int32_t on);

  /* the frame: THE CALLER provides the buffer, RGBA8, exactly w*h*4 bytes. The
     library allocates nothing and owns nothing, so no question of ownership
     arises. */
  nsh_status  (*render)(nsh_session*, int32_t w, int32_t h, uint8_t* rgba);

  /* the last error in words, UTF-8, valid until the next call on that session */
  const char* (*last_error)(nsh_session*);
  const char* (*version)(void);

  /* RECOMPUTE the vertical scale from what is in view right now.

     The scale in height is a property of the scene, not a consequence of the
     frame. It is computed once when the formula changes and frozen after that:
     moving the camera does not touch it. Otherwise the camera would change the
     GEOMETRY of the plot - move back, bring a new peak into the domain, and
     the whole surface sinks.

     This call is the only way to recompute the scale without changing the
     formula. The same range drives the colour, so the colours do not drift
     with the height either. */
  nsh_status  (*fit_z)(nsh_session*);

  /* PARTS OF THE FRAME THAT ARE TAKEN: x, y, width, height, and so on in
     fours. count is the number of INTEGERS, that is four times the number of
     rectangles.

     Labels are placed where there is room, and only the caller knows where
     there is room: their panels lie OVER the frame and the library cannot see
     them. The hint is optional - without it the frame comes out a little
     worse, but it comes out. */
  nsh_status  (*set_obstacles)(nsh_session*, const int32_t* rects, int32_t count);

  /* THE CAMERA AS A STANDING POINT.

     Drop a perpendicular from the camera to the reference plane, and it is
     THAT height which holds as the camera tilts. The older camera orbited, and
     there the height followed from the distance and the tilt: tilting made the
     camera dive towards the plane.

         position = (cx, cy, z0 + h)
         tilting  changes only azimuth and elevation
         panning  changes only cx and cy
         the wheel changes only h

     h IS SIGNED: positive is above, zero puts the camera IN the plane,
     negative is below. Zero is allowed, and there is NO forbidden neighbourhood
     around it.

     The reference plane is the middle of the frozen range in z. This camera has
     no distance at all. The call puts the session into a standing camera, and
     set_camera brings it back; whichever call came last is the one in force.

     This call does NOT touch the domain: where the domain comes from is what
     set_region_mode says. A standing camera used to switch the domain
     calculation on by itself, and because of that you could neither walk about
     inside a declared domain nor explain in one place how a cube differs from
     a plane.

     With this camera THE LIBRARY works out the domain: it intersects the view
     frustum with the slab the surface lies in, projects onto XY, and takes the
     enclosing rectangle. set_domain is not needed then. */
  nsh_status  (*set_camera_at)(nsh_session*, double cx, double cy, double h,
                               double azimuth, double elevation, double fov);

  /* THE FURTHEST DISTANCE, in the units of the problem. A ray that runs along
     the plane, or above the horizon, meets it infinitely far away; this limit
     makes the frustum finite. It is named as a limit on purpose rather than
     hidden inside the trigonometry. Zero takes the default: eight heights
     together with the thickness of the slab. */
  nsh_status  (*set_max_extent)(nsh_session*, double extent);

  /* VERTICAL EXAGGERATION, a multiplier on the frozen one. One leaves it as it
     was frozen when the formula changed. Above one lifts a shallow relief. */
  nsh_status  (*set_z_exaggeration)(nsh_session*, double k);

  /* THE DOMAIN THAT IS IN VIEW: x0, x1, y0, y1, four doubles in a row. Only
     for the camera as a standing point. The caller needs it to show numbers. */
  nsh_status  (*view_region)(nsh_session*, int32_t w, int32_t h, double* out4);

  /* AUTO Z. Off by default, and that is a decision rather than caution:
     refitting all the time makes the geometry a consequence of the camera, and
     the surface jumps the moment a new peak comes into view - the very thing
     being avoided.

     Switched on, it compares the range that is NEEDED with the frozen one. A
     refit is allowed once the ratio passes 2.0; after it fires it is locked
     until the ratio falls back below 1.5. The colour range is recomputed in the
     SAME step: there is no separate floating range for colour. */
  nsh_status  (*set_auto_z)(nsh_session*, int32_t on);

  /* Whether the automatic refit fired on the last frame. Reading it CLEARS it:
     the caller needs to show a short notice once. */
  int32_t     (*auto_z_fired)(nsh_session*);

  /* HOW THE RELIEF IS SHOWN: 0 contour lines, 1 colour, 2 both.

     0 by default. Colour gives the shape at once, but you cannot COUNT with
     it: the eye does not turn a shade into a number. A line of equal height is
     a number, and it can be counted off with a finger, as on a map.

     step is the distance in height between the lines, in the units of the
     formula; 0 means "choose one": the nearest step of the form 1, 2, or 5
     times a power of ten, such that about fifteen lines come out. The scale at
     the side shows THE SAME drawing - under contour lines it stops being a
     colour scale and becomes a ruler with ticks at those same heights.

     It does NOT rebuild the mesh: the drawing is worked out in the shader. */
  nsh_status  (*set_shading)(nsh_session*, int32_t mode, double step);

  /* WHERE THE DOMAIN COMES FROM: 0 a person declared it, 1 the library works
     it out from the point of view. 0 by default.

     This is the ONLY difference between the two ways of drawing, and
     everything else follows from it:

       0 - a cube. The domain is the one set_domain gave. Sampling is uniform.
           The edges of the domain are visible and are part of the subject, so
           nothing dissolves in the distance. set_axes draws the box with its
           numbering.
       1 - an endless plane. The domain is the intersection of the view frustum
           with the slab the surface lies in. Sampling follows the density on
           screen: nodes crowd underfoot and thin out towards the horizon. The
           far edge of the sheet dissolves into the background, because that is
           the edge of OUR sampling and not an edge of the function.

     The computation and the drawing are the same either way: the formula, the
     mesh, the light, the contour lines, the labels, and the scale all go down
     one path.

     Mode 1 needs a camera given as a POINT (set_camera_at): the view frustum is
     built by a camera in the coordinates of the problem, and an orbiting camera
     has no such point - it stands relative to the box, the box follows from the
     domain, and the domain from the camera. The impossible combination is
     refused when drawing rather than when setting, so that the order of the
     calls does not matter. */
  nsh_status  (*set_region_mode)(nsh_session*, int32_t mode);
} nsh_api_v1;

/* The only export of the library. Ask for 1 and you get v1 forever. */
const nsh_api_v1* nsh_get_api(uint32_t version);

#ifdef __cplusplus
}
#endif
#endif /* NASHIRA3D_H */
