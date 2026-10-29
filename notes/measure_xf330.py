"""Maxspect XF330 Cloud Edition geometry from the vendor's pictures. Prints the numbers in xf330_outlet_geometry.md.

    python notes/measure_xf330.py [RENDER.webp] [MANUAL.pdf]

Inputs (not in this repo; the vendor's): the Bulk Reef Supply product render "...-fr.webp" (pump straight on, tube
horizontal, 1200 x 1200, from bulkreefsupply.com/gyre-xf330-cloud-edition-standard-package-2350-gph-maxspect.html),
scaled by the BRS length 10.5 in and cross-checked against 265 mm; the Maxspect Gyre 300 Cloud manual PDF, page 6 of the
English section (installation drawing, bare pump, side view), scaled by 265 mm. Dark means grey < 128; a slot or window
is black, grey < 40.
"""
import sys
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image

VENDOR = Path(__file__).resolve().parents[3] / "vendor" / "flow"   # reef_build's docs/vendor, when this repo sits inside it
RENDER = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    VENDOR / "maxspect" / "calcs" / "images" / "251816-maxspect-gyre-xf330-cloud-standardedition-bundle-fr.webp"
MANUAL = Path(sys.argv[2]) if len(sys.argv) > 2 else VENDOR / "maxspect" / "maxspect_gyre-300-cloud_manual.pdf"
L_IN = 10.5          # BRS listing
L_MM = 265.0         # Maxspect
GPH = 2350.0         # rated
DARK, BLACK = 128, 40


def runs(seg):
    """[(is_black, length)] along a 1-D boolean array."""
    out, s = [], 0
    for i in range(1, len(seg) + 1):
        if i == len(seg) or seg[i] != seg[s]:
            out.append((bool(seg[s]), i - s))
            s = i
    return out


def render():
    a = np.asarray(Image.open(RENDER).convert("L")).astype(int)
    dark = a < DARK
    body = slice(250, 560)                      # rows holding the pump; the cable loops below
    # length: widest dark span over the tube's center rows
    spans = [(np.where(dark[y])[0].min(), np.where(dark[y])[0].max()) for y in range(400, 441)]
    x0, x1 = min(s[0] for s in spans), max(s[1] for s in spans)
    px_in = (x1 - x0) / L_IN
    px_in_mm = (x1 - x0) / (L_MM / 25.4)
    xc = (x0 + x1) / 2
    print(f"render {RENDER.name}: pump x {x0}..{x1}, {x1 - x0} px = {L_IN} in -> {px_in:.1f} px/in ({px_in_mm:.1f} px/in at {L_MM:g} mm)")

    def vext(x):
        ys = np.where(dark[body, x])[0] + body.start
        return ys.min(), ys.max()

    # end caps: columns just inside each end
    caps = [vext(x0 + 18), vext(x1 - 18)]
    cap_d = np.mean([b - t for t, b in caps]) / px_in
    yc = np.mean([(t + b) / 2 for t, b in caps])
    print(f"  end cap: {[(int(t), int(b)) for t, b in caps]} -> {cap_d:.2f} in, tube center row {yc:.0f}")
    # top-edge profile along the tube: directors sit higher than the cage, the cradle higher still, the motor between
    top = np.array([vext(x)[0] if dark[body, x].any() else 9999 for x in range(x0, x1 + 1)])
    bot = np.array([vext(x)[1] if dark[body, x].any() else 0 for x in range(x0, x1 + 1)])
    # cage bottom edge under the directors (first and last fifth of the length), radius from the center row
    left, right = slice(60 - x0, 215 - x0), slice(985 - x0, 1135 - x0)
    cage_bot = np.median(np.r_[bot[left], bot[right]])
    cage_d = 2 * (cage_bot - yc) / px_in
    print(f"  cage: bottom edge y {cage_bot:.0f}, radius {cage_bot - yc:.0f} px -> OD {cage_d:.2f} in")
    # directors: columns whose top edge sits at the director top, in runs of 20 px or more (the cable crosses the left
    # pair and the cradle lip hangs under the first right one, so only the top edge is used, read on the right and mirrored)
    dir_top = np.median(np.r_[top[left], top[right]])
    is_dir = np.abs(top - dir_top) <= 7
    r_start = None
    for x in range(int(xc - x0), len(top) - 20):
        if is_dir[x:x + 20].all():
            r_start = x + x0
            break
    m0, m1 = 2 * xc - r_start, r_start
    print(f"  motor and cradle: x {m0:.0f}..{m1:.0f} (right edge read, left mirrored), {(m1 - m0) / px_in:.2f} in; "
          f"slotted cages start {(m1 - xc) / px_in:.2f} in from center (director tops y {dir_top:.0f})")
    cage_out = ((x1 - 45) - xc) / px_in
    print(f"  cages reach {cage_out:.2f} in from center (end caps 45 px); per end {cage_out - (m1 - xc) / px_in:.2f} in gross")
    # slots: rows through the lit lower cage
    for row in (455, 465):
        for xa, xb in ((60, 215), (985, 1135)):
            r = runs(a[row, xa:xb] < BLACK)
            opens = [n for b, n in r[1:-1] if b]
            ribs = [n for b, n in r[1:-1] if not b]
            if opens and ribs:
                print(f"  slots row {row} x {xa}-{xb}: open {np.median(opens):.0f} px, rib {np.median(ribs):.0f} px, "
                      f"pitch {(np.median(opens) + np.median(ribs)) / px_in:.2f} in, {100 * np.median(opens) / (np.median(opens) + np.median(ribs)):.0f}% open")
    # director face: black extent down two columns through the windows, open runs across one row
    for x in (100, 165):
        ys = np.where(a[300:400, x] < BLACK)[0] + 300
        print(f"  director col {x}: black y {ys.min()}..{ys.max()} -> {(ys.max() - ys.min()) / px_in:.2f} in tall")
    r = runs(a[360, 60:215] < BLACK)
    opens = sum(n for b, n in r if b)
    print(f"  director row 360 x 60-215: open {opens} of {215 - 60} px ({100 * opens / (215 - 60):.0f}%), face {(215 - 60) / px_in:.2f} in long")
    return cage_d, px_in


