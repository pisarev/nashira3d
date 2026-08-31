"""The sheet of thumbnails for the gallery of samples.

    python web/build_samples.py

It reads the list of samples FROM THE PAGE ITSELF and draws each one with the
same core that draws everything else. Hence the two properties this was made
for:

  - the gallery shows a REAL surface rather than an invented icon. An icon
    would have to be invented, and an invented icon will sooner or later drift
    away from what the formula actually gives;
  - there is one list. Had the generator kept a copy of its own, it would have
    fallen behind, and a person would choose the picture of one formula and get
    another.

Why a sheet rather than twenty files. Twenty pictures are twenty requests and
twenty entries in the release. One sheet goes out in a single piece, and a cell
is cut out by shifting the background.

The order of the cells equals the order of the entries in the list. A probe
checks that the number of cells matches the number of samples.
"""

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "python"))

PAGE = os.path.join(HERE, "preview.html")
OUT = os.path.join(HERE, "samples.png")

CELL_W, CELL_H = 176, 120

ENTRY = re.compile(
    r'\{\s*n:"([^"]+)",\s*g:"([^"]+)",\s*z:([-\d.]+),\s*d:\[([^\]]+)\],\s*'
    r'f:"([^"]+)"\s*\}', re.S)


def columns():
    """How many columns the sheet has. The number lives ON THE PAGE and is read
    from there: a second copy would sooner or later drift away from the layout
    of the cell."""
    text = io.open(PAGE, encoding="utf-8").read()
    m = re.search(r"const SAMPLE_COLS\s*=\s*(\d+)", text)
    if not m:
        raise SystemExit("SAMPLE_COLS is not declared on the page")
    return int(m.group(1))


def samples():
    text = io.open(PAGE, encoding="utf-8").read()
    i = text.find("const SAMPLES = [")
    if i < 0:
        raise SystemExit("the page has no list of samples")
    block = text[i:text.index("];", i)]
    out = []
    for n, g, z, d, f in ENTRY.findall(block):
        box = [float(v) for v in d.split(",")]
        out.append((n, g, float(z), box, f))
    if not out:
        raise SystemExit("the list of samples is empty: the pattern has fallen behind it")
    return out


def main():
    import numpy as np
    import nashira3d

    rows = samples()
    cols = columns()
    n = len(rows)
    grid_rows = (n + cols - 1) // cols
    # The sheet is SINGLE-CHANNEL: the thumbnails are grey, and there is no
    # point keeping three channels of identical values. It also weighs three
    # times less before any compression.
    sheet = np.zeros((grid_rows * CELL_H, cols * CELL_W), dtype=np.uint8)

    print("samples %d, sheet %d by %d cells" % (n, cols, grid_rows))
    flat = []
    with nashira3d.Session("0", quality=70) as s:
        s.axes = False
        s.grid = False
        # LINES, not colour. Contours read like a drawing: they show the shape
        # and the steepness, and twenty coloured cells side by side quarrel
        # with each other, while eighteen grey ones add up to one sheet.
        s.shading = "contours"
        for k, (name, group, z, box, formula) in enumerate(rows):
            s.formula = formula
            s.domain = tuple(box)
            s.box = (1.0, 1.0, z)
            s.camera = (0.9, 0.55, 3.2, 0.9)
            s.fit = True
            img = s.render(CELL_W, CELL_H)
            # Luminance by Rec. 709: a plain average over the channels turns
            # blue and green into muddle, and in this palette they are the main
            # ones.
            grey = (0.2126 * img[:, :, 0] + 0.7152 * img[:, :, 1]
                    + 0.0722 * img[:, :, 2]).astype(np.uint8)
            r = k // cols
            c = k % cols
            sheet[r * CELL_H:(r + 1) * CELL_H, c * CELL_W:(c + 1) * CELL_W] = grey
            # A witness that the cell is not empty: how many DIFFERENT tones
            # are in it. A flat fill is not a picture of the formula but a
            # picture of a refusal, and in silence it looks the same as a
            # successful one.
            tones = len(set(grey.reshape(-1)[::7].tolist()))
            if tones < 12:
                flat.append((name, tones))
            print("  %2d %-16s %-8s tones %5d" % (k, name, group, tones))

    if flat:
        print("")
        print("FLAT CELLS: " + ", ".join("%s (%d)" % x for x in flat))
        raise SystemExit(1)

    # Sixty-four levels of grey. A smooth gradient in full eight bits compresses
    # WORSE than an indexed palette: measured on this very sheet, 179 006 bytes
    # at 8 bits, 171 300 at 128 levels, 138 239 at 64, 106 788 at 32.
    # Sixty-four was taken because on a cell of 176 by 120 it produces no
    # banding, while thirty-two is already on the edge.
    from PIL import Image
    (Image.fromarray(sheet, "L")
          .convert("P", palette=Image.ADAPTIVE, colors=64)
          .save(OUT, optimize=True))
    print("")
    print("sheet: %s, %d bytes, cell %d by %d, grid %d by %d"
          % (OUT, os.path.getsize(OUT), CELL_W, CELL_H, cols, grid_rows))


if __name__ == "__main__":
    main()
