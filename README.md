# aquascape_cfd

Water flow in a reef tank, modeled before the tank is wet. Two wavemakers, a return nozzle, a sand bed and a rock
structure, run through FluidX3D (a GPU lattice-Boltzmann solver) and drawn as nine cuts through the water: looking down
at three heights, through the front glass at three depths, from the side at three stations. Plus a tool for shaping the
rock in MS Paint and seeing what the shape does to the flow.

Built for one 90 gallon rimless tank (35.5 × 23.5 in inside, 22.1 in of water, 2.5 in of sand). The tank numbers sit in
one block at the top of `src/cfd_tank.py`; the holes in `tank/holes.csv`. Changing them to your tank is a short job for
you or your AI; see `AGENTS.md`.

This is a hobby project, shared because it was fun and might save someone the same 10-15 hours. It runs; it has not been
checked against a real tank. Treat the numbers as "which layout is better", not "what speed is this coral seeing".

## What it shows

Open tank, pumps only, 20 s average, looking down 1 in over the sand:

![open tank, sand](cases/1_open_tank/flow/top3_low.png)

The same pumps with the rock in. Side cut through the main rock, looking from the right pane. The solid tan is the rock
the cut passes through; the pale wash is all the rock behind the glass, the far one outlined solid, the near one dotted:

![rock, side cut](cases/2_two_bommies/flow/side3_far.png)

The rock itself, shaped as 1 in square rods and rendered in Blender:

![rock from the right front](cases/2_two_bommies/rock/corner_right_front.png)

Each case is one folder in `cases/`: `rock/` (the rock's views and renders), `rock.stl`, and `flow/` (nine views plus
`numbers.txt`). `3_nsa_test` is an open, holey scape copied by eye from a photo, run the same way for comparison: big
openings carry 2-3 in/s, about what that spot gets with no rock at all.

## Videos

The averages above hide most of what the water does. `src/flow_anim.py` draws every 0.2 s of a run and joins the
frames: 20 s of tank time played at 2x speed, one 10 s video per view. The "starved" patches turn out to get swept every few
seconds; the front-glass jet split wanders. Videos are not in git; these five are hosted by GitHub.

Side cut through the main rock (far):

https://github.com/user-attachments/assets/597150b7-91bd-4960-9b3c-4bdcb6e5fb64

Side cut through the overhang (middle):

https://github.com/user-attachments/assets/48004576-23b3-4228-a583-2229f0e54342

Side cut through the right rock (near):

https://github.com/user-attachments/assets/69d7d781-2ac6-481d-a29f-6e55cc72a262

Through the front glass, mid-depth:

https://github.com/user-attachments/assets/d2c2f51c-d70c-4568-a903-16ca76596a7f

Looking down, 1 in over the sand:

https://github.com/user-attachments/assets/df88e1ec-7b96-4f2d-b04e-c0fe462247af

## What you need

- A GPU with OpenCL (any recent NVIDIA, AMD or Intel). A 90 s run on a 4 mm grid is about 3 minutes on a mid-range card.
- [FluidX3D](https://github.com/ProjectPhysX/FluidX3D), cloned beside this folder (or anywhere, with `FLUIDX3D` set to
  its path), and whatever builds it on your machine (Visual Studio Build Tools on Windows; `make` elsewhere).
- Python 3.12 with `pip install -r requirements.txt`.
- [Blender](https://www.blender.org/) 4 or 5 for the rock renders (`BLENDER` env var, or on PATH).
- Windows was the build machine. Nothing is Windows-only on purpose except the default Blender path and the Arial font
  the rod tool draws with.

## Quick start

```
python src/cfd_tank.py prepare            # points FluidX3D's setup.cpp at src/cfd_tank.cpp, sets its defines
# build FluidX3D (Release, x64)
python src/cfd_tank.py run --case open_tank --t 90 --pumps "3:forward,32.5:left" --rfg-tilt 20
python src/cfd_tank.py views --case open_tank --out cases/1_open_tank/flow --title "Open tank"
python src/rock_rods.py draw 2_two_bommies  # the rock's views to paint on, and the Blender corners
python src/rock_rods.py stl 2_two_bommies
python src/cfd_tank.py run --case rock --t 60 --warm open_tank --pumps "3:forward,32.5:left" --rfg-tilt 20 --stl cases/2_two_bommies/rock.stl
python src/cfd_tank.py views --case rock --out cases/2_two_bommies/flow --title "With the rock"
```

Raw fields land in `FluidX3D/bin/reef_out/<case>/` (about 140 MB a run). `--warm` starts a run from another's end
instead of still water: half the time, same answer.

## Shaping rock

`src/rock_rods.py` treats the rock as a grid of 1 in square rods on the sand, each its own height. It draws a top view,
a front view and a side view, with a copy of each to paint on in MS Paint. Eyedrop a color off the drawing and paint:
green 3 in, yellow 5, orange 8, red 10, purple 13; white cuts a rod out; a color on open sand adds a rod. Then
`python src/rock_rods.py update NAME` reads the paint, redraws, and rerenders the Blender corners. Undercuts (ledges,
overhangs) are set in words: `set NAME --x 14:18 --y 8:17 --bottom 3.5`. A floating check refuses rock with nothing
holding it up. `stl` writes the shape for the flow run.

`cases/2_two_bommies/rock/` is the shape in the pictures: heights.csv and bottoms.csv are the whole record. A new
case starts as a copy of an old case folder, renamed.

## What is in the pictures

- Color: 20 s mean speed, in inches per second, in five bands: starved (under 2), low (2-4), LPS (4-8), SPS (8-12),
  hot (over 12). Rules of thumb from reef-keeping, not measurements.
- Arrows: mean direction in the plane of the cut; motion through the page does not show. Length goes as the square root
  of speed so slow water still shows its way.
- Red arrow or ring: a pump and the way it points. Pale tan: rock. Deeper tan: the sand bed.
- `numbers.txt`: tank mean, sand band, fastest water over the sand (sand starts to move at about 13 in/s), dead sand.

## Layout

```
src/        cfd_tank.py (prepare, run, views), cfd_tank.cpp (the FluidX3D setup), rock_rods.py (+ rock_rods_blender.py),
            flow_anim.py (videos)
tank/       holes.csv: return and drain positions
notes/      how the pump and nozzle geometry were measured off vendor pictures, with the scripts
cases/      one folder per scenario: 1_open_tank, 2_two_bommies, 3_nsa_test; each rock/ (rods or the script that
            made it, views, renders), rock.stl (what the solver loads), flow/ (nine views, numbers.txt; videos ignored)
```

## License

MIT for everything here (see `LICENSE`). FluidX3D is not included and has its own license: no commercial use, no
military use, publish altered source with published results. `src/cfd_tank.cpp` and the defines `prepare` sets are the
altered source; that is why they are here.
