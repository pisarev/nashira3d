"""The bridge between the page and the real library.

WHY. A viewer that parses the formula itself and builds the mesh itself shows
ITS OWN arithmetic, not the library's. For a quick look that will do; for a
check it will not: a substitute parser may agree with the core on simple
formulas and disagree on the ones the whole thing was started for.

Nothing is computed here. The page sends a formula and a camera position, the
bridge passes them into nsh_api_v1 and returns the frame the core drew - the
same bytes that go to a user of the library. TJitParser does the parsing,
nsh_surface builds the mesh, nsh_render draws the picture.

To run:  python web/bridge.py  [port]
Then:    http://localhost:8770/
"""

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'python'))

import nashira3d

# An OpenGL context belongs to the thread that created it. A lock is NOT ENOUGH
# here: on another thread the card's calls do not throw, they refuse in silence
# - glCheckFramebufferStatus returns 0 and ERR_GPU goes out. So every call into
# the core is made by one dedicated thread, and the request handlers only put
# jobs into its queue.
#
# Found right here: the server handed requests out across threads and held the
# lock, as the header told it to, and still got a refusal. The wording in
# nashira3d.h had to be corrected - see the THREADS section.
import queue
import threading

# What this bridge can do. The number grows when a HANDLE appears that the page
# can use. It is needed for this: the process lives a long time while it reads
# the page from disk on every request - and a pair easily arises where the look
# is new and the behaviour is old. Such a disagreement is silent: the page
# sends a parameter, the bridge does not know it and quietly drops it. An
# evening has already gone on this once, working out why the move did not work.
# What the bridge serves besides the page and the frames. The list is closed -
# see serve_static.
STATIC = {
    '/logo.png':    ('logo.png',    'image/png'),
    '/favicon.png': ('favicon.png', 'image/png'),
    '/logo.ico':    ('logo.ico',    'image/x-icon'),
    '/logo-mark.png': ('logo-mark.png', 'image/png'),
    '/samples.png': ('samples.png', 'image/png'),
}

BRIDGE_API = 9
FEATURES = ['pan', 'size-declared', 'box', 'fit', 'fit-z', 'obstacles',
            'stand', 'region', 'auto-z', 'shading', 'region-mode']

JOBS = queue.Queue()
STATS = {'frames': 0, 'render_ms': 0.0, 'errors': 0}
READY = threading.Event()
FAILED = [None]


def in_gl(fn):
    """Run fn on the thread that owns the context and wait for the result."""
    box = {'done': threading.Event()}
    JOBS.put((fn, box))
    box['done'].wait()
    if 'error' in box:
        raise box['error']
    return box['result']


def gl_thread():
    try:
        session = nashira3d.Session(formula='0', quality=50)
        session.render(64, 64)          # the context and the first compile happen here
    except Exception as e:              # noqa: BLE001 - the text is needed outside, not the type
        FAILED[0] = e
        READY.set()
        return
    READY.set()
    while True:
        fn, box = JOBS.get()
        if fn is None:
            return
        try:
            box['result'] = fn(session)
        except Exception as e:          # noqa: BLE001
            box['error'] = e
        finally:
            box['done'].set()


def rects(text):
    """Parse 'x,y,w,h;x,y,w,h' into a flat list of integers.

    Rubbish is dropped in silence: this is a hint for placing the labels, not a
    contract. Without it the frame comes out slightly worse, but it comes
    out."""
    out = []
    for part in text.split(';'):
        bits = part.split(',')
        if len(bits) != 4:
            continue
        try:
            v = [int(round(float(b))) for b in bits]
        except ValueError:
            continue
        if v[2] > 0 and v[3] > 0:
            out.extend(v)
    return out[:64]


def num(q, name, default):
    try:
        return float(q.get(name, [default])[0])
    except (TypeError, ValueError):
        return float(default)


