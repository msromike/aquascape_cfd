"""VCA Random Flow Generator (US 11,071,990) bell geometry from the patent drawing, scaled to the 3/4 in nozzle.

    python notes/measure_rfg.py [SHEET01.png]

Sources: sheet 1 of US 11,071,990 B1 (FIG. 1, side elevation), rendered from the patent PDF at 200 dpi (pymupdf; the PDF
is at patentimages.storage.googleapis.com/5c/2a/6c/27b5d5ad12b66a/US11071990.pdf, not in this repo); the patent
text for the diameter ratios (A ~ 2C, B ~ 1.1C, D ~ A, E_mid ~ 1.7C, E_out ~ 2.5C); BRS listing for the 3/4 in nozzle,
2.75 in long, 1.7 in OD, optimal 420-500 GPH. The bell outline is traced row by row from a clean start row, following
the nearest ink run; the exit wall angle is a straight-line fit over the top part of the bell below the rim ellipse.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

VENDOR = Path(__file__).resolve().parents[3] / "vendor" / "flow"   # reef_build's docs/vendor, when this repo sits inside it
SHEET = Path(sys.argv[1]) if len(sys.argv) > 1 else VENDOR / "rfg" / "calcs" / "images" / "US11071990_sheet01.png"
OD_IN = 1.7           # BRS, bell outside diameter at the outlet
GPH = 500.0           # return target
Y_START, Y_END = 520, 1360   # rows of the bell outline to trace: the rim ellipse's widest row down to the bell base ring 30
X_LEFT, X_RIGHT = (400, 640), (1000, 1240)   # windows holding the left and right wall; labels sit outside them
X_AXIS = 820          # nozzle axis, px


def trace(a):
    ink = a < 128
    left, right = [], []
    lx, rx = None, None
    for y in range(Y_START, Y_END + 1):
        xs = np.where(ink[y])[0]
        runs, s = [], None
        for i in range(1, len(xs) + 1):
            if i == len(xs) or xs[i] != xs[i - 1] + 1:
                runs.append((xs[s if s is not None else 0], xs[i - 1]))
                s = i
        if not runs:
            continue
        l_cands = [r for r in runs if X_LEFT[0] <= r[0] <= X_LEFT[1]]
        r_cands = [r for r in runs if X_RIGHT[0] <= r[1] <= X_RIGHT[1]]
        if not l_cands or not r_cands:
            continue
        if lx is None:                      # first row: the outermost runs
            lx = min(r[0] for r in l_cands)
            rx = max(r[1] for r in r_cands)
        else:                               # follow the run nearest the last edge, within 12 px
            lc = min(l_cands, key=lambda r: abs(r[0] - lx), default=None)
            rc = min(r_cands, key=lambda r: abs(r[1] - rx), default=None)
            if lc is None or abs(lc[0] - lx) > 12 or rc is None or abs(rc[1] - rx) > 12:
                continue
            lx, rx = lc[0], rc[1]
        left.append((y, lx))
        right.append((y, rx))
    return np.array(left), np.array(right)


def main():
    a = np.asarray(Image.open(SHEET).convert("L"))
    left, right = trace(a)
    ys = left[:, 0]
    width = right[:, 1] - left[:, 1]
    print(f"FIG. 1 bell outline traced y {ys.min()}..{ys.max()} ({len(ys)} rows)")
    rim_w = width[0]                    # the rim ellipse is widest at the start row
    i_mid = int(np.argmin(width))
    w_top, w_mid, w_base = width[0], width[i_mid], width[-1]
    print(f"  widths: rim {rim_w} px, at y {ys[0]} {w_top} px, narrowest {w_mid} px at y {ys[i_mid]}, base y {ys[-1]} {w_base} px")
    print(f"  ratios: rim/narrowest {rim_w / w_mid:.2f} (patent 2.5/1.7 = 1.47), base/narrowest {w_base / w_mid:.2f} (patent 2.0/1.7 = 1.18)")
    px_in = rim_w / OD_IN
    print(f"  scale: {px_in:.0f} px/in from the 1.7 in OD; bell from rim to base {(ys[-1] - ys[0]) / px_in:.2f} in, "
          f"narrowest {w_mid / px_in:.2f} in, base {w_base / px_in:.2f} in")
    # exit wall angle: straight fit of each edge over the top rows traced
    for n_rows in (80, 180, 280):
        sel = slice(0, n_rows)
        al = np.degrees(np.arctan(abs(np.polyfit(ys[sel], left[sel, 1], 1)[0])))
        ar = np.degrees(np.arctan(abs(np.polyfit(ys[sel], right[sel, 1], 1)[0])))
        print(f"  wall angle off the axis over y {ys[0]}..{ys[n_rows - 1]} ({(ys[n_rows - 1] - ys[0]) / px_in:.2f} in): "
              f"left {al:.0f} deg, right {ar:.0f} deg")
    # throat and jet from the patent ratios
    c_in = OD_IN / 2.5
    q = GPH * 3.785e-3 / 3600
    v = q / (np.pi * (c_in * 0.0254 / 2) ** 2)
    print(f"  patent ratios at 1.7 in OD: throat C {c_in:.2f} in, intake A {2 * c_in:.2f} in, bell middle {1.7 * c_in:.2f} in")
    print(f"  central jet at {GPH:g} GPH through C: {v / 0.0254:.0f} in/s ({v:.2f} m/s); through a 0.75 in bore: "
          f"{q / (np.pi * (0.75 * 0.0254 / 2) ** 2) / 0.0254:.0f} in/s")


if __name__ == "__main__":
    main()
