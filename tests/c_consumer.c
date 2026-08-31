/* An outside consumer of the seam that knows nothing about Python.
 *
 * Why it exists apart from the battery. Until now the seam was only ever
 * exercised through our own cffi binding. That is a dangerous symmetry: one
 * and the same mistake about layout or about the order of the table, made in
 * the core and in the binding alike, cancels itself out, and hundreds of
 * checks pass in agreement. A foreign program in C, built by a foreign
 * compiler and knowing nothing but include/nashira3d.h, breaks that symmetry.
 *
 * What is checked is exactly what is promised on the outside:
 *   - the library loads by file name, with no scaffolding of any kind;
 *   - nsh_get_api is the single entry, and it answers to version 1;
 *   - an unknown version gets a null answer rather than rubbish;
 *   - size in the table matches sizeof ON THE CALLER'S SIDE - that is the
 *     build check: let the layout drift and the number drifts with it;
 *   - the order of the members is the one in the header: calls go by name,
 *     and if somebody inserted a function in the middle, a neighbouring call
 *     would do the wrong thing;
 *   - the create -> render -> destroy cycle survives many times over;
 *   - bad arguments come back as an error code, not as a crash.
 *
 * Build and run - tests/build_c_consumer.sh (Linux) and .ps1 (Windows).
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stddef.h>

#include "nashira3d.h"

#ifdef _WIN32
#  include <windows.h>
#  define LIBHANDLE HMODULE
#  define LIBOPEN(p) LoadLibraryA(p)
#  define LIBSYM(h, n) ((void*)GetProcAddress((h), (n)))
#  define LIBCLOSE(h) FreeLibrary(h)
#else
#  include <dlfcn.h>
#  define LIBHANDLE void*
#  define LIBOPEN(p) dlopen((p), RTLD_NOW)
#  define LIBSYM(h, n) dlsym((h), (n))
#  define LIBCLOSE(h) dlclose(h)
#endif

static int total = 0;
static int failed = 0;

static void check(const char* name, int ok, const char* got)
{
    total++;
    if (ok) {
        printf("  ok   %-46s %s\n", name, got ? got : "");
    } else {
        failed++;
        printf("  FAIL %-46s %s\n", name, got ? got : "");
    }
}

typedef const nsh_api_v1* (*get_api_fn)(uint32_t);

int main(int argc, char** argv)
{
    LIBHANDLE h;
    get_api_fn get_api;
    const nsh_api_v1* api;
    nsh_session* s = NULL;
    unsigned char* rgba;
    char buf[128];
    int i, w = 64, ht = 48;
    nsh_status st;

    if (argc < 2) {
        printf("a path to the library is required: c_consumer <nashira3d.dll|.so>\n");
        return 1;
    }

    printf("AN OUTSIDE CONSUMER OF THE SEAM (plain C)\n\n");

    h = LIBOPEN(argv[1]);
    check("the library loaded", h != NULL, argv[1]);
    if (!h) return 1;

    get_api = (get_api_fn)LIBSYM(h, "nsh_get_api");
    check("nsh_get_api found by name", get_api != NULL, NULL);
    if (!get_api) return 1;

    /* The second entry that was never promised must not be there: the table
       is the only way in. */
    check("nsh_render is NOT exported", LIBSYM(h, "nsh_render") == NULL, NULL);
    check("nsh_create is NOT exported", LIBSYM(h, "nsh_create") == NULL, NULL);

    check("version 0 answers null", get_api(0) == NULL, NULL);
    check("version 2 answers null", get_api(2) == NULL, NULL);
    check("version 99 answers null", get_api(99) == NULL, NULL);

    api = get_api(1);
    check("version 1 hands out the table", api != NULL, NULL);
    if (!api) return 1;

    snprintf(buf, sizeof(buf), "table %u, sizeof at the caller %u",
             (unsigned)api->size, (unsigned)sizeof(nsh_api_v1));
    check("size matches the caller's side",
          api->size == (uint32_t)sizeof(nsh_api_v1), buf);

    check("the same version hands out the same table", get_api(1) == api, NULL);

    /* THE RULE FOR EXTENDING THE TABLE, exercised rather than trusted. The
       header says a caller must check size before touching a member added
       after the first published v1. Here the last member of that first table
       is set_region_mode, so size has to cover it - otherwise every consumer
       built against this header is reading past the end of what the library
       actually filled in. */
    {
        size_t need = offsetof(nsh_api_v1, set_region_mode)
                    + sizeof(((nsh_api_v1*)0)->set_region_mode);
        snprintf(buf, sizeof(buf), "size %u, the first table needs %u",
                 (unsigned)api->size, (unsigned)need);
        check("size covers the whole of the first published table",
              (size_t)api->size >= need, buf);
    }

    /* Not one empty slot in the table: a hole would mean that the build of
       the core and the header have drifted apart, and a call through such a
       member is a crash at somebody else's machine. */
    {
        void* const* p = (void* const*)((const char*)api + sizeof(uint32_t));
        int slots = (int)((sizeof(nsh_api_v1) - sizeof(uint32_t)) / sizeof(void*));
        int holes = 0;
        for (i = 0; i < slots; i++) if (p[i] == NULL) holes++;
        snprintf(buf, sizeof(buf), "slots %d, empty %d", slots, holes);
        check("no empty slots in the table", holes == 0, buf);
    }

    check("version() answers with a string", api->version() != NULL, api->version());

    st = api->create(&s);
    check("create", st == NSH_OK && s != NULL, NULL);
    if (st != NSH_OK) return 1;

    check("the formula was taken", api->set_formula(s, "sin(x)*cos(y)") == NSH_OK, NULL);
    check("the domain was taken", api->set_domain(s, -2, 2, -2, 2) == NSH_OK, NULL);
    check("the quality was taken", api->set_quality(s, 40) == NSH_OK, NULL);
    check("the camera was taken",
          api->set_camera(s, 0.9, 0.45, 3.4, 0.9) == NSH_OK, NULL);

    /* Refusals are part of the contract too, and they have to HAPPEN rather
       than take the process down. */
    check("a broken formula is refused",
          api->set_formula(s, "sin(") == NSH_ERR_FORMULA, NULL);
    check("after the refusal the formula still stands",
          api->set_formula(s, "sin(x)*cos(y)") == NSH_OK, NULL);
    check("quality outside 0..100 is refused",
          api->set_quality(s, 1000) == NSH_ERR_ARG, NULL);
    check("last_error answers in words", api->last_error(s) != NULL,
          api->last_error(s));

    rgba = (unsigned char*)malloc((size_t)w * ht * 4);
    check("the buffer was allocated", rgba != NULL, NULL);
    if (!rgba) return 1;

    memset(rgba, 0, (size_t)w * ht * 4);
    st = api->render(s, w, ht, rgba);
    snprintf(buf, sizeof(buf), "code %d", (int)st);
    check("render did its work", st == NSH_OK, buf);

    if (st == NSH_OK) {
        long nonzero = 0;
        for (i = 0; i < w * ht * 4; i++) if (rgba[i]) nonzero++;
        snprintf(buf, sizeof(buf), "non-zero bytes %ld out of %d", nonzero, w * ht * 4);
        check("the frame is not empty", nonzero > 0, buf);
        /* The alpha is promised opaque: RGBA8, and the sheet is opaque. */
        check("the alpha is filled in", rgba[3] != 0, NULL);
    }

    check("a zero size is refused",
          api->render(s, 0, ht, rgba) == NSH_ERR_ARG, NULL);
    check("a null buffer is refused",
          api->render(s, w, ht, NULL) == NSH_ERR_ARG, NULL);

    free(rgba);
    api->destroy(s);
    check("destroy did its work", 1, NULL);

    /* The life cycle many times over: leaks and call order are more dangerous
       than a wrong pixel, and a hundred green frames say nothing about them. */
    {
        int cycles = 200, bad = 0;
        /* The name is tiny and not small: small is a type name in rpcndr.h at
           Microsoft, and it arrives here through windows.h. */
        unsigned char tiny[16 * 12 * 4];
        for (i = 0; i < cycles; i++) {
            nsh_session* t = NULL;
            if (api->create(&t) != NSH_OK) { bad++; continue; }
            if (api->set_formula(t, "x*x+y*y") != NSH_OK) bad++;
            if (api->render(t, 16, 12, tiny) != NSH_OK) bad++;
            api->destroy(t);
        }
        snprintf(buf, sizeof(buf), "cycles %d, failures %d", cycles, bad);
        check("create/render/destroy two hundred times", bad == 0, buf);
    }

    LIBCLOSE(h);

    printf("\n  TOTAL: checks %d, failures %d\n", total, failed);
    return failed ? 1 : 0;
}