class Handler(BaseHTTPRequestHandler):

    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        pass

    def send_bytes(self, code, ctype, body, extra=None):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (extra or {}).items():
            self.send_header(k, str(v))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, code, text, ctype='text/plain; charset=utf-8'):
        self.send_bytes(code, ctype, text.encode('utf-8'))

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ('/', '/preview.html'):
            return self.serve_page()
        if u.path in STATIC:
            return self.serve_static(u.path)
        if u.path == '/health':
            return self.serve_health()
        if u.path == '/frame':
            return self.serve_frame(parse_qs(u.query))
        self.send_text(404, 'no such path')

    def serve_page(self):
        path = os.path.join(HERE, 'preview.html')
        try:
            with open(path, 'rb') as f:
                body = f.read()
        except OSError as e:
            return self.send_text(500, 'preview.html is not readable: %s' % e)
        # The page is served WITH NO CACHE. Otherwise after an edit the browser
        # shows the old one: the frames are requested with no-store while the
        # page itself is not, and a person sees the old behaviour with a new
        # core.
        self.send_bytes(200, 'text/html; charset=utf-8', body,
                        {'Cache-Control': 'no-store, must-revalidate',
                         'Pragma': 'no-cache'})

    def serve_static(self, path):
        """Serve one of the known files next to the page.

        The list is closed and the path from the request is NOT JOINED to the
        directory: otherwise /logo.png turns into /../../anything. The bridge
        lives on the loopback interface, but that does not stop a hole from
        being a hole."""
        name, ctype = STATIC[path]
        try:
            with open(os.path.join(HERE, name), 'rb') as f:
                body = f.read()
        except OSError as e:
            return self.send_text(404, 'no file %s: %s' % (name, e))
        self.send_bytes(200, ctype, body, {'Cache-Control': 'max-age=3600'})

    def serve_health(self):
        try:
            if FAILED[0] is not None:
                raise FAILED[0]
            v = nashira3d.version()
            body = {'ok': True, 'version': v,
                    'bridge': BRIDGE_API, 'features': FEATURES,
                    'frames': STATS['frames'],
                    'avg_ms': round(STATS['render_ms'] / STATS['frames'], 2)
                              if STATS['frames'] else None}
        except Exception as e:
            body = {'ok': False, 'error': str(e)}
        self.send_text(200, json.dumps(body, ensure_ascii=False),
                       'application/json; charset=utf-8')

    def serve_frame(self, q):
        # A ceiling is needed: a frame of 8000x8000 is 256 MB for one picture.
        # But a clamp has to be ANNOUNCED rather than silently returning
        # another size: the page has to draw what the frame declares about
        # itself, not what it asked for.
        w = max(16, min(4096, int(num(q, 'w', 640))))
        h = max(16, min(4096, int(num(q, 'h', 440))))
        formula = (q.get('f', ['0'])[0] or '0')

        def job(s):
            # The order matters: the formula is checked by the core, and if it
            # is unsound the previous one stays alive. That is exactly the
            # behaviour that has to be shown.
            s.formula = formula
            s.domain = (num(q, 'x0', -1), num(q, 'x1', 1),
                        num(q, 'y0', -1), num(q, 'y1', 1))
            s.quality = int(num(q, 'q', 50))
            # WHERE THE DOMAIN COMES FROM is the one difference between the
            # cube and the infinite plane. It is set BEFORE the camera: the
            # core checks the combination at drawing time and the order of the
            # calls does not matter, but it reads better top to bottom when
            # what is being drawn is said first.
            s.region_mode = (q.get('region', ['declared'])[0] or 'declared')

            # The camera. A standing one is set only on an explicit flag, not
            # on the presence of the fields; the else branch takes it back to
            # orbit - in the core the call that came last is the one in force.
            if num(q, 'stand', 0) >= 0.5:
                s.stand(num(q, 'camx', 0), num(q, 'camy', 0), num(q, 'camh', 3),
                        num(q, 'az', 0.9), num(q, 'el', 0.45), num(q, 'fov', 0.9))
                # A standing point has no box proportions: the axes are not
                # distorted. The box-height field does not vanish, though - it
                # takes on its own meaning, the vertical exaggeration. The old
                # 0.3 means one, that is 'as frozen when the formula changed'.
                s.z_exaggeration = max(0.02, num(q, 'bz', 0.3) / 0.3)
            else:
                s.camera = (num(q, 'az', 0.9), num(q, 'el', 0.45),
                            num(q, 'dist', 3.4), num(q, 'fov', 0.9))
            s.auto_z = num(q, 'autoz', 0) >= 0.5
            s.pan = (num(q, 'panx', 0), num(q, 'pany', 0))
            s.box = (num(q, 'bx', 1), num(q, 'by', 1), num(q, 'bz', 0.3))
            s.fit = num(q, 'fit', 1) >= 0.5
            s.light = (num(q, 'laz', 2.2), num(q, 'lel', 0.9))
            s.axes = num(q, 'axes', 1) >= 0.5
            s.grid = num(q, 'grid', 1) >= 0.5

            # How the relief is shown. By name, not by number: 'shade=2' in the
            # bridge log is unreadable, 'shade=both' reads without a reference
            # table.
            s.shading = (q.get('shade', ['contours'])[0] or 'contours')
            s.contour_step = max(0.0, num(q, 'cstep', 0))

            # The rectangles of the page's panels. The core places the labels
            # in the free places of the frame, and only the page knows which
            # places are free: the panels lie OVER the frame and the core
            # cannot see them.
            s.obstacles = rects(q.get('obst', [''])[0])

            # A one-off action, not a setting: the page sends it once, and the
            # order matters here - the domain and the formula are already set,
            # so the range is recomputed over the very mesh that will be seen.
            if num(q, 'fitz', 0) >= 0.5:
                s.fit_z()
            t0 = time.perf_counter()
            buf = s.render(w, h)
            ms = (time.perf_counter() - t0) * 1000.0

            # The core WORKS OUT the domain, and the page needs it as numbers
            # on the screen. An empty domain is not an error of the frame: the
            # camera may have gone below the slab and be looking away from the
            # surface. The frame is legitimate then, merely empty. Whether the
            # auto-fit fired is read IMMEDIATELY after the frame, and goes out.
            fired = s.auto_z_fired()

            reg = None
            if num(q, 'stand', 0) >= 0.5:
                try:
                    reg = s.region(w, h)
                except Exception:       # noqa: BLE001 - an empty domain is not a refusal
                    reg = None
            return buf, ms, reg, fired

        try:
            buf, ms, reg, fired = in_gl(job)
        except Exception as e:          # noqa: BLE001 - the text is needed outside
            STATS['errors'] += 1
            return self.send_text(400, str(e))
        STATS['frames'] += 1
        STATS['render_ms'] += ms

        body = bytes(memoryview(buf).cast('B')) if not isinstance(buf, bytes) else buf
        head = {'X-Width': w, 'X-Height': h,
                'X-Render-Ms': '%.2f' % ms,
                'X-Core-Version': nashira3d.version()}
        if reg is not None:
            head['X-Region'] = ','.join('%.6g' % v for v in reg)
        if fired:
            head['X-Auto-Z'] = 'refitted'
        self.send_bytes(200, 'application/octet-stream', body, head)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8770
    # The core is brought up before the first request: the OpenGL context and
    # the first compile of a formula cost hundreds of milliseconds, and there
    # is no reason to pay them in the middle of a rotation.
    t0 = time.perf_counter()
    threading.Thread(target=gl_thread, daemon=True, name='nashira3d-gl').start()
    READY.wait()
    warm = (time.perf_counter() - t0) * 1000.0
    if FAILED[0] is not None:
        print('the core did not come up:', FAILED[0])
        return

    srv = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print('Nashira3D %s, core warmed up in %.0f ms' % (nashira3d.version(), warm))
    print('page: http://localhost:%d/' % port)
    print('Ctrl+C to stop')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nstopped')


if __name__ == '__main__':
    main()
