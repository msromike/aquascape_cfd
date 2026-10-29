"""Animations of one run: the nine views (cfd_tank.draw_nine) at every saved snapshot, joined into one MP4 per view.

    python src/flow_anim.py CASE OUT_DIR --title "words" [--fps 10] [--scale 0.5] [--workers 6] [--keep] [--encode-only]

The run must have saved snapshots (cfd_tank.py run --dump 0.2,0.4,... --report 0.2; 100 of them for 20 s). Frames are
drawn into FluidX3D/bin/reef_out/CASE/frames/<view>/, six snapshots at a time; the videos go to OUT_DIR/<view>.mp4,
--scale 0.5 at half width (8-13 MB each instead of 14-25). Each frame is stamped with its tank time and the playback
speed, worked out from the snapshot spacing and --fps (0.2 s snapshots at 10 fps play at 2x). --keep leaves the frames
and snapshots; --encode-only reuses kept frames (a second size). Otherwise the frames and every snapshot but the last
(the warm start) are deleted.
"""
import argparse
import shutil
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cfd_tank as cfd  # noqa: E402

VIEWS = ["front1_near", "front2_middle", "front3_far", "side1_near", "side2_middle", "side3_far",
         "top1_high", "top2_middle", "top3_low"]


def snapshots(case):
    """(time, name tag) of every saved snapshot, in time order."""
    return sorted((float(p.stem[2:-1]), p.stem[2:-1]) for p in (cfd.OUT / case).glob("u_*s.bin"))


def frame(job):
    case, title, i, t, tag, speed = job
    frames = cfd.OUT / case / "frames"
    cfd.draw_nine(case, tag, lambda name: frames / name / f"{i:03d}.png", title, 6.0,
                  stamp=f"; at {t:.1f} s, played at {speed:g}x speed")
    return i


def main():
    p = argparse.ArgumentParser()
    p.add_argument("case")
    p.add_argument("out")
    p.add_argument("--title", required=True)
    p.add_argument("--fps", type=int, default=10)   # 0.2 s snapshots at 10 fps: 2x speed
    p.add_argument("--scale", type=float, default=1.0)   # frame width as a share of the drawn 2200 px
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--keep", action="store_true")
    p.add_argument("--encode-only", action="store_true")
    a = p.parse_args()
    snaps = snapshots(a.case)
    frames = cfd.OUT / a.case / "frames"
    if not a.encode_only:
        times = [t for t, _ in snaps]
        speed = round(float(np.median(np.diff(times))) * a.fps, 2)   # tank seconds per second of video
        for v in VIEWS:
            (frames / v).mkdir(parents=True, exist_ok=True)
        jobs = [(a.case, a.title, i, t, tag, speed) for i, (t, tag) in enumerate(snaps)]
        with Pool(a.workers) as pool:
            for n, _ in enumerate(pool.imap_unordered(frame, jobs), 1):
                if n % 10 == 0 or n == len(jobs):
                    print(f"frames: {n} of {len(jobs)} snapshots", flush=True)

    import imageio.v2 as imageio
    from PIL import Image
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for v in VIEWS:
        with imageio.get_writer(out / f"{v}.mp4", fps=a.fps, codec="libx264", quality=8, macro_block_size=2,
                                ffmpeg_log_level="error") as w:
            for f in sorted((frames / v).glob("*.png")):
                im = Image.open(f).convert("RGB")
                if a.scale != 1.0:   # even pixel counts keep the encoder from resizing again
                    im = im.resize((int(im.width * a.scale) // 2 * 2, int(im.height * a.scale) // 2 * 2), Image.LANCZOS)
                w.append_data(np.asarray(im))
        print(out / f"{v}.mp4", flush=True)
    if not a.keep:
        shutil.rmtree(frames)
        for t, tag in snaps[:-1]:
            (cfd.OUT / a.case / f"u_{tag}s.bin").unlink()


if __name__ == "__main__":
    main()
