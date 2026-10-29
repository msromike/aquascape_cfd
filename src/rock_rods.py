"""Rock as rods: a 1 in grid of square rods standing on the sand, each its own height. Shaped by painting on the views.

    python src/rock_rods.py start CASE [--core RUN]   (rods to the water line everywhere but the glass clearance; the slow
        core of that open-tank run drawn dashed on the top view, none if the run is not there)
    python src/rock_rods.py update CASE   (reads the paint on the three views, redraws them)
    python src/rock_rods.py draw CASE
    python src/rock_rods.py set CASE --x 20:24 [--y 3:19] [--h 0] [--cap]   (a box of rods to a height; 0 takes them
        out; --cap slices only the taller ones down)
    python src/rock_rods.py set CASE --x 8:14 --y 3:5 --bottom 4   (undercut: open water under those rods, 4 in up)
    python src/rock_rods.py stl CASE       (cases/CASE/rock.stl, for cfd_tank.py --stl)

A case is a folder, cases/CASE/: rock/ (this tool's), rock.stl, flow/ (cfd_tank.py views --out cases/CASE/flow). A new
case is a copy of an old one, renamed.
Out: cases/CASE/rock/: top.png, front.png, side.png and a copy of each to paint on,
top_edit.png, front_edit.png, side_edit.png; corner_left_front.png, corner_right_front.png, corner_right_back.png (Blender; not for paint); heights.csv (inches over the sand, back row first, as the top view reads),
bottoms.csv (where a rod starts, inches over the sand: 0 on the sand, more for a ledge or a swim-through; absent means
all 0), core.csv (the slow core of the open-tank run, start --core), history/ (heights and bottoms before each change).
Paint on the _edit copies (Paint, any brush or fill); an outline counts as filled. update reads them, then redraws both.
One color per meaning, the same in the drawing and the legend; eyedrop it. Paint is whatever differs from the clean copy
the _edit canvas was made from (history/base_<view>.png).
Top: green, yellow, orange, red or purple sets the rods already under it to 3, 5, 8, 10 or 13 in (HEIGHT_PAINT);
every square a stroke passes through takes its height: a rod is set, open sand gets a rod (a line is a row, a loop fills);
white takes the rod out; a white line across a block cuts off the smaller piece.
Front and side: red or white shaves the column or row down to the highest rock left.
"""
import argparse
import csv
import os
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cfd_tank as cfd  # noqa: E402

CASES = cfd.ROOT / "cases"
L, W, SAND, WATER = cfd.INSIDE_L_IN, cfd.INSIDE_W_IN, cfd.SAND_IN_DEFAULT, cfd.WATER_IN
FULL = WATER - SAND
NX, NY = int(np.ceil(L)), int(np.ceil(W))   # rods; the last column and row are 0.5 in wide
CLEAR_IN = {"left": 3.0, "right": 3.0, "front": 3.0, "back": 4.5}   # sand to the glass; the back is the loop's back leg
PUMPS_X = (3.0, L - 3.0)  # winner: upright XF330 in the back corners
PUMP_Y = W - cfd.GYRE_STANDOFF_IN
PUMP_Z = cfd.MID_Z_IN
CORE_CASE = "nr90_corners_12p3_forward_left"   # the open-tank winner; start --core picks another
CORE_IN_S = 4.0           # slow core: column mean under the LPS band

P = 40                    # px per inch
ML, MT, MR, MB = 150, 90, 330, 90
BANDS = [(3, "green", (120, 190, 120)), (5, "yellow", (240, 220, 120)), (8, "orange", (240, 170, 100)),
         (10, "red", (215, 110, 110)), (13, "purple", (175, 130, 200)), (99, "brown", (130, 90, 60))]
# in over the sand; the drawing and the paint share these colors
SHADES = (1.0, 0.82, 0.65)                     # near, middle, far third
CREAM = (250, 232, 190)   # rod numbers; white is paint
SANDC, WATERC, GRID, MARK =(225, 210, 170), (215, 232, 245), (175, 165, 145), (60, 60, 60)
VIEWS = ("top", "front", "side")
# a band's color painted on the top view: the rods under it go to the band's top height over the sand
HEIGHT_PAINT = [(name, rgb, float(top)) for top, name, rgb in BANDS[:5]]
WHITE = (255, 255, 255)   # cut
PALETTE = np.array([[c * s for c in rgb] for _, _, rgb in BANDS for s in SHADES], dtype=float)