def manual():
    p = pymupdf.open(MANUAL)[7]                 # page 6 of the English section
    sc = 4
    pix = p.get_pixmap(matrix=pymupdf.Matrix(sc, sc), colorspace=pymupdf.csGRAY)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    f = pix.width / 827.0                       # the band was located on an 827 px wide render
    band = a[int(280 * f):int(325 * f)] < 160   # row "1)." of the installation figure
    ink = band.sum(axis=0) > 2
    spans, s = [], None
    for x, v in enumerate(ink):
        if v and s is None:
            s = x
        if not v and s is not None:
            if x - s > 100:
                spans.append((s, x))
            s = None
    s, e = spans[0]                             # the bare pump, left of the arrow
    px_mm = (e - s) / L_MM
    heights = [int(np.ptp(np.where(band[:, x])[0]) + 1) if band[:, x].any() else 0 for x in range(s, e)]
    h = np.array(heights)
    cage = np.median(np.r_[h[20:120], h[-220:-20]])
    motor = np.median(h[260:440])
    print(f"manual p.6 bare pump: {e - s} px = {L_MM:g} mm -> {px_mm:.2f} px/mm; cage {cage:.0f} px = {cage / px_mm:.0f} mm "
          f"({cage / px_mm / 25.4:.2f} in); motor {motor:.0f} px = {motor / px_mm:.0f} mm; tallest {h.max()} px = {h.max() / px_mm:.0f} mm (cradle)")


def areas(cage_d):
    q = GPH * 3.785e-3 / 3600                   # m3/s
    slotted = 5.0                               # in, both ends, net of rings and collars
    face = 4 * 1.34 * 0.67 * 0.85               # four director faces net of louvers
    rows = [("director faces only, net of louvers", face),
            ("120 deg arc, 5.0 in slotted, 60% open", np.pi * cage_d / 3 * slotted * 0.6),
            ("180 deg arc, 60% open", np.pi * cage_d / 2 * slotted * 0.6),
            ("180 deg arc, gross", np.pi * cage_d / 2 * slotted),
            ("360 deg cage, gross", np.pi * cage_d * slotted),
            ("recommended", 4.0)]
    print(f"outlet readings at {GPH:g} GPH, cage OD {cage_d:.2f} in:")
    for name, area in rows:
        v = q / (area * 0.0254 ** 2)
        print(f"  {name:42s} {area:5.1f} in2  {v / 0.0254:5.0f} in/s ({v:.2f} m/s)")


if __name__ == "__main__":
    cage_d, _ = render()
    manual()
    areas(round(cage_d, 1))
