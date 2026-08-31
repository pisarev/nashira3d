"""The link to the core. cffi in ABI mode, so nobody needs a compiler.

The declarations below have to repeat include/nashira3d.h word for word. For
now that rests on attention; in 1.0.0 a check will stand here that compares
them by machine - a mismatch here is not a refusal but rubbish in someone
else's pointers.
"""

import os
import sys
from cffi import FFI

CDEF = """
typedef struct nsh_session nsh_session;

typedef struct {
  uint32_t size;
  int         (*create)(nsh_session** out);
  void        (*destroy)(nsh_session*);
  int         (*set_formula)(nsh_session*, const char*);
  int         (*set_domain)(nsh_session*, double, double, double, double);
  int         (*set_quality)(nsh_session*, int32_t);
  int         (*set_camera)(nsh_session*, double, double, double, double);
  int         (*set_pan)(nsh_session*, double, double);
  int         (*set_box)(nsh_session*, double, double, double);
  int         (*set_fit)(nsh_session*, int32_t);
  int         (*set_grid)(nsh_session*, int32_t);
  int         (*set_fill)(nsh_session*, double);
  int         (*set_light)(nsh_session*, double, double);
  int         (*set_axes)(nsh_session*, int32_t);
  int         (*render)(nsh_session*, int32_t, int32_t, uint8_t*);
  const char* (*last_error)(nsh_session*);
  const char* (*version)(void);
  int         (*fit_z)(nsh_session*);
  int         (*set_obstacles)(nsh_session*, const int32_t*, int32_t);
  int         (*set_camera_at)(nsh_session*, double, double, double,
                               double, double, double);
  int         (*set_max_extent)(nsh_session*, double);
  int         (*set_z_exaggeration)(nsh_session*, double);
  int         (*view_region)(nsh_session*, int32_t, int32_t, double*);
  int         (*set_auto_z)(nsh_session*, int32_t);
  int32_t     (*auto_z_fired)(nsh_session*);
  int         (*set_shading)(nsh_session*, int32_t, double);
  int         (*set_region_mode)(nsh_session*, int32_t);
} nsh_api_v1;

const nsh_api_v1* nsh_get_api(uint32_t version);
"""

OK              = 0
ERR_ARG         = 1
ERR_FORMULA     = 2
ERR_GPU         = 3
ERR_MEMORY      = 4
ERR_STATE       = 5
ERR_UNSUPPORTED = 6

NAMES = {
    OK: "OK", ERR_ARG: "ERR_ARG", ERR_FORMULA: "ERR_FORMULA",
    ERR_GPU: "ERR_GPU", ERR_MEMORY: "ERR_MEMORY", ERR_STATE: "ERR_STATE",
    ERR_UNSUPPORTED: "ERR_UNSUPPORTED",
}

ffi = FFI()
ffi.cdef(CDEF)


def _candidates():
    """Where to look for the library. The environment variable comes first:
    development runs on it."""
    env = os.environ.get("NASHIRA3D_LIB")
    if env:
        yield env
    name = "nashira3d.dll" if sys.platform == "win32" else "libnashira3d.so"
    here = os.path.dirname(os.path.abspath(__file__))
    yield os.path.join(here, name)
    root = os.path.dirname(os.path.dirname(here))
    sub = "win64" if sys.platform == "win32" else "linux64"
    yield os.path.join(root, "build", sub, name)


def load():
    """Return (lib, api). A refusal names EVERY path it looked at, not one."""
    looked = []
    for path in _candidates():
        looked.append(path)
        if not os.path.isfile(path):
            continue
        lib = ffi.dlopen(path)
        api = lib.nsh_get_api(1)
        if api == ffi.NULL:
            raise OSError("%s: nsh_get_api(1) returned NULL" % path)
        want = ffi.sizeof("nsh_api_v1")
        if api.size != want:
            raise OSError(
                "%s: the table is %d bytes, expected %d - the builds disagree"
                % (path, api.size, want))
        return lib, api
    raise OSError("library not found, looked at:\n  " + "\n  ".join(looked))
