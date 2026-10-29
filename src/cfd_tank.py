"""Display-tank flow in FluidX3D: wire the setup in, run a case, draw it.

    python src/cfd_tank.py prepare [--fp32]
    python src/cfd_tank.py run --case open_tank --t 90 --pumps "3:forward,32.5:left" --rfg-tilt 20
    python src/cfd_tank.py run --case rock --t 60 --warm open_tank --pumps "3:forward,32.5:left" --rfg-tilt 20 --stl stl/rods_two_bommies.stl
    python src/cfd_tank.py views --case rock --out flow_images/2_two_bommies --title "words for the first line of every picture"

prepare points FluidX3D/src/setup.cpp at src/cfd_tank.cpp and sets defines.hpp; rebuild FluidX3D after it.
run writes FluidX3D/bin/reef_case.txt and runs the exe; no rebuild between cases. Raw fields stay in FluidX3D/bin/reef_out/<case>.
views draws one case as nine pictures plus numbers.txt: front1_near, front2_middle, front3_far (through the front glass, 3 in
behind it, mid-depth, 3 in off the back glass); side1_near, side2_middle, side3_far (from the right pane, at 3/4, 1/2 and 1/4
of the length); top1_high, top2_middle, top3_low (looking down, 1 in under the water line, mid-water, 1 in over the sand).
Color is the 20 s mean speed in coral bands; arrows are the mean direction in the cut.
This tank: 90 gal rimless, inside 35.5 x 23.5 in, rim 23.25 in, water line 22.1 in above the bottom glass, sand 2.5 in.
Openings from tank/holes.csv, measured on the outside of the left pane: inside y = 23.5 - (from back - 0.5 glass).
Return: one jet at R1, 500 GPH. Overflow: D1 and D2 share it, each through a 1.5 in bulkhead bore.
Lid: FluidX3D walls are bounce-back only, so the water line is a no-slip lid; it drags the top layer a little.
Pumps: --pumps "x:way,x:way", upright Maxspect XF330 tubes on their mounts off the back glass, x in from the left pane,
pointing left, right or forward (out at the front glass), or off (body only). Height: --gyre-z-in, default mid-water.
Geometry GYRE_* from notes/xf330_outlet_geometry.md; rated flow out the slots.
Rock: binary STL in tank metres (x from the left pane, y from the front glass, z from the bottom glass), from rock_rods.py.
RFG: off unless --rfg-tilt; 20 deg (15 to 25) traced off the patent drawing, snap and hold times from US 11,071,990
(notes/rfg_jet_pattern.md). The return enters at the 0.68 in throat.
Warm start: --warm CASE starts the fluid from that case's last snapshot; same dx only.
FluidX3D: the clone named by $FLUIDX3D, else a FluidX3D folder beside this folder or beside any folder above it.
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import textwrap
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]   # the aquascape_cfd folder


def find_fluidx3d():
    if os.environ.get("FLUIDX3D"):
        return Path(os.environ["FLUIDX3D"])
    return next((p / "FluidX3D" for p in ROOT.parents if (p / "FluidX3D").is_dir()), ROOT.parent / "FluidX3D")


FX3D = find_fluidx3d()
EXE = FX3D / "bin" / "FluidX3D.exe"
OUT = FX3D / "bin" / "reef_out"
DRILL = ROOT / "tank" / "holes.csv"

IN = 0.0254
GPH = 3.785e-3 / 3600.0

INSIDE_L_IN = 35.5
INSIDE_W_IN = 23.5
RIM_IN = 23.25
WATER_IN = 22.1
GLASS_IN = 0.5
BULKHEAD_BORE_IN = 1.5

# XF330 from notes/xf330_outlet_geometry.md (product render and manual, part not in hand)
GYRE_L_IN = 10.4                  # tube, end cap to end cap
GYRE_TUBE_IN = 1.2                # cage outside diameter
GYRE_STANDOFF_IN = 2.0            # back glass to the tube center; TBD, 1.9 to 2.3 in
GYRE_SLOT_IN, GYRE_SLOT_OUT = 1.8, 4.85   # slotted cage, from the tube center, each end; the motor between is solid
GYRE_MOUNT_L_IN, GYRE_MOUNT_W_IN = 3.5, 1.5   # mount block, tube to glass, across the motor and cradle section
GYRE_OUTLET_IN2 = 4.0             # both cages; bracket 3 to 6 in2
SAND_IN_DEFAULT = 2.5               # sand bed top over the bottom glass
MID_Z_IN = SAND_IN_DEFAULT + (WATER_IN - SAND_IN_DEFAULT) / 2   # tube center at mid-water, 12.3 in up
# --pumps "3:forward,32.5:left": upright pumps placed one at a time, x in from the left pane; (push, aim deg off the glass);
# off is the body with no flow
PUMP_WAYS = {"left": ("-x", 0.0), "right": ("+x", 0.0), "forward": ("-x", 90.0), "off": ("-x", 0.0)}


def prepare(fp16s):
    setup = FX3D / "src" / "setup.cpp"
    cpp = (Path(__file__).resolve().parent / "cfd_tank.cpp").as_posix()
    setup.write_text('#include "setup.hpp"\n'
                     f'#include "{cpp}" // aquascape_cfd; upstream: git checkout src/setup.cpp\n')
    defines = FX3D / "src" / "defines.hpp"
    text = defines.read_text()
    want = {"BENCHMARK": False, "FP16S": fp16s, "EQUILIBRIUM_BOUNDARIES": True, "SUBGRID": True,
            "INTERACTIVE_GRAPHICS": False, "INTERACTIVE_GRAPHICS_ASCII": False, "GRAPHICS": False}
    for name, on in want.items():
        pattern = re.compile(r"^(//)?#define " + name + r"\b", re.M)
        if not pattern.search(text):
            sys.exit(f"defines.hpp: no #define {name}")
        text = pattern.sub(("" if on else "//") + "#define " + name, text, count=1)  # later hits are derived defines
    defines.write_text(text)
    print("setup.cpp and defines.hpp set (FP16S " + ("on" if fp16s else "off, FP32") + "). Rebuild FluidX3D.")


def openings(return_gph, nozzle_d_in):
    holes = {r["hole_id"]: r for r in csv.DictReader(DRILL.open())}

    def yz(h):
        y_in = INSIDE_W_IN - (float(h["x_from_back_in"]) - GLASS_IN)
        z_in = RIM_IN - float(h["y_from_top_in"])
        return y_in * IN, z_in * IN

    q = return_gph * GPH
    discs = [("R1", "inlet", *yz(holes["R1"]), nozzle_d_in * IN, q)]
    for hid in ("D1", "D2"):
        discs.append((hid, "outlet", *yz(holes[hid]), BULKHEAD_BORE_IN * IN, q / 2))
    return discs


def run(a):
    if not EXE.exists():
        sys.exit(f"no {EXE}; build FluidX3D first")
    lines = [
        f"case {a.case}",
        f"dx_m {a.dx_mm / 1000.0:.6f}",
        f"Lx_m {INSIDE_L_IN * IN:.6f}",
        f"Ly_m {INSIDE_W_IN * IN:.6f}",
        f"Lz_m {WATER_IN * IN:.6f}",
        f"sand_m {a.sand_in * IN:.6f}",
        f"t_end_s {a.t}",
        f"report_s {a.report}",
        f"dump_s {','.join(f'{v:g}' for v in sorted({float(v) for v in a.dump.split(',') if v} | {a.t}))}",
        f"u_lat {a.u_lat}",
        f"avg_from_s {max(a.t - a.avg_s, 0.0)}",
        f"sample_s {a.sample}",
    ]
    for name, kind, y, z, d, q in openings(a.return_gph, a.nozzle_d_in):
        lines.append(f"disc {name} {kind} {y:.6f} {z:.6f} {d:.6f} {q:.8f}")
    pumps = []   # (x in from the left pane, push, aim deg, GPH); the tube axis is z (upright) in every case
    for spec in a.pumps.split(",") if a.pumps else []:
        x_in, way = spec.split(":")
        push, aim = PUMP_WAYS[way]
        pumps.append((float(x_in), push, aim, 0.0 if way == "off" else a.gyre_gph))
    slot_len_in = 2 * (GYRE_SLOT_OUT - GYRE_SLOT_IN)
    rows = max(1, round(a.gyre_outlet_in2 / (slot_len_in * a.dx_mm / 25.4)))   # whole cell rows; the log has the area
    for i, (x_in, push, aim, gph) in enumerate(pumps):
        lines.append(f"gyre G{i + 1} {x_in * IN:.6f} {a.gyre_z_in * IN:.6f} z {push} {gph * GPH:.8f} "
                     f"{GYRE_L_IN * IN:.6f} {GYRE_TUBE_IN * IN:.6f} {(INSIDE_W_IN - GYRE_STANDOFF_IN) * IN:.6f} "
                     f"{GYRE_SLOT_IN * IN:.6f} {GYRE_SLOT_OUT * IN:.6f} {GYRE_MOUNT_L_IN * IN:.6f} {GYRE_MOUNT_W_IN * IN:.6f} {rows} "
                     f"{aim:g}")
    for p in a.stl:
        path = Path(p).resolve()
        if not path.exists():
            sys.exit(f"no {path}")
        lines.append(f"stl {path.as_posix()}")
    if a.rfg_tilt > 0:
        lo, hi = (float(v) for v in a.rfg_dwell.split(","))
        lines.append(f"rfg {a.rfg_tilt} {lo} {hi} {a.rfg_ramp} {a.rfg_seed}")
    if a.warm:
        wmeta = {p[0]: p[1] for p in (l.split() for l in (OUT / a.warm / "meta.txt").read_text().splitlines()) if len(p) == 2}
        snaps = sorted((OUT / a.warm).glob("u_*s.bin"), key=lambda p: float(p.stem[2:-1]))
        if not snaps:
            sys.exit(f"{a.warm} has no snapshot to start from")
        lines.append(f"warm {snaps[-1].as_posix()} {wmeta['Nx']} {wmeta['Ny']} {wmeta['Nz']}")
    (EXE.parent / "reef_case.txt").write_text("\n".join(lines) + "\n")
    log = OUT / f"{a.case}.log"
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with log.open("w") as f:
        rc = subprocess.run([str(EXE)], cwd=EXE.parent, stdout=f, stderr=subprocess.STDOUT).returncode
    print(f"exit {rc}, {time.time() - t0:.0f} s wall; log {log}")
    for line in log.read_text(errors="replace").splitlines():
        if "Info:" in line or "Error" in line or "error" in line:
            print(line.strip().strip("|").strip())
    stats = OUT / a.case / "stats.csv"
    if stats.exists():
        rows = stats.read_text().splitlines()
        print("\n".join([rows[0]] + rows[1:][-5:]))


def load(case, t):
    """One run's field: the time average (t None), or the snapshot at t s. Returns meta, discs, u (3, nz, ny, nx), speed,
    flags (0 fluid), a label, a tag."""
    import numpy as np
    d = OUT / case
    meta, discs = {}, []
    for line in (d / "meta.txt").read_text().splitlines():
        parts = line.split()
        if parts[0] == "disc":
            discs.append(parts[1:])
        elif parts[0] in ("gyre", "stl"):
            meta.setdefault(parts[0], []).append(parts[1:])
        else:
            meta[parts[0]] = float(parts[1])
    nx, ny, nz = int(meta["Nx"]), int(meta["Ny"]), int(meta["Nz"])
    flags = np.fromfile(d / "flags.bin", dtype=np.uint8).reshape(nz, ny, nx)
    if t is None:   # time average: mean vector for arrows, mean speed for color
        f = np.fromfile(d / "u_avg.bin", dtype=np.float32).reshape(4, nz, ny, nx)
        label = f"mean over {meta['avg_from_s']:.0f}-{meta['avg_to_s']:.0f} s ({int(meta['avg_samples'])} samples)"
        return meta, discs, f[:3], f[3], flags, label, "avg"
    u = np.fromfile(d / f"u_{t}s.bin", dtype=np.float32).reshape(3, nz, ny, nx)
    return meta, discs, u, np.sqrt((u ** 2).sum(axis=0)), flags, f"snapshot at {t} s", f"{t}s"


ROCK_TAN, SAND_TAN, ROCK_EDGE = "#f1e8d6", "#d9c7a0", "#7a6a4f"   # rock at the cut (and glass), the sand bed, rock outline
ARROW_IN = 1.5      # arrow spacing; a vmax arrow is nearly this long, faster water is drawn at vmax, slower as root speed
DPI = 200           # about 7 px per 4 mm cell at these sheet sizes
PANEL_W_IN = 8.5    # sheet inches per slice; the sheets are meant to be scrolled
EDGES = {           # axis labels, then the walls at the bottom, top, left and right of each kind of slice
    "plan": ("in from the left pane", "in from the front glass", "front glass", "back glass", "left pane", "right pane"),
    "front": ("in from the left pane", "in up from the bottom glass", "sand", "water line", "left pane", "right pane"),
    "end": ("in from the front glass", "in up from the bottom glass", "sand", "water line", "front glass", "back glass"),
}


CORAL_BANDS = [(2, "starved, under 2", "#2b1d4e"), (4, "low, 2 to 4", "#3d6fb4"), (8, "LPS, 4 to 8", "#3daa66"),
               (12, "SPS, 8 to 12", "#f0c330"), (16, "hot, over 12", "#de4a2c")]   # in/s at the coral; reef-keeping rules of thumb


def band_colors():
    from matplotlib.colors import BoundaryNorm, ListedColormap
    cmap = ListedColormap([c for _, _, c in CORAL_BANDS])
    cmap.set_over(CORAL_BANDS[-1][2])
    return cmap, BoundaryNorm([0] + [b for b, _, _ in CORAL_BANDS], cmap.N)


def band_colorbar(fig, m, ax):
    edges = [0] + [b for b, _, _ in CORAL_BANDS]
    cb = fig.colorbar(m, ax=ax, shrink=0.9, extend="max", label="mean speed, in/s")
    cb.set_ticks([(a + b) / 2 for a, b in zip(edges, edges[1:])])
    cb.set_ticklabels([w for _, w, _ in CORAL_BANDS])
    return cb


def slice_panel(ax, kind, img, h, v, uh, uv, vmax, dx_in, title, bands=False, sand_in=None, behind=None):
    """Speed as colour (smooth to vmax, or the coral bands), mean direction as arrows, walls named on the edges.
    Rock is pale tan, the sand bed a deeper tan (sand_in, side and front cuts), so the white arrows show against both.
    behind: all the rock seen through the glass along the cut's normal, drawn as a see-through wash over the flow."""
    import numpy as np
    ax.set_facecolor(ROCK_TAN)
    if sand_in is not None and kind in ("front", "end"):
        ax.axhspan(0, sand_in, color=SAND_TAN, zorder=0.5)
    if bands:
        cmap, norm = band_colors()
        m = ax.pcolormesh(h, v, img, cmap=cmap, norm=norm, shading="nearest")
    else:
        m = ax.pcolormesh(h, v, img, cmap="viridis", vmin=0, vmax=vmax, shading="nearest")
    step = max(1, int(round(ARROW_IN / dx_in)))
    hh, vv = np.meshgrid(h[1:-1:step], v[1:-1:step])
    solid = np.isnan(img[1:-1:step, 1:-1:step])   # no arrows in the rock, the sand or the glass
    ah = np.ma.masked_where(solid, uh[1:-1:step, 1:-1:step])
    av = np.ma.masked_where(solid, uv[1:-1:step, 1:-1:step])
    mag = np.hypot(ah, av)
    cap = vmax * np.sqrt(np.minimum(mag, vmax) / vmax) / np.maximum(mag, 1e-9)   # length goes as root speed: slow water still shows its way
    ax.quiver(hh, vv, ah * cap, av * cap, color="white", edgecolor="black", linewidth=0.4,
              angles="xy", scale_units="xy", scale=vmax / (0.9 * ARROW_IN), units="xy", width=0.05,
              headwidth=4, headlength=4.5, headaxislength=4, minlength=0.5, zorder=3)
    if behind is not None:   # all the rock seen through the glass: a see-through wash; far half solid outline, near half dotted
        from matplotlib.colors import ListedColormap
        far, near = behind
        both = far | near
        if both.any():
            ax.pcolormesh(h, v, np.ma.masked_where(~both, np.ones(both.shape)), cmap=ListedColormap([ROCK_TAN]), alpha=0.6,
                          shading="nearest", zorder=2)
        for part, color, width, style, z in ((far, ROCK_EDGE, 1.6, "solid", 2.5), (near, "black", 2.2, "dotted", 2.6)):
            if part.any():
                ax.contour(h, v, part.astype(float), levels=[0.5], colors=[color], linewidths=width, linestyles=style,
                           zorder=z)
    hl, vl, bottom, top, left, right = EDGES[kind]
    ax.set_title(title, fontsize=12)
    ax.set_xlabel(hl, fontsize=10)
    ax.set_ylabel(vl, fontsize=10)
    box = dict(boxstyle="round,pad=0.2", fc="black", ec="none", alpha=0.55)
    for x, y, text, rot, ha, va in ((0.5, 0.005, bottom, 0, "center", "bottom"), (0.5, 0.995, top, 0, "center", "top"),
                                    (0.005, 0.5, left, 90, "left", "center"), (0.995, 0.5, right, 90, "right", "center")):
        ax.text(x, y, text, transform=ax.transAxes, rotation=rot, ha=ha, va=va, fontsize=9, color="white", bbox=box)
    ax.set_aspect("equal")
    ax.set_xlim(0, h[-2] + 0.5 * dx_in)
    ax.set_ylim(0, v[-2] + 0.5 * dx_in)
    ax.tick_params(labelsize=9)
    return m