def font(size, bold=False):
    return ImageFont.truetype("arialbd.ttf" if bold else "arial.ttf", size)


def band(h):
    return next((name, rgb) for top, name, rgb in BANDS if h <= top)


def cell(i, j):
    return i, min(i + 1.0, L), j, min(j + 1.0, W)


def folder(name):
    return CASES / name / "rock"


def read_grid(path):
    rows = list(csv.reader(path.open(encoding="utf-8")))[1:]
    g = np.zeros((NY, NX))
    for r in rows:
        g[int(r[0])] = [float(v) for v in r[1:]]
    return g


def write_grid(path, g):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["y \\ x"] + list(range(NX)))
        for j in range(NY - 1, -1, -1):
            w.writerow([j] + [f"{v:g}" for v in g[j]])


def read_bottoms(d):
    return read_grid(d / "bottoms.csv") if (d / "bottoms.csv").exists() else np.zeros((NY, NX))


def floating(g, bt):
    """Rods not held up: no path to the sand through neighbors that overlap them by 1 in or more."""
    rods = g > 0
    held = rods & (bt <= 0)
    while True:
        grow = held.copy()
        for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = np.roll(np.roll(held, dj, 0), di, 1)
            nt, nbt = np.roll(np.roll(g, dj, 0), di, 1), np.roll(np.roll(bt, dj, 0), di, 1)
            grow |= rods & nb & (np.minimum(g, nt) - np.maximum(bt, nbt) >= 1.0)
        if (grow == held).all():
            return rods & ~held
        held = grow


def levels(g):
    """One height per color: every rod goes to its band's height (3, 5, 8, 10, 13; over 13 is the water line)."""
    lo = 0.0
    out = g.copy()
    for top, _, _ in BANDS:
        out[(g > lo) & (g <= top)] = min(float(top), FULL)
        lo = top
    g[:] = out
    return g


def tidy(g, bt):
    """No bottom without a rod, and at least 2 in of rock over an undercut, else the rod goes back to the sand."""
    bt[(g <= 0) | (g - bt < 2.0)] = 0.0
    return bt


def slow_core(case):
    """Where the open-tank run is slow through the whole water column: rock there costs the least flow."""
    if not case or not (cfd.OUT / case / "u_avg.bin").exists():
        return np.zeros((NY, NX))
    meta, discs, u, speed, flags, label, tag = cfd.load(case, None)
    dx = meta["dx_m"] / cfd.IN
    nz, ny, nx = flags.shape
    s = speed / cfd.IN
    s[flags != 0] = np.nan
    xs, ys, zs = ((np.arange(k) - 0.5) * dx for k in (nx, ny, nz))
    col = np.nanmean(s[(zs > SAND) & (zs < WATER)], axis=0)
    g = np.full((NY, NX), np.inf)
    for j in range(NY):
        for i in range(NX):
            x0, x1, y0, y1 = cell(i, j)
            g[j, i] = np.nanmean(col[np.ix_((ys >= y0) & (ys < y1), (xs >= x0) & (xs < x1))])
    lab, n = ndimage.label((g < CORE_IN_S) & (clear_field() > 0))   # off the glass: the slow strips along the panes are not it
    sizes = ndimage.sum(np.ones_like(g), lab, range(1, n + 1))
    return (lab == 1 + int(np.argmax(sizes))).astype(float)


def clear_field():
    """Rods to the water line everywhere but the sand off the glass and the room round each pump."""
    g = np.zeros((NY, NX))
    c = CLEAR_IN
    for j in range(NY):
        for i in range(NX):
            x0, x1, y0, y1 = cell(i, j)
            clear = x0 >= c["left"] and x1 <= L - c["right"] and y0 >= c["front"] and y1 <= W - c["back"]
            near_pump = any(x1 > px - 1.6 and x0 < px + 1.6 for px in PUMPS_X) and y1 > PUMP_Y - 1.6
            g[j, i] = FULL if clear and not near_pump else 0.0
    return g


def start(a):
    d = folder(a.name)
    d.mkdir(parents=True, exist_ok=True)
    write_grid(d / "heights.csv", clear_field())
    write_grid(d / "core.csv", slow_core(a.core))
    draw(a)


# ---- drawing: fixed pixel geometry so the paint can be read back

def top_px(x, y):
    return ML + x * P, MT + (W - y) * P


