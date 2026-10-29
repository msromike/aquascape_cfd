"""Render any case's rock.stl (millimetres around the tank center, placed by the case's place.json) in the tank: front-on, and from the right front corner.

    blender --background --factory-startup --python src/render_stl.py -- ABSOLUTE/cases/CASE/rock.stl ABSOLUTE/cases/CASE/rock
(absolute paths: Blender resolves relative ones against the drive root)
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

L, W, RIM, WATER, SAND = 35.5, 23.5, 23.25, 22.1, 2.5


def mat(name, rgb):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    return m


def box(name, x0, x1, y0, y1, z0, z1, rgb):
    bm = bmesh.new()
    v = [bm.verts.new(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                   (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        bm.faces.new([v[i] for i in f])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    ob = bpy.data.objects.new(name, me)
    me.materials.append(mat(name, rgb))
    bpy.context.scene.collection.objects.link(ob)


args = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
bpy.ops.wm.stl_import(filepath=args[0])
rock = bpy.context.selected_objects[0]
rock.scale = (1 / 25.4,) * 3   # mm to the scene's inches
place_file = Path(args[0]).parent / "place.json"
place = json.loads(place_file.read_text()) if place_file.exists() else {}
move = [float(v) / 25.4 for v in place.get("move_mm", [0, 0, 0])]
turn = math.radians(float(place.get("turn_deg", 0)))
xs = [v.co.x / 25.4 for v in rock.data.vertices]
ys = [v.co.y / 25.4 for v in rock.data.vertices]
cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
c, s = math.cos(turn), math.sin(turn)
rock.rotation_euler = (0.0, 0.0, turn)   # about the rock's own center, as cfd_tank.py does, then the move
rock.location = (L / 2 + cx - (c * cx - s * cy) + move[0], W / 2 + cy - (s * cx + c * cy) + move[1], move[2])
rock.data.materials.append(mat("rock", (0.86, 0.80, 0.68)))
box("sand", 0, L, 0, W, 0, SAND, (0.80, 0.72, 0.56))
t = 0.12
for z in (0.0, RIM):
    for x0, x1, y0, y1 in ((0, L, 0, 0), (0, L, W, W), (0, 0, 0, W), (L, L, 0, W)):
        box(f"edge{z}{x0}{y0}", x0 - t, x1 + t, y0 - t, y1 + t, z - t, z + t, (0.25, 0.25, 0.28))
for x0, x1, y0, y1 in ((0, L, 0, 0), (0, L, W, W), (0, 0, 0, W), (L, L, 0, W)):
    box(f"water{x0}{y0}", x0 - 0.08, x1 + 0.08, y0 - 0.08, y1 + 0.08, WATER - 0.08, WATER + 0.08, (0.25, 0.5, 0.85))
for x in (3.0, L - 3.0):   # the pumps on the back glass, tube 1.2 in, 10.4 in tall, centered 12.3 in up
    box(f"pump{x}", x - 0.6, x + 0.6, W - 2.6, W - 1.4, 12.3 - 5.2, 12.3 + 5.2, (0.12, 0.12, 0.13))

scene.render.engine = "BLENDER_WORKBENCH"
sh = scene.display.shading
sh.light, sh.color_type = "STUDIO", "MATERIAL"
sh.show_shadows, sh.show_cavity = True, True
sh.cavity_type = "WORLD"
scene.display.render_aa = "8"
world = bpy.data.worlds.new("w")
world.color = (0.93, 0.94, 0.96)
scene.world = world
scene.render.resolution_x, scene.render.resolution_y = 1600, 1050
scene.render.image_settings.file_format = "PNG"
aim = Vector((L / 2, W / 2, 9.0))
for name, eye in (("front", Vector((L / 2, -62.0, 14.0))), ("corner_right_front", Vector((L + 30, -48.0, RIM + 22)))):
    bpy.ops.object.camera_add(location=eye, rotation=(aim - eye).to_track_quat("-Z", "Y").to_euler())
    cam = bpy.context.active_object
    cam.data.lens_unit, cam.data.angle = "FOV", math.radians(40)
    cam.data.clip_end = 1000
    scene.camera = cam
    scene.render.filepath = f"{args[1]}/{name}.png"
    bpy.ops.render.render(write_still=True)