def summary(case):
    """Decision numbers from the time-averaged field: speed spread, slow water, the dead zone on the sand."""
    import numpy as np
    meta, discs, u, speed, flags, label, tag = load(case, None)
    dx_in = meta["dx_m"] / IN
    nz, ny, nx = flags.shape
    s = speed / IN
    fluid = flags == 0
    v = s[fluid]
    zs = (np.arange(nz) - 0.5) * dx_in
    xs = (np.arange(nx) - 0.5) * dx_in
    ys = (np.arange(ny) - 0.5) * dx_in
    sand_in = meta["sand_m"] / IN
    kz = int(np.argmin(np.abs(zs - (sand_in + 1.0))))
    plane = s[kz]
    dead = (plane < 1.0) & fluid[kz]
    yy, xx = np.meshgrid(ys, xs, indexing="ij")
    low = (zs >= sand_in) & (zs <= sand_in + 3.0)
    band = s[low][fluid[low]]
    kb = int(np.argmin(np.abs(zs - (sand_in + 0.5))))
    return {
        "window": label,
        "mean in/s": v.mean(),
        "median in/s": float(np.median(v)),
        "% under 1 in/s": 100 * (v < 1.0).mean(),
        "% under 3 in/s": 100 * (v < 3.0).mean(),
        "sand band mean in/s (0-3 in up)": band.mean(),
        "dead zone 1 in up, in2": dead.sum() * dx_in ** 2,
        "dead zone center, in from left": xx[dead].mean() if dead.any() else float("nan"),
        "dead zone center, in from front": yy[dead].mean() if dead.any() else float("nan"),
        "fastest 0.5 in over the sand, in/s": s[kb][fluid[kb]].max(),
    }