def side_px(h, z):
    return ML + h * P, MT + (WATER - z) * P


def frame(img, w_in, h_in, title, edges, vticks):
    d = ImageDraw.Draw(img)
    d.rectangle([ML - 1, MT - 1, ML + w_in * P, MT + h_in * P], outline=(0, 0, 0), width=1)
    d.text((ML, 20), title, fill=(0, 0, 0), font=font(22, True))
    bottom, top, left, right = edges
    d.text((ML + w_in * P / 2, MT + h_in * P + 48), bottom, fill=(0, 0, 0), font=font(16), anchor="mt")
    d.text((ML + w_in * P / 2, MT - 8), top, fill=(0, 0, 0), font=font(16), anchor="mb")
    d.text((ML - 52, MT + h_in * P / 2), left, fill=(0, 0, 0), font=font(16), anchor="rm")
    d.text((ML + w_in * P + 10, MT + h_in * P - 4), right, fill=(0, 0, 0), font=font(16), anchor="lb")   # under the legend
    for k in range(0, int(w_in) + 1, 2):
        x = ML + k * P
        d.line([x, MT + h_in * P, x, MT + h_in * P + 8], fill=(0, 0, 0))
        d.text((x, MT + h_in * P + 12), str(k), fill=(0, 0, 0), font=font(14), anchor="mt")
    for label, v in vticks:
        d.line([ML - 8, v, ML, v], fill=(0, 0, 0))
        d.text((ML - 12, v), label, fill=(0, 0, 0), font=font(14), anchor="rm")
    return d


def legend(d, x0, lines):
    y = MT
    for name, rgb, words in lines:
        if rgb:
            d.rectangle([x0, y, x0 + 22, y + 22], fill=rgb, outline=(0, 0, 0))
        d.text((x0 + 30, y + 11), words, fill=(0, 0, 0), font=font(15), anchor="lm")
        y += 32


def band_legend():
    """Every color once, one height each (levels()); painted, it sets that height, cuts or adds."""
    out = [(name, rgb, f"{name}: {min(top, FULL):g} in up") for top, name, rgb in BANDS]
    return out + [("white", WHITE, "white: cuts"), ("", None, "a color on the sand adds a rod"),
                  ("", None, "front, side: red cuts too"), ("", None, "heights: inches over the sand")]


def draw_top(g, core, path, bt):
    img = Image.new("RGB", (int(ML + L * P + MR), int(MT + W * P + MB)), (255, 255, 255))
    d = frame(img, L, W, "Rock rods from above", ("front glass", "back glass", "left pane", "right pane"),
              [(str(k), top_px(0, k)[1]) for k in range(0, int(W) + 1, 2)])
    for j in range(NY):
        for i in range(NX):
            x0, x1, y0, y1 = cell(i, j)
            (a, b), (c, e) = top_px(x0, y1), top_px(x1, y0)
            h = g[j, i]
            rgb = band(h)[1] if h > 0 else SANDC
            d.rectangle([a, b, c - 1, e - 1], fill=rgb)
            d.rectangle([a, b, c - 1, e - 1], outline=GRID)
            if h > 0:
                dark = sum(rgb) < 400
                d.text(((a + c) / 2, (b + e) / 2), f"{h:g}", fill=CREAM if dark else (0, 0, 0), font=font(13), anchor="mm")
                if bt[j, i] > 0:   # open under: a dark corner and the height the rock starts at
                    d.polygon([(a, b), (a + 14, b), (a, b + 14)], fill=MARK)
                    d.text((a + 2, e - 2), f"u{bt[j, i]:g}", fill=CREAM if dark else (0, 0, 0), font=font(10), anchor="lb")
    for j in range(NY):   # core outline, dashed, on the edges between core and not
        for i in range(NX):
            if not core[j, i]:
                continue
            x0, x1, y0, y1 = cell(i, j)
            for nj, ni, seg in ((j + 1, i, ((x0, y1), (x1, y1))), (j - 1, i, ((x0, y0), (x1, y0))),
                                (j, i - 1, ((x0, y0), (x0, y1))), (j, i + 1, ((x1, y0), (x1, y1)))):
                if 0 <= nj < NY and 0 <= ni < NX and core[nj, ni]:
                    continue
                (p0, q0), (p1, q1) = top_px(*seg[0]), top_px(*seg[1])
                for t in np.arange(0, 1, 0.25):
                    d.line([p0 + (p1 - p0) * t, q0 + (q1 - q0) * t, p0 + (p1 - p0) * (t + 0.13), q0 + (q1 - q0) * (t + 0.13)],
                           fill=(0, 0, 0), width=3)
    r = cfd.GYRE_TUBE_IN / 2
    for px in PUMPS_X:
        a, b = top_px(px - r, PUMP_Y + r)
        c, e = top_px(px + r, PUMP_Y - r)
        d.ellipse([a, b, c, e], fill=MARK)
        d.text(((a + c) / 2, e + 4), "pump", fill=MARK, font=font(13), anchor="mt")
    for hid, kind, y_m, z_m, *rest in cfd.openings(500, 0.68):
        a, b = top_px(0, y_m / cfd.IN)
        d.polygon([(a, b - 8), (a + 12, b), (a, b + 8)], fill=MARK)
        d.text((a + 15, b), hid, fill=MARK, font=font(13), anchor="lm")
    legend(d, ML + L * P + 50, band_legend() + [("", None, "dashed: slow core of the open-tank run"),
                                                ("", None, "dark corner, u4: open under, rock from 4 in up")])
    img.save(path)


