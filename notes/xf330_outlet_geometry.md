# Maxspect XF330 Cloud Edition: outlet geometry for the CFD

Notes for the CFD. Part not in hand; numbers are from the Bulk Reef Supply product renders and the Maxspect Gyre 300 Cloud manual (vendor material, not in this repo; links below).

## Use these

- Tube length, end cap to end cap: 10.5 in (BRS); Maxspect 265 mm (10.4 in).
- Cage outside diameter: 1.2 in.
- End cap diameter: 1.0 in.
- Motor and cradle section, centered on the tube: 3.5 in long.
- Slotted cages: 1.8 in to 4.85 in from the tube center, each end. Two cage segments per end, 3.1 in gross per end.
- Slotted length net of rings and collars: about 2.5 in per end, 5.0 in both ends.
- Slot pattern along the cage: 0.22 in pitch, 68% open. Call the cage 60% open after the rings.
- Director face per cage: 1.34 in along the tube by 0.67 in across, louvered, about 85% open. Four faces.
- Outlet area, both ends together: **4 in²**. Bracket 3 to 6 in².
- Exit speed at 2350 GPH through 4 in²: 38 in/s (0.96 m/s). At 3 in²: 50 in/s. At 6 in²: 25 in/s.
- Tube center off the glass: TBD, 1.9 to 2.3 in. BRS gives 2.5 in overall width, Maxspect 75 mm (2.9 in); neither says what the width includes.

## Why 4 in²

Every reading of "outlet" that passes the rated flow at a believable speed lands in the same band:

| Outlet taken as | Area, both ends | Speed at 2350 GPH |
|---|---|---|
| Director faces only, net of louvers | 3.0 in² | 50 in/s |
| 120° discharge arc of the cage, 5.0 in slotted, 60% open | 3.8 in² | 40 in/s |
| 180° arc, 60% open | 5.7 in² | 27 in/s |
| 180° arc, gross, no ribs deducted | 9.4 in² | 16 in/s |
| 360° cage, gross | 19 in² | 8 in/s |

The 10 to 11 in² figure is the half-cage with nothing deducted for ribs. A crossflow rotor does not discharge over its whole half-cage, and the ribs are a third of the cage. The 3 in² figure is a single 0.45 in band. Both are definitions, not measurements. 4 in² is the middle of the readings that survive; momentum goes as Q²/A, so the bracket is a factor 2 in push, not 3.5.

## How measured

- Image: the BRS listing's `...-fr.webp` render, 1200 × 1200, pump straight on, tube horizontal.
- Scale: dark pixels (grey < 128) span x = 11 to 1186 at the tube's center rows: 1175 px for 10.5 in, 112 px/in. At 265 mm the scale is 112.6 px/in; the two anchors agree within 1%.
- Pump center x = 599. Directors (top edge at y = 307 for 20 px or more, read right of center and mirrored): x = 402 to 795 is the motor and cradle (3.5 in); directors x = 55 to 402 and 795 to 1141 (3.1 in per end). End caps: 45 px (0.4 in) each.
- End cap: y = 363 to 477 at x = 29 and 1168, 114 px, 1.03 in. Tube center row y = 418.
- Cage: bottom edge y = 486 under the directors; radius 68 px from the center row, 136 px diameter, 1.22 in. The top edge is under the director.
- Slots: rows y = 455 to 465 through the lower cage, columns 60 to 215 and 985 to 1135, threshold grey < 40: open runs 17 px, ribs 7 to 8 px, pitch 25 px.
- Director face: black from y = 319 to 394 at x = 100 and 165 (75 px, 0.67 in); row y = 360 shows five open runs of 25 to 28 px with 4 to 5 px vanes between over x = 60 to 215 (150 px, 1.34 in).
- Cross-check: manual page 6, installation drawing, bare pump, orthographic side view. Rendered at 4×: pump 681 px long over 265 mm; cage height 77 px (30 mm, 1.18 in); motor 85 px (33 mm, 1.3 in); cradle 91 to 95 px (36 mm). Cage diameter agrees with the render within 1%.

## Reproduce

- `python notes/measure_xf330.py RENDER.webp MANUAL.pdf`: every number above, from the render and the manual page, with the outlet readings at 2350 GPH.
- Inputs: the `...-fr.webp` render from the BRS listing, https://www.bulkreefsupply.com/gyre-xf330-cloud-edition-standard-package-2350-gph-maxspect.html, and the Maxspect Gyre 300 Cloud manual PDF (maxspect.com), page 6 of the English section. Save both and pass their paths.
- Length and magnet: the same BRS listing.

## Not anchors

- The cable connector. Maxspect waterproof screw connector, no standard size, and it lies closer to the camera than the pump.
- The external magnet (5 × 0.5 × 1.75 in, BRS). In the renders it only appears ghosted through glass in a perspective shot.
- Manual page 8, exploded view. Stylized: the cage is drawn 1.6× taller than the motor. Good for part order, not for size.
- The perspective renders (`cv1`, `cv2c`, `le`). Fine for reading the slot and director pattern, not for scale.

## Assumptions

- Directors clipped on, louvers at straight flow, as shipped. The louvers steer along the tube axis (swing, wide, spot); they do not change the area band.
- 2350 GPH as published. It is a vendor rating of flow through the pump. No published velocity-at-distance test exists for any Gyre; the one meter test found (Reefs.com, XF-130) reads at the discharge face and its figure is not readable.

## Open

- Tube center off the glass: measure the cradle when P0260 arrives.
- Outlet area: caliper the cage and director when P0260 arrives; a bucket or velocity test settles the arc.