def pump_marks(ax, kind, meta):
    """Red arrow from each running pump the way its outlets point; grey ring for a pump that is off. The end view, which
    the pumps are not in, gets a ring at each pump's spot on the back glass and the list in words."""
    import math
    pumps = {(round(float(g[1]) / IN, 1), round(float(g[2]) / IN, 1), round(float(g[8]) / IN, 1), float(g[5]) > 0,
              g[4], round(float(g[9]))) for g in meta.get("gyre", [])}
    running_at = {p[0] for p in pumps if p[3]}
    words = []
    for x, z, yc, running, push, aim_deg in sorted(pumps):
        if not running and x in running_at:
            continue
        aim = math.radians(aim_deg)
        s = 1.0 if push[0] == "+" else -1.0
        d = {"x": 0.0, "y": -math.sin(aim), "z": 0.0}
        d[push[1]] += s * math.cos(aim)
        way = "out at the front glass" if aim_deg >= 45 else {"-x": "left", "+x": "right", "-z": "down", "+z": "up"}[push]
        words.append(f"pump {x:.0f} in from the left pane: " + (f"points {way}" if running else "off"))
        h0, v0, dh, dv = {"plan": (x, yc, d["x"], d["y"]), "front": (x, z, d["x"], d["z"])}.get(kind, (yc, z, d["y"], d["z"]))
        if running and math.hypot(dh, dv) > 0.2:
            (h_lo, h_hi), (v_lo, v_hi) = ax.get_xlim(), ax.get_ylim()
            room = min(((h_hi if dh > 0 else h_lo) - h0) / dh if abs(dh) > 1e-3 else 99,
                       ((v_hi if dv > 0 else v_lo) - v0) / dv if abs(dv) > 1e-3 else 99)
            n = max(1.0, min(4.0, room - 0.3))   # 4 in, shorter where a pane is closer, so the arrow stays in the frame
            ax.annotate("", xy=(h0 + n * dh, v0 + n * dv), xytext=(h0, v0),
                        arrowprops=dict(arrowstyle="-|>", color="red", lw=3, mutation_scale=22))
        else:
            ax.plot(h0, v0, "o", ms=12, mfc="none", mec="red" if running else "grey", mew=2.5)
    if kind in ("end", "front") and words:
        ax.text(0.02, 0.02, "\n".join(words), transform=ax.transAxes, ha="left", va="bottom", fontsize=9, color="red",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="red", alpha=0.85))


