"""Corner view of the rock rods in Blender: run by rock_rods.py draw, never by hand.

    blender --background --factory-startup --python src/rock_rods_blender.py -- scene.json out_dir

scene.json (inches, x from the left pane, y from the front glass, z from the bottom glass): tank L W rim water sand,
rods [[x0, x1, y0, y1, z_bottom, z_top, [r, g, b]]], pumps [[x0, x1, y0, y1, z0, z1]], holes [[name, y, z, dia]],
views {name: [eye x, eye y]}: one PNG each in out_dir.
Workbench engine: flat colors, studio light, shadows and cavity; seconds, not minutes.
"""
import json
import math
import sys

import bmesh
import bpy
from mathutils import Vector


def mat(name, rgb):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    return m


def boxes(name, items, materials):
    """One object of boxes: items are (x0, x1, y0, y1, z0, z1, material index)."""
    bm = bmesh.new()
    for x0, x1, y0, y1, z0, z1, k in items:
        v = [bm.verts.new(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                       (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            bm.faces.new([v[i] for i in f]).material_index = k
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    for m in materials:
        me.materials.append(m)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def frame(name, x0, x1, y0, y1, z, rgb, t=0.12):
    """A thin rectangle of bars at height z: tank edges and the water line."""
    k = [mat(name, rgb)]
    return boxes(name, [(x0 - t, x1 + t, y0 - t, y0 + t, z - t, z + t, 0), (x0 - t, x1 + t, y1 - t, y1 + t, z - t, z + t, 0),
                        (x0 - t, x0 + t, y0 - t, y1 + t, z - t, z + t, 0), (x1 - t, x1 + t, y0 - t, y1 + t, z - t, z + t, 0)], k)


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    s = json.load(open(args[0]))
    L, W, rim, water, sand = s["L"], s["W"], s["rim"], s["water"], s["sand"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    colors = sorted({tuple(r[6]) for r in s["rods"]})
    mats = [mat(f"rod{i}", c) for i, c in enumerate(colors)]
    boxes("rods", [(x0, x1, y0, y1, z0, zt, colors.index(tuple(c))) for x0, x1, y0, y1, z0, zt, c in s["rods"]], mats)
    boxes("sand", [(0, L, 0, W, 0, sand, 0)], [mat("sand", (0.80, 0.72, 0.56))])
    boxes("pumps", [(*p, 0) for p in s["pumps"]], [mat("pump", (0.12, 0.12, 0.13))])
    for z in (0.0, rim):
        frame(f"edge{z:g}", 0, L, 0, W, z, (0.25, 0.25, 0.28))
    frame("water", 0, L, 0, W, water, (0.25, 0.5, 0.85), t=0.08)
    posts = [(x - 0.12, x + 0.12, y - 0.12, y + 0.12, 0, rim, 0) for x in (0, L) for y in (0, W)]
    boxes("posts", posts, [mat("post", (0.25, 0.25, 0.28))])
    for name, y, z, dia in s["holes"]:
        bpy.ops.mesh.primitive_cylinder_add(radius=max(dia / 2, 0.3), depth=0.3, location=(0.15, y, z), rotation=(0, math.pi / 2, 0))
        bpy.context.active_object.data.materials.append(mat(f"hole_{name}", (0.1, 0.1, 0.1)))

    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light, sh.color_type = "STUDIO", "MATERIAL"
    sh.show_shadows, sh.show_cavity = True, True
    sh.cavity_type = "WORLD"
    scene.display.shadow_focus = 0.6
    scene.display.render_aa = "8"
    world = bpy.data.worlds.new("w")
    world.color = (0.93, 0.94, 0.96)
    scene.world = world
    scene.render.resolution_x, scene.render.resolution_y = 1600, 1050
    scene.render.image_settings.file_format = "PNG"

    aim = Vector((L / 2, W / 2, rim / 2))
    for name, (ex, ey) in s["views"].items():   # each off a corner, a little above the rim
        eye = Vector((ex, ey, rim + 22))
        bpy.ops.object.camera_add(location=eye, rotation=(aim - eye).to_track_quat("-Z", "Y").to_euler())
        cam = bpy.context.active_object
        cam.data.lens_unit, cam.data.angle = "FOV", math.radians(42)
        cam.data.clip_end = 1000
        scene.camera = cam
        scene.render.filepath = f"{args[1]}/{name}.png"
        bpy.ops.render.render(write_still=True)


main()