def draw_elev(g, path, along, bt):
    """Front (along x, looking through the front glass) or side (along y, looking from the right pane)."""
    span = L if along == "x" else W
    img = Image.new("RGB", (int(ML + span * P + MR), int(MT + WATER * P + MB)), (255, 255, 255))
    title = "Rock rods through the front glass" if along == "x" else "Rock rods from the right pane"
    edges = ("bottom glass", "water line", "left pane", "right pane") if along == "x" else \
        ("bottom glass", "water line", "front glass", "back glass")
    d = frame(img, span, WATER, title, edges, [(str(k), side_px(0, SAND + k)[1]) for k in range(0, int(FULL) + 1, 2)])
    d.rectangle([*side_px(0, WATER), side_px(span, SAND)[0] - 1, side_px(0, SAND)[1] - 1], fill=WATERC)
    d.rectangle([*side_px(0, SAND), side_px(span, 0)[0] - 1, side_px(0, 0)[1] - 1], fill=SANDC)
    if along == "x":   # back rows first, the front row last
        order = [(j, i) for j in range(NY - 1, -1, -1) for i in range(NX)]
        depth = lambda j, i: cell(i, j)[2] / W
        across = lambda j, i: cell(i, j)[:2]
    else:              # left pane first, the right pane last
        order = [(j, i) for i in range(NX) for j in range(NY)]
        depth = lambda j, i: 1 - cell(i, j)[1] / L
        across = lambda j, i: cell(i, j)[2:]
    for j, i in order:
        h = g[j, i]
        if h <= 0:
            continue
        shade = SHADES[min(2, int(depth(j, i) * 3))]
        rgb = tuple(int(c * shade) for c in band(h)[1])
        h0, h1 = across(j, i)
        a, b = side_px(h0, SAND + h)
        c, e = side_px(h1, SAND + bt[j, i])
        d.rectangle([a, b, c - 1, e - 1], fill=rgb)
    for k in range(int(np.ceil(span)) + 1):   # 1 in grid over the water and the rock, heights over the sand
        x = side_px(min(k, span), 0)[0]
        d.line([x, side_px(0, WATER)[1], x, side_px(0, SAND)[1]], fill=GRID)
    for k in range(int(FULL) + 1):
        v = side_px(0, SAND + k)[1]
        d.line([ML, v, side_px(span, 0)[0], v], fill=GRID)
    zt0, zt1 = PUMP_Z - cfd.GYRE_L_IN / 2, PUMP_Z + cfd.GYRE_L_IN / 2
    r = cfd.GYRE_TUBE_IN / 2
    for pc in (PUMPS_X if along == "x" else [PUMP_Y]):
        a, b = side_px(pc - r, zt1)
        c, e = side_px(pc + r, zt0)
        d.rectangle([a, b, c, e], outline=MARK, width=3)
        d.text(((a + c) / 2, b - 4), "pump", fill=MARK, font=font(13), anchor="mb")
    holes = cfd.openings(500, 0.68)
    for hid, kind, y_m, z_m, dia_m, *rest in holes:
        hc = 0.8 if along == "x" else y_m / cfd.IN
        a, b = side_px(hc, z_m / cfd.IN)
        rr = max(6, dia_m / cfd.IN * P / 2)
        d.ellipse([a - rr, b - rr, a + rr, b + rr], outline=MARK, width=3)
        if along == "y":
            d.text((a, b - rr - 3), hid, fill=MARK, font=font(13), anchor="mb")
    if along == "x":   # all three are in the left pane, one behind another
        a, b = side_px(0.8, holes[0][3] / cfd.IN)
        d.text((a, b - 34), ", ".join(h[0] for h in holes), fill=MARK, font=font(13), anchor="mb")
    shade_words = "near third bright, far third dark"
    legend(d, ML + span * P + 50, band_legend() + [("", None, shade_words), ("", None, "scale and grid: inches over the sand")])
    img.save(path)


