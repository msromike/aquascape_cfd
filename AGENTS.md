# aquascape_cfd: notes for an AI picking this up

Read this before touching the code. It is what the model that built this would want told.

## What it is

A FluidX3D setup for a reef display tank, a Python driver, and a rock-shaping tool. One tank, one pump setup, one rock,
all decided; the pictures in `flow_images/` are the result. Everything else is a path to regenerate or change them.

## How a run works

1. `src/cfd_tank.py prepare` overwrites `FluidX3D/src/setup.cpp` with two lines (include `setup.hpp`, include this
   repo's `src/cfd_tank.cpp` by absolute path) and toggles seven `#define`s in `FluidX3D/src/defines.hpp`
   (FP16S on, EQUILIBRIUM_BOUNDARIES on, SUBGRID on, BENCHMARK and the graphics off). Then FluidX3D is rebuilt.
   `git checkout src/setup.cpp src/defines.hpp` in the FluidX3D clone puts it back.
2. `run` writes `FluidX3D/bin/reef_case.txt` (one key per line: box, sand, discs for the holes, `gyre` lines for the
   pumps, `stl` paths, `rfg`, `warm`) and runs the exe. `cfd_tank.cpp` reads that file; it has no tank numbers of its own.
3. The exe writes `reef_out/<case>/`: `flags.bin` (uint8, 0 fluid), `u_<t>s.bin` snapshots (3 float32 blocks, m/s),
   `u_avg.bin` (mean u, v, w, then mean speed), `stats.csv`, `meta.txt`.
4. `views` loads `u_avg.bin` and draws nine pictures (`draw_nine`); `summary()` makes the numbers.

Units: the solver works in metres and seconds; every number a person sees is inches and in/s. `IN = 0.0254`.

## Settings that were checked, and what they cost

- 4 mm grid: reads about 10% slow against 3 mm, same pattern. Screening grid; good enough to rank layouts.
- `--u-lat 0.2`: jet speed in lattice units; within 1% of 0.1 and twice as fast.
- FP16S: within 2% of FP32, 1.9x faster.
- Warm start (`--warm`) 45-60 s from a settled run: within 2% of a cold 90 s run.
- The last 20 s are averaged (`--avg-s 20`, a sample every 0.25 s).
- A 90 s cold run is about 3 minutes; 60 s warm about 2.

## Traps

- Voxel trap: on the 4 mm grid, 10 in and 30 in land on cell centers and FluidX3D's ray voxelizer miscounts on a rod
  edge there (a phantom wall). `rock_rods.py stl` shifts the mesh 0.1 mm to dodge it. If you change `dx` or make rock by
  another route, check for phantom solid cells against your geometry before believing a run.
- Don't edit `cfd_tank.py` while a batch is running: each run reimports it.
- `prepare` hard-codes an absolute include path; rerun it after moving this folder.
- `rock_rods.py update` reads paint by diffing the `*_edit.png` canvas against `history/base_*.png`. Never redraw over a
  painted canvas; `draw` refuses unless `update` consumed it.
- One color, one height, everywhere in the rod tool. Do not invent a filter or threshold on the paint without saying
  so to the person painting: every square a stroke touches takes that color's height.
- Pump geometry (`GYRE_*`) is from a product render and a manual drawing, not a pump in hand. The outlet area
  (`GYRE_OUTLET_IN2`, 4 in²) sets how hard the jet pushes; the bracket is 3 to 6. Say so when quoting speeds.
- The water line is a no-slip lid (FluidX3D bounce-back). It drags the top inch a little.

## Changing the tank

- Box and water: `INSIDE_L_IN`, `INSIDE_W_IN`, `RIM_IN`, `WATER_IN`, `SAND_IN_DEFAULT` in `src/cfd_tank.py`.
- Holes: `tank/holes.csv`, measured on the outside of the left pane from the back and the top.
- Pumps: `--pumps "x:way,x:way"` (x in from the left pane; left, right, forward, off), `--gyre-z-in` height,
  `--gyre-gph`. Another pump model means new `GYRE_*` numbers; `notes/` shows how these were measured.
- Return nozzle: `--return-gph`, `--nozzle-d-in`, `--rfg-tilt` (0 for a plain nozzle).
- Rock clearances and pump positions for the rod tool: `CLEAR_IN`, `PUMPS_X` in `src/rock_rods.py`.

## What was decided here, for context

Pumps upright in the back corners at mid-water, the left one aimed at the front glass, the right one along the back
glass, both on: a loop (front leg fast, return slow across the back two thirds). Rock as two bommies, 42% of the floor,
with an overhang open to the channel between them. The flow run with the rock lost about a tenth of the mean speed and
gained dead sand behind the right bommie; the owner chose to tune that with pump speed in the wet tank, not with rock.
