# VCA Random Flow Generator, 3/4 in (P0280): jet pattern for the CFD

Notes for the CFD agent. Part not in hand. From US 11,071,990 B1 (this folder) and the BRS listing for the 3/4 in nozzle.

## Use these

- Central jet: 500 GPH through a 0.68 in throat, 88 in/s (2.2 m/s). Re about 38,000.
- Pattern: one jet, snapped among five fixed directions, 72° apart around the nozzle axis.
- Tilt off the axis: **20°**. Bracket 15 to 25.
- Hold per position: random, 1 to 5 s at 500 GPH. Snap, not sweep: ramp 0.25 s or less.
- Time average: a hollow cone of half-angle 20° about the axis. Instantaneous: a single jet in one of the five slots.
- Five peripheral jets always on, same five directions, 90° helical twist. They are entrained tank water, not pump flow: no extra momentum, no extra flow to inject.
- Inject 500 GPH at the throat speed, not spread over the 1.6 in bell outlet. The bell carries throat flow plus entrained water; 500 GPH over the bell face would be 4× too slow.
- Nozzle envelope: 2.75 in long, 1.7 in OD at the outlet (BRS). Bell 1.85 in from rim to base, 1.14 in at the waist, 1.31 in at the base. Intake A 1.36 in, throat C 0.68 in.

## What the patent gives

- Shape, as ratios of the throat C: intake A ≈ 2C, sidewall B ≈ 1.1C, bell opening D ≈ A, bell waist ≈ 1.7C, bell outlet ≈ 2.5C, central column = C. Five vanes, each wrapped 90° around the bell, ending halfway between the waist and the outlet.
- Mechanism: the central jet snaps toward whichever of the five channels has the lower pressure at its port, holds, then snaps to another. Random order.
- Rate: faster with flow. "A few seconds to under a second" at high flow for a given nozzle, "every thirty to sixty seconds" at low flow. The 3/4 in nozzle is listed at 420 to 500 GPH optimal, so 500 GPH is the fast end.

## What the patent does not give

- The deflection angle. No number anywhere in the text or claims.
- The hold-time distribution at any stated flow, or any flow number at all.
- Any velocity or thrust.

## Where 20° comes from

The jet, when snapped, runs along one channel against the bell wall and leaves at the wall's angle at the lip. FIG. 1 is an orthographic side view. Traced (`measure_rfg.py`):

| Fit over the top of the bell | Wall angle off the axis |
|---|---|
| 0.17 in below the rim | 24° |
| 0.39 in | 21° |
| 0.61 in | 19° |

A Coanda-attached jet detaches at the lip along the local wall, so 24° is the top of the bracket; it has thickness C and some of it is still coming off the straighter wall below, so 20° is the center. The drawing's rim-to-waist and base-to-waist ratios read 1.49 and 1.15 against the patent's 1.47 and 1.18, so the drawing is to proportion.

## Not from the patent, and how to close it

- The hold times at 500 GPH and the real angle: dye test when P0280 arrives, 10 s of video from above and from the side.
- A nozzle-scale FluidX3D run could show the snapping: a 3 in box at 0.5 mm cells is cheap, but the throat is at Re 38,000 and the snap is a Coanda bistability; a coarse lattice may hold the jet on one wall or never attach it. A model check, not a design input.

## Reproduce

- `python notes/measure_rfg.py SHEET01.png`: bell widths, ratios, wall angles, throat speed, from sheet 1 of the patent drawings.
- The sheets: the patent PDF, https://patentimages.storage.googleapis.com/5c/2a/6c/27b5d5ad12b66a/US11071990.pdf, rendered at 200 dpi (pymupdf); sheet 1 is FIG. 1. The text is at https://patents.google.com/patent/US11071990B1/en.
- 3/4 in nozzle size and flow range: BRS, https://www.bulkreefsupply.com/3-4-loc-line-random-flow-generator-vivid-creative-aquatics.html (2.75 in L × 1.7 in OD, 200 GPH min, 420 to 500 GPH optimal).

## Against the CFD as it stands

`cfd_tank.cpp` already snaps R1 among five positions on a cone with a random hold and a short ramp. Set tilt 20 (runs so far used 0, 15, 30). The R1 disc is 0.75 in; the throat is 0.68 in, so the jet momentum at 500 GPH is 20% higher than a 0.75 in bore gives. Use 0.68 if the disc can be set, else note the 20%.