BLENDER = Path(os.environ.get("BLENDER") or shutil.which("blender")
               or r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")   # $BLENDER, else on PATH, else 5.2 default
CORNERS = {"corner_left_front": ("left front", -30.0, -48.0), "corner_right_front": ("right front", L + 30, -48.0),
           "corner_right_back": ("right back", L + 30, W + 48)}   # camera off each corner, inches


def draw_persp(g, d, bt):
    """The rods from three corners, looking down a little, rendered in Blender (rock_rods_blender.py); tank edges, sand,
    water line (blue), pumps and the left-pane holes for scale. A caption bar goes on after."""
    import json
    import subprocess
    r = cfd.GYRE_TUBE_IN / 2
    rods = []
    for j in range(NY):
        for i in range(NX):
            if g[j, i] > 0:
                rods.append([*cell(i, j), SAND + bt[j, i], SAND + g[j, i], [c / 255 for c in band(g[j, i])[1]]])
    scene = {"L": L, "W": W, "rim": cfd.RIM_IN, "water": WATER, "sand": SAND, "rods": rods,
             "pumps": [[px - r, px + r, PUMP_Y - r, PUMP_Y + r, PUMP_Z - cfd.GYRE_L_IN / 2, PUMP_Z + cfd.GYRE_L_IN / 2]
                       for px in PUMPS_X],
             "holes": [[h[0], h[2] / cfd.IN, h[3] / cfd.IN, h[4] / cfd.IN] for h in cfd.openings(500, 0.68)],
             "views": {name: [ex, ey] for name, (words, ex, ey) in CORNERS.items()}}
    spec = d / "scene.json"
    spec.write_text(json.dumps(scene))
    for name in CORNERS:   # a failed render must not leave the last picture standing
        (d / f"{name}.png").unlink(missing_ok=True)
    (d / "corner.png").unlink(missing_ok=True)
    rc = subprocess.run([str(BLENDER), "--background", "--factory-startup", "--python",
                         str(Path(__file__).with_name("rock_rods_blender.py")), "--", str(spec), str(d)],
                        capture_output=True, text=True)
    spec.unlink()
    hs = g[g > 0]
    for name, (words, ex, ey) in CORNERS.items():
        path = d / f"{name}.png"
        if not path.exists():
            print("blender: " + (rc.stdout + rc.stderr)[-800:])
            return
        img = Image.open(path).convert("RGB")
        out = Image.new("RGB", (img.width, img.height + 60), (255, 255, 255))
        out.paste(img, (0, 60))
        ImageDraw.Draw(out).text((20, 30), f"Rock rods from the {words} corner, looking down a little: {len(hs)} rods, "
                                 f"tallest {hs.max() if len(hs) else 0:g} in over the sand; blue line: water line",
                                 fill=(0, 0, 0), font=font(22, True), anchor="lm")
        out.save(path)


def base_of(edit):
    """The clean drawing an _edit canvas was copied from."""
    view = edit.stem.replace("_edit", "")
    base = edit.parent / "history" / f"base_{view}.png"
    return base if base.exists() else edit.with_name(f"{view}.png")


def painted(d, view):
    """True when the _edit canvas no longer matches the clean view it was copied from: someone has painted on it."""
    edit = d / f"{view}_edit.png"
    base = base_of(edit)
    return edit.exists() and base.exists() and edit.read_bytes() != base.read_bytes()


def draw(a, consumed=False):
    """Redraw every view. A painted canvas is replaced only when update has just read it (consumed)."""
    d = folder(a.name)
    keep = [v for v in VIEWS if not consumed and painted(d, v)]
    g, core, bt = read_grid(d / "heights.csv"), read_grid(d / "core.csv"), read_bottoms(d)
    draw_top(g, core, d / "top.png", bt)
    draw_elev(g, d / "front.png", "x", bt)
    draw_elev(g, d / "side.png", "y", bt)
    draw_persp(g, d, bt)
    for view in VIEWS:   # fresh canvases to paint on; the clean views stay as they are
        if view in keep:
            print(f"{view}_edit.png has paint on it: kept, not replaced")
            continue
        shutil.copy(d / f"{view}.png", d / f"{view}_edit.png")
        (d / "history").mkdir(exist_ok=True)
        shutil.copy(d / f"{view}.png", d / "history" / f"base_{view}.png")
    loose = floating(g, bt)
    if loose.any():
        js, iss = np.nonzero(loose)
        print(f"FLOATING: {loose.sum()} rods with nothing under or beside them to hold them up: " +
              ", ".join(f"x {i} y {j}" for j, i in zip(js, iss)))
    print(f"{d}: {int((g > 0).sum())} rods, {int((bt > 0).sum())} undercut, tallest {g.max():g} in over the sand, "
          f"{100 * (g > 0).sum() / (L * W):.0f}% of the floor")


# ---- reading the paint back

def paint(path, w_in, h_in, red_cuts=True):
    """Cuts (white, and red on front and side), the drawn rock, and every painted pixel."""
    px = np.asarray(Image.open(path).convert("RGB")).astype(int)
    base = np.asarray(Image.open(base_of(path)).convert("RGB")).astype(int)
    changed = np.any(px != base, axis=-1) if base.shape == px.shape else np.ones(px.shape[:2], dtype=bool)
    r, gch, b = px[..., 0], px[..., 1], px[..., 2]
    inside = np.zeros(r.shape, dtype=bool)   # the frame only: the white margin round it is not paint
    inside[MT + 2:int(MT + h_in * P) - 2, ML + 2:int(ML + w_in * P) - 2] = True
    white = (r >= 245) & (gch >= 245) & (b >= 245) & inside & changed   # Paint's eraser; cuts like red
    red = ndimage.binary_fill_holes((stroke(px, "red") & changed & red_cuts) | white)   # top view: red is a height
    dist = np.min(np.linalg.norm(px[..., None, :] - PALETTE[None, None], axis=-1), axis=-1)
    rock = (dist < 20) & ~red
    grid = np.linalg.norm(px - np.array(GRID), axis=-1) < 12   # a grid line on a rock top belongs to the rock under it
    rock[:-1] |= grid[:-1] & rock[1:]
    return red, rock, changed


def stroke(px, name):
    """Pixels of one band's color, eyedropped (Paint's own swatch of that hue reads the same); the caller keeps only
    the changed ones, since the drawing is the same color."""
    r, g, b = px[..., 0], px[..., 1], px[..., 2]
    drawn = np.linalg.norm(px - np.array(dict((n, c) for _, n, c in BANDS)[name]), axis=-1) < 20
    return drawn | {"green": (g >= 170) & (r <= 90) & (b <= 120),
                    "yellow": (r >= 200) & (g >= 200) & (b <= 80),
                    "orange": (r >= 200) & (g >= 90) & (g <= 170) & (b <= 80),
                    "red": (r >= 190) & (g <= 70) & (b <= 70),
                    "purple": (r >= 120) & (g <= 85) & (b >= 120)}[name]


def snap(v):
    return max(0.0, round(v * 4) / 4)


def read_top(g, path):
    red, _, changed = paint(path, L, W, red_cuts=False)
    cut = add = 0
    boxes = {}
    rods = np.zeros(red.shape, dtype=bool)
    for j in range(NY):
        for i in range(NX):
            x0, x1, y0, y1 = cell(i, j)
            (a, b), (c, e) = top_px(x0, y1), top_px(x1, y0)
            boxes[j, i] = (slice(int(b) + 4, int(e) - 4), slice(int(a) + 4, int(c) - 4))
            if g[j, i] > 0:
                rods[int(b):int(e), int(a):int(c)] = True
    # a line across a block cuts it; the smaller pieces go, the largest stays
    pieces, _ = ndimage.label(rods & ~ndimage.binary_dilation(red, iterations=4))
    blocks, nb = ndimage.label(rods)
    keep = np.zeros(pieces.max() + 1, dtype=bool)
    for k in range(1, nb + 1):
        ids, counts = np.unique(pieces[(blocks == k) & (pieces > 0)], return_counts=True)
        if ids.size:
            keep[ids[np.argmax(counts)]] = True
    kept, dropped = keep[pieces] & (pieces > 0), ~keep[pieces] & (pieces > 0)
    px = np.asarray(Image.open(path).convert("RGB")).astype(int)
    # every square a stroke passes through takes its color's height: on a rod it sets the rod, on sand it adds one, so a
    # line is a row of rods and a closed loop fills in; specks under 40 px (antialiasing off the rod numbers) are not paint
    marks = []
    for name, _, h in HEIGHT_PAINT:
        lab, n = ndimage.label(stroke(px, name) & changed)
        m = np.zeros(red.shape, dtype=bool)
        if n:
            big = np.nonzero(ndimage.sum(np.ones_like(lab), lab, range(1, n + 1)) >= 40)[0] + 1
            m = ndimage.binary_fill_holes(np.isin(lab, big))
        marks.append((h, m))
    reset = 0
    for j in range(NY):
        for i in range(NX):
            box = boxes[j, i]
            counts = [(m[box].sum(), h) for h, m in marks]
            n_px, hit = max(counts)
            hit = hit if n_px >= 40 else None   # the stroke touches this square
            if g[j, i] > 0 and (red[box].sum() >= 40 or dropped[box].sum() > kept[box].sum()):
                g[j, i] = 0.0
                cut += 1
            elif hit is not None and g[j, i] > 0:
                reset += int(g[j, i] != hit)
                g[j, i] = hit
            elif hit is not None:
                g[j, i] = hit
                add += 1
    return f"top: {cut} rods out, {add} in, {reset} to a painted height"


def read_elev(g, path, along):
    red, rock, _ = paint(path, L if along == "x" else W, WATER)
    span_n = NX if along == "x" else NY
    shaved = 0
    rows_z = lambda r: WATER - (r - MT) / P
    for k in range(span_n):
        h0, h1 = (cell(k, 0)[:2] if along == "x" else cell(0, k)[2:])
        cols = range(int(ML + h0 * P) + 3, int(ML + h1 * P) - 3)
        rows = slice(int(MT), int(MT + FULL * P))
        line = g[:, k] if along == "x" else g[k, :]
        tops = []
        for c in cols:
            hit = np.nonzero(rock[rows, c])[0]
            tops.append(rows_z(MT + hit[0]) - SAND if hit.size else 0.0)
        cap = float(np.median(tops))
        top_now = line.max()
        painted = red[rows, cols.start:cols.stop].any()   # shave only where red or white went on, never from a stale canvas
        if top_now > 0 and painted and cap < top_now - 0.2:
            line[:] = np.minimum(line, snap(cap))
            shaved += 1
    word = "columns" if along == "x" else "rows"
    return f"{'front' if along == 'x' else 'side'}: {shaved} {word} shaved"


def update(a):
    d = folder(a.name)
    g = read_grid(d / "heights.csv")
    n = save_history(d)
    notes = [read_top(g, d / "top_edit.png"), read_elev(g, d / "front_edit.png", "x"),
             read_elev(g, d / "side_edit.png", "y")]
    write_grid(d / "heights.csv", levels(g))
    write_grid(d / "bottoms.csv", tidy(g, read_bottoms(d)))
    print("; ".join(notes) + f"; before this update: history/{n:02d}.csv")
    draw(a, consumed=True)


def save_history(d):
    hist = d / "history"
    hist.mkdir(exist_ok=True)
    n = len(list(hist.glob("[0-9][0-9].csv"))) + 1
    shutil.copy(d / "heights.csv", hist / f"{n:02d}.csv")
    if (d / "bottoms.csv").exists():
        shutil.copy(d / "bottoms.csv", hist / f"{n:02d}_bottoms.csv")
    return n


def set_box(a):
    """Rods with x and y in the box (in from the left pane and the front glass) to a height over the sand; 0 takes them out."""
    d = folder(a.name)
    g = read_grid(d / "heights.csv")
    n = save_history(d)
    (x0, x1), (y0, y1) = (map(float, a.x.split(":")), map(float, (a.y or f"0:{W}").split(":")))
    hit = 0
    bt = read_bottoms(d)
    for j in range(NY):
        for i in range(NX):
            cx0, cx1, cy0, cy1 = cell(i, j)
            if not (cx0 >= x0 and cx1 <= x1 and cy0 >= y0 and cy1 <= y1):
                continue
            if a.bottom is not None:   # undercut the rods already there
                if g[j, i] > 0:
                    bt[j, i] = a.bottom
                    hit += 1
            elif a.cap:   # slice: only rods taller than h come down to h
                if g[j, i] > a.h:
                    g[j, i] = a.h
                    hit += 1
            elif g[j, i] > 0 or a.h > 0:
                g[j, i] = min(a.h, FULL)
                hit += 1
    write_grid(d / "heights.csv", levels(g))
    write_grid(d / "bottoms.csv", tidy(g, bt))
    what = f"open under to {a.bottom:g} in" if a.bottom is not None else f"to {a.h:g} in"
    print(f"set: {hit} rods {what}; before this: history/{n:02d}.csv")
    draw(a)


# ---- STL: each rod from the bottom glass (or its undercut) to its top, one closed shell, tank millimetres

def stl(a):
    d = folder(a.name)
    g, bt = read_grid(d / "heights.csv"), read_bottoms(d)
    tris = []

    def quad(p, n):
        # 0.1 mm off the inch grid: on the 4 mm lattice 10 in and 30 in fall on cell centers, and the voxelizer's rays
        # miscount on a rod edge there (a phantom wall along y = 10 in, 2026-10-29)
        p = [np.array(v, dtype=float) * cfd.IN * 1000.0 + 0.1 for v in p]
        for t in ((p[0], p[1], p[2]), (p[0], p[2], p[3])):
            if np.dot(np.cross(t[1] - t[0], t[2] - t[0]), n) < 0:
                t = (t[0], t[2], t[1])
            tris.append((n, *t))

    def span(j, i):
        """Solid from z0 to z1 (bottom glass up, or from the undercut), or None."""
        if not (0 <= j < NY and 0 <= i < NX) or g[j, i] <= 0:
            return None
        return (SAND + bt[j, i] if bt[j, i] > 0 else 0.0), SAND + g[j, i]

    for j in range(NY):
        for i in range(NX):
            s = span(j, i)
            if s is None:
                continue
            x0, x1, y0, y1 = cell(i, j)
            z0, zt = s
            quad([(x0, y0, zt), (x1, y0, zt), (x1, y1, zt), (x0, y1, zt)], (0, 0, 1))
            quad([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1))
            for nj, ni, n, (pa, pb) in ((j - 1, i, (0, -1, 0), ((x0, y0), (x1, y0))), (j + 1, i, (0, 1, 0), ((x0, y1), (x1, y1))),
                                        (j, i - 1, (-1, 0, 0), ((x0, y0), (x0, y1))), (j, i + 1, (1, 0, 0), ((x1, y0), (x1, y1)))):
                ns = span(nj, ni)   # wall wherever this rod is solid and the neighbor is not
                walls = [(z0, zt)] if ns is None else [(z0, min(zt, ns[0])), (max(z0, ns[1]), zt)]
                for za, zc in walls:
                    if zc > za:
                        quad([(*pa, za), (*pb, za), (*pb, zc), (*pa, zc)], n)
    rec = np.zeros(len(tris), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")])
    rec["n"] = [t[0] for t in tris]
    rec["v"] = [t[1:] for t in tris]
    path = CASES / a.name / "rock.stl"
    with path.open("wb") as f:
        f.write(b"rock_rods".ljust(80, b" "))
        f.write(np.uint32(len(tris)).tobytes())
        f.write(rec.tobytes())
    print(f"{path}: {len(tris)} triangles, {int((g > 0).sum())} rods")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("start", start), ("update", update), ("draw", draw), ("stl", stl), ("set", set_box)):
        s = sub.add_parser(name)
        s.add_argument("name")
        if name == "start":
            s.add_argument("--core", default=CORE_CASE)   # open-tank run whose slow core the top view outlines
        if name == "set":
            s.add_argument("--x", default=f"0:{L}")   # "20:24", in from the left pane; all of it when left out
            s.add_argument("--y")                  # in from the front glass; all of it when left out
            s.add_argument("--h", type=float, default=0.0)
            s.add_argument("--cap", action="store_true")   # slice the taller rods down to --h, leave the rest
            s.add_argument("--bottom", type=float)          # undercut: the rods already there start this far over the sand
        s.set_defaults(fn=fn)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
