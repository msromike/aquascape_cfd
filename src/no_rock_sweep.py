"""Open-tank pump sweep: two upright XF330 in the back corners, 3 in off each side pane, both on, every way of pointing the
pair that does not aim at its own pane, at three heights. This is the sweep that picked the pump setup; the rock was shaped
on its winner.

    python src/no_rock_sweep.py              (runs what is missing, then draws the views and writes the ranking)
    python src/no_rock_sweep.py --views-only

Ways: left or right along the back glass, or forward (out at the front glass). Full speed, RFG 20 deg, 60 s each, warm from
the run before (the first from FIRST_WARM, any settled open-tank run on the same grid; a cold 90 s run if it is missing).
Heights: tube center at mid-water, 2 in lower, and lowest with the tube 1 in over the sand.
Out: flow_images/no_rock/pumps_<z>in_up/<mount>/: the nine views and numbers.txt. A mount folder with a $ in front of its
name is kept and written into (the $ marks a pick by hand).
flow_images/no_rock/ranking.csv: every setup's numbers, best tank mean first.
"""
import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cfd_tank as cfd  # noqa: E402

OUT = cfd.ROOT / "flow_images" / "no_rock"
SAND = cfd.SAND_IN_DEFAULT
PUMPS_X = (3.0, cfd.INSIDE_L_IN - 3.0)
MOUNTS = [(a, b) for a in ("right", "forward") for b in ("left", "forward")]   # left pump's way, right pump's way
HEIGHTS = [cfd.MID_Z_IN, cfd.MID_Z_IN - 2.0, SAND + 1.0 + cfd.GYRE_L_IN / 2]   # tube center, in up from the bottom glass
FIRST_WARM = "cmid_right_alone"
SAND_MOVES_IN_S = 13.0            # low end of the 1-2 mm aragonite estimate, 0.5 in over the sand


def case(z, a, b):
    return f"nr_corners_{z:.1f}_{a}_{b}".replace(".", "p")


def done(name):
    return (cfd.OUT / name / "u_avg.bin").exists()


def run_one(name, z, a, b, warm):
    args = ["run", "--case", name, "--rfg-tilt", "20", "--gyre-z-in", f"{z:.2f}",
            "--pumps", f"{PUMPS_X[0]:.2f}:{a},{PUMPS_X[1]:.2f}:{b}"]
    args += ["--t", "60", "--warm", warm] if warm else ["--t", "90"]
    t0 = time.time()
    rc = subprocess.run([sys.executable, str(Path(cfd.__file__)), *args], capture_output=True, text=True)
    line = next((l for l in rc.stdout.splitlines() if l.startswith("exit")), (rc.stdout + rc.stderr)[-300:])
    print(f"run {name}" + (f" --warm {warm}" if warm else " cold") + f": {line} ({time.time() - t0:.0f} s)", flush=True)


def run_all():
    warm = FIRST_WARM if done(FIRST_WARM) else ""
    for z in HEIGHTS:
        for a, b in MOUNTS:
            name = case(z, a, b)
            if not done(name):
                run_one(name, z, a, b, warm)
            if done(name):
                warm = name


def mount_dir(z, a, b):
    where = OUT / f"pumps_{z:.1f}in_up"
    name = f"left-pump-{a}_right-pump-{b}"
    return where / ("$" + name) if (where / ("$" + name)).is_dir() else where / name


def views_and_ranking():
    rows = []
    for z in HEIGHTS:
        for a, b in MOUNTS:
            name = case(z, a, b)
            if not done(name):
                print(f"views: {name} not run, skipped", flush=True)
                continue
            folder = mount_dir(z, a, b)
            title = (f"Open tank, corner pumps, tube center {z:.1f} in up ({z - SAND:.1f} in over the sand); "
                     f"left pump points {a}, right pump points {b}: both on")
            cfd.views(SimpleNamespace(case=name, out=str(folder), title=title, vmax=6.0))
            r = cfd.summary(name)
            rows.append({"setup": f"tube center {z:.1f} in; left pump {a}, right pump {b}; both on",
                         "folder": folder.relative_to(OUT).as_posix(),
                         "tank mean in/s": round(r["mean in/s"], 1),
                         "sand band in/s": round(r["sand band mean in/s (0-3 in up)"], 1),
                         "dead sand in2": round(r["dead zone 1 in up, in2"]),
                         "% water under 1 in/s": round(r["% under 1 in/s"]),
                         "% water under 3 in/s": round(r["% under 3 in/s"]),
                         "fastest 0.5 in over the sand in/s": round(r["fastest 0.5 in over the sand, in/s"]),
                         "sand moves": "yes" if r["fastest 0.5 in over the sand, in/s"] > SAND_MOVES_IN_S else "no",
                         "case": name})
    rows.sort(key=lambda r: -r["tank mean in/s"])
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "ranking.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(OUT / "ranking.csv", flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--views-only", action="store_true")
    a = p.parse_args()
    if not a.views_only:
        run_all()
    views_and_ranking()


if __name__ == "__main__":
    main()
