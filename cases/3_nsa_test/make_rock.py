"""Proof of concept: an open, "NSA"-style scape copied by eye from one photo of a build video, as a watertight STL for
the flow model, for comparison with the solid two_bommies rock. Renders: render_rock.py beside it, into rock/.

    python cases/3_nsa_test/make_rock.py      -> rock.stl beside it (tank metres; needs trimesh and manifold3d)

Read off the photo at about 46 px/in (table width ~ tank length), front-on, perspective ignored:
left: a pillar with a boulder cap, a low mound, an arm bridging pillar to mound high up, a low rail between them, the arch
open in between; right: a tower on two feet with a cave between, a crown, and an arm reaching left over the channel.
Depth is a guess: each structure about 8 in front to back around y = 11 in. Lumps are jittered ellipsoids, unioned;
the surface is pocked with holes. Inches here, x from the left pane, y from the front glass, z from the bottom glass.
"""
import math
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent   # this case
IN = 0.0254
SAND = 2.5
rng = np.random.default_rng(11)


def lump(c, r, squash=(1.0, 1.0, 0.8)):
    """A rough rock lump: an ellipsoid with its vertices jittered."""
    m = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    v = m.vertices * np.array(squash) * r
    v *= 1 + rng.uniform(-0.18, 0.18, (len(v), 1))
    m.vertices = v + np.array(c)
    return m


def path(points, r0, r1, step=1.0, wobble=0.6):
    """Lumps along a polyline, radius r0 to r1, jittered off the line."""
    out = []
    pts = [np.array(p, float) for p in points]
    total = sum(np.linalg.norm(b - a) for a, b in zip(pts, pts[1:]))
    d = 0.0
    for a, b in zip(pts, pts[1:]):
        seg = np.linalg.norm(b - a)
        n = max(1, int(seg / step))
        for k in range(n):
            t = k / n
            p = a + (b - a) * t
            r = r0 + (r1 - r0) * (d + seg * t) / total
            out.append(lump(p + rng.uniform(-wobble, wobble, 3) * np.array([0.6, 1.0, 0.5]), r))
        d += seg
    out.append(lump(pts[-1], r1))
    return out


Y = 11.0   # structures centered front to back
parts = []
# left: pillar with a boulder cap
parts += path([(6.0, Y, 1.5), (5.8, Y + 0.5, 7.0), (6.3, Y - 0.5, 11.5)], 2.6, 1.9)
parts += [lump((5.8, Y, 14.0), 2.4, (1.0, 1.1, 0.75)), lump((7.2, Y + 1.5, 13.2), 1.6)]
# left: low mound under the far end of the arch
parts += [lump((14.0, Y, 3.5), 3.0, (1.0, 1.2, 0.7)), lump((13.6, Y - 1.0, 6.5), 2.2), lump((14.5, Y + 1.0, 8.6), 1.7)]
# left: the arm bridging high, pillar top to mound, and a low rail between them
parts += path([(7.0, Y, 12.5), (10.5, Y + 0.5, 13.0), (14.0, Y - 0.5, 12.4), (16.5, Y, 11.3), (15.0, Y, 9.6)], 1.7, 1.4)
parts += path([(8.0, Y + 0.5, 5.0), (12.0, Y, 5.2)], 1.1, 1.1, wobble=0.3)
# right: two feet with a cave between, a lintel over the cave
parts += [lump((22.5, Y, 4.6), 2.4, (1.0, 1.2, 1.0)), lump((29.0, Y, 4.6), 2.8, (1.0, 1.2, 0.95))]
parts += path([(22.5, Y, 7.2), (25.5, Y + 0.5, 7.9), (28.5, Y, 7.2)], 1.7, 1.7, wobble=0.3)
# right: the tower and its crown
parts += path([(25.5, Y, 9.0), (26.0, Y + 0.5, 12.0), (25.8, Y - 0.5, 14.5)], 2.8, 2.0)
parts += [lump((25.8, Y, 15.8), 2.0, (1.0, 1.0, 0.9)), lump((29.5, Y + 1.0, 9.5), 2.0), lump((30.5, Y - 1.0, 12.0), 1.4)]
# right: the arm reaching left over the channel
parts += path([(24.0, Y, 13.0), (21.0, Y + 0.5, 14.2), (18.0, Y - 0.5, 14.8), (16.0, Y, 14.2)], 1.6, 1.1)

rock = trimesh.boolean.union(parts, engine="manifold")
# pock the surface: small holes where a sphere sits on the skin
skin, _ = trimesh.sample.sample_surface(rock, 60, seed=11)   # seeded: the same rock every run
holes = [trimesh.creation.icosphere(subdivisions=1, radius=rng.uniform(0.5, 1.0)).apply_translation(p) for p in skin]
rock = trimesh.boolean.difference([rock] + holes, engine="manifold")
# keep it inside the clearances: 3 in off the front and side panes, 4.5 in off the back glass; cut flat 1 in into the sand
box = trimesh.creation.box(extents=(35.5 - 6.0, 23.5 - 7.5, 22.1)).apply_translation((3.0 + (35.5 - 6.0) / 2, 3.0 + (23.5 - 7.5) / 2,
                                                                                      SAND - 1.0 + 22.1 / 2))
rock = trimesh.boolean.intersection([rock, box], engine="manifold")
print(f"watertight {rock.is_watertight}, {len(rock.faces)} faces, volume over the sand about "
      f"{trimesh.boolean.intersection([rock, box.copy().apply_translation((0, 0, 1.0))], engine='manifold').volume:.0f} in3")
lo, hi = rock.bounds
print(f"x {lo[0]:.1f}-{hi[0]:.1f}, y {lo[1]:.1f}-{hi[1]:.1f}, z {lo[2]:.1f}-{hi[2]:.1f} in (top {hi[2] - SAND:.1f} in over the sand)")
out = HERE / "rock.stl"
rock.copy().apply_scale(IN).export(out)
print(out)