def views(a):
    """One case as single-view images, one panel each with its own colorbar, titled in words; numbers.txt beside them."""
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    draw_nine(a.case, None, lambda name: out / f"{name}.png", a.title, a.vmax)
    r = summary(a.case)
    dead = r["dead zone 1 in up, in2"]
    where = (f", centered {r['dead zone center, in from left']:.0f} in from the left pane, "
             f"{r['dead zone center, in from front']:.0f} in from the front glass") if dead else ""
    lines = [a.title,
             f"tank mean: {r['mean in/s']:.1f} in/s",
             f"sand band, 0 to 3 in up: {r['sand band mean in/s (0-3 in up)']:.1f} in/s",
             f"fastest water 0.5 in over the sand: {r['fastest 0.5 in over the sand, in/s']:.0f} in/s",
             f"dead sand 1 in up, under 1 in/s: {dead:.0f} in²{where}",
             f"water under 1 in/s: {r['% under 1 in/s']:.0f}%",
             f"water under 3 in/s: {r['% under 3 in/s']:.0f}%",
             f"case {a.case}, {r['window']}"]
    (out / "numbers.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out)


def draw_nine(case, t, path_for, title, vmax, stamp=""):
    """The nine views of one field: the time average (t None) or the snapshot at t s. path_for(name) is where each goes;
    stamp goes after the title (the time, for animation frames)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    meta, discs, u, speed, flags, label, tag = load(case, t)
    s = speed / IN
    s[flags != 0] = np.nan
    ux, uy, uz = u / IN
    dx_in = meta["dx_m"] / IN
    nz, ny, nx = flags.shape
    xs, ys, zs = ((np.arange(k) - 0.5) * dx_in for k in (nx, ny, nz))
    sand_in = meta["sand_m"] / IN

    def k(arr, v):
        return int(np.argmin(np.abs(arr - v)))

    kz, km, ks = k(zs, sand_in + 1.0), k(zs, sand_in + (WATER_IN - sand_in) / 2), k(zs, WATER_IN - 1.0)
    sides = [("side1_near", "near", 0.75), ("side2_middle", "middle", 0.5), ("side3_far", "far", 0.25)]   # from the right pane
    # everything solid between the panes, seen from the right pane: rock and pumps; not the glass, the hole cells or the sand.
    # Each separate piece over the sand (a bommie, a pump) goes with the half of the tank its middle is in: the far one (the
    # left bommie) and the near one (the right bommie) apart, so the near one draws over it.
    from scipy import ndimage
    solid = flags != 0
    solid[:, [0, -1], :] = solid[:, :, [0, 1, -2, -1]] = False
    solid[(zs < sand_in + 0.5 * dx_in) | (np.arange(nz) >= nz - 1)] = False
    pieces, n_pieces = ndimage.label(solid)
    mid_x = ndimage.mean(np.broadcast_to(xs, solid.shape), pieces, range(1, n_pieces + 1))
    near_ids = [i + 1 for i, x in enumerate(mid_x) if x > INSIDE_L_IN / 2]
    is_near = np.isin(pieces, near_ids)
    silhouette = ((solid & ~is_near).any(axis=2), is_near.any(axis=2))
    # through the front glass the bommies stand side by side: one outline for all of it
    fronts = [("front1_near", "near", 3.0), ("front2_middle", "middle", INSIDE_W_IN / 2), ("front3_far", "far", INSIDE_W_IN - 3.0)]
    front_outline = (solid.any(axis=1), np.zeros((nz, nx), dtype=bool))
    shots = [(name, "front", s[:, ky, :], ux[:, ky, :], uz[:, ky, :], xs, zs,
              f"looking through the front glass, {word} cut, {ys[ky]:.1f} in back from the front glass: {np.nanmean(s[:, ky, :]):.1f} in/s")
             for name, word, ky in ((n, w, k(ys, y)) for n, w, y in fronts)]
    shots += [(name, "end", s[:, :, kx], uy[:, :, kx], uz[:, :, kx], ys, zs,
               f"looking from the right pane, {word} cut, {xs[kx]:.1f} in from the left pane: {np.nanmean(s[:, :, kx]):.1f} in/s")
              for name, word, kx in ((n, w, k(xs, f * INSIDE_L_IN)) for n, w, f in sides)]
    low = (zs >= sand_in) & (zs <= sand_in + 3.0)
    dead = ((s[kz] < 1.0) & (flags[kz] == 0)).sum() * dx_in ** 2
    shots += [("top3_low", "plan", s[kz], ux[kz], uy[kz], xs, ys,
              f"looking down, 1 in over the sand: {np.nanmean(s[low]):.1f} in/s, dead {dead:.0f} in²"),
             ("top2_middle", "plan", s[km], ux[km], uy[km], xs, ys,
              f"looking down at mid-water, {zs[km]:.0f} in up: {np.nanmean(s[km]):.1f} in/s"),
             ("top1_high", "plan", s[ks], ux[ks], uy[ks], xs, ys,
              f"looking down, 1 in under the water line: {np.nanmean(s[ks]):.1f} in/s")]
    for name, kind, img, uh, uv, h, v, words in shots:
        aspect = (v[-2] - v[0]) / (h[-2] - h[0])
        fig, ax = plt.subplots(figsize=(PANEL_W_IN + 2.5, PANEL_W_IN * aspect + 1.5), layout="constrained")
        m = slice_panel(ax, kind, img, h, v, uh, uv, vmax, dx_in, textwrap.fill(title, 80) + f"\n{words}{stamp}", bands=True,
                        sand_in=sand_in, behind={"end": silhouette, "front": front_outline}.get(kind))
        pump_marks(ax, kind, meta)
        cb = band_colorbar(fig, m, ax)
        if t is not None:
            cb.set_label("speed at this instant, in/s")
        fig.savefig(path_for(name), dpi=DPI)
        plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("prepare")
    pp.add_argument("--fp32", action="store_true")              # FP16S storage is the default: within 2% of FP32, 1.9x faster
    pr = sub.add_parser("run")
    pr.add_argument("--case", required=True)
    pr.add_argument("--dx-mm", type=float, default=4.0)
    pr.add_argument("--t", type=float, default=60.0)
    pr.add_argument("--report", type=float, default=1.0)
    pr.add_argument("--dump", default="")                    # snapshot times; the end is always one (warm starts use it)
    pr.add_argument("--pumps", default="")                   # x_in:way per pump: left, right, forward or off
    pr.add_argument("--gyre-z-in", type=float, default=MID_Z_IN)  # tube center, in up from the bottom glass
    pr.add_argument("--gyre-gph", type=float, default=2350.0)  # XF330 rated maximum
    pr.add_argument("--gyre-outlet-in2", type=float, default=GYRE_OUTLET_IN2)  # both cages; less = same flow, faster, harder push
    pr.add_argument("--stl", action="append", default=[])
    pr.add_argument("--rfg-tilt", type=float, default=0.0)   # degrees off the nozzle axis; 0 = straight jet
    pr.add_argument("--rfg-dwell", default="1,5")            # hold time range, s
    pr.add_argument("--rfg-ramp", type=float, default=0.25)  # s per snap
    pr.add_argument("--rfg-seed", type=int, default=1)
    pr.add_argument("--warm", default="")                    # case to start from
    pr.add_argument("--avg-s", type=float, default=20.0)    # average over the last avg-s seconds
    pr.add_argument("--sample", type=float, default=0.25)   # seconds between averaging samples
    pr.add_argument("--sand-in", type=float, default=SAND_IN_DEFAULT)
    pr.add_argument("--return-gph", type=float, default=500.0)
    pr.add_argument("--nozzle-d-in", type=float, default=0.68)   # RFG throat, notes/rfg_jet_pattern.md
    pr.add_argument("--u-lat", type=float, default=0.2)       # jet speed in lattice units: 0.2 is within 1% of 0.1, 2x faster
    pv = sub.add_parser("views")
    pv.add_argument("--case", required=True)
    pv.add_argument("--out", required=True)
    pv.add_argument("--title", required=True)                # the leaf in words, first line of every image
    pv.add_argument("--vmax", type=float, default=6.0)
    a = p.parse_args()
    if a.cmd == "prepare":
        prepare(not a.fp32)
    elif a.cmd == "run":
        run(a)
    else:
        views(a)


if __name__ == "__main__":
    main()
