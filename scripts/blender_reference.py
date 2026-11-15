# SPDX-License-Identifier: GPL-3.0-or-later
"""Run inside pinned Blender; generate reference assets and baseline smoke evidence."""
import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile

import bpy
from mathutils import Vector

WORK = Path(__file__).resolve().parents[1] / "work"
NAMES = ("grid", "tabletop", "facade", "measurable-targets")
FEATURE = "tilt_shift_enabled"  # Proposed future RNA identifier; absent in upstream M1.
PIN = "02f0899d78e374b63e7181d9061e1f7ab03419cc"


def material(name, color):
    result = bpy.data.materials.new(name)
    result.diffuse_color = (*color, 1)
    result.use_nodes = True
    result.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*color, 1)
    result.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
    return result


def box(name, center, size, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def make_scene(name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = name
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x, scene.render.resolution_y = 320, 240
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'OPEN_EXR'
    scene.render.image_settings.color_depth = '32'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.exr_codec = 'ZIP'
    scene.cycles.samples = 32
    scene.cycles.seed = 71
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.use_denoising = False
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.world = bpy.data.worlds.new("constant-world")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.15, 0.15, 0.15, 1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.5
    gray = material("neutral", (0.5, 0.5, 0.5))
    dark = material("dark", (0.04, 0.04, 0.04))
    white = material("white", (0.8, 0.8, 0.8))
    red = material("red", (0.6, 0.03, 0.02))
    box("ground", (0, 0, -0.06), (16, 16, 0.1), gray)
    if name == "grid":
        for i in range(-6, 7):
            box(f"grid-x-{i}", (i * 0.5, 0, 0.002), (0.012, 6, 0.008), dark)
            box(f"grid-y-{i}", (0, i * 0.5, 0.003), (6, 0.012, 0.008), dark)
        location, target = (3, -5, 3.5), (0, 0, 0)
    elif name == "tabletop":
        box("table", (0, 0, 0.8), (3, 4, 0.12), white)
        for i in range(7):
            box(f"depth-block-{i}", ((i % 3 - 1)*0.6, -1.5+i*0.5, 1.05),
                (0.25, 0.25, 0.4), red if i % 2 else dark)
        location, target = (3, -5, 3), (0, 0, 0.8)
    elif name == "facade":
        box("facade", (0, 1, 3), (5, 0.2, 6), white)
        for row in range(6):
            for col in range(5):
                box(f"window-{row}-{col}", ((col-2)*0.9, 0.88, 0.5+row*0.9),
                    (0.5, 0.02, 0.5), dark)
        location, target = (4, -10, 1.7), (0, 1, 3)
    else:
        for index, depth in enumerate((0, 1, 2, 3, 4)):
            box(f"target-at-y-{depth}m", ((index-2)*0.6, depth, 0.7), (0.4, 0.04, 1.4), white)
            for stripe in range(9):
                box(f"stripe-{index}-{stripe}", ((index-2)*0.6-0.18+stripe*0.045,
                                                depth-0.025, 0.7), (0.018, 0.01, 1.3), dark)
        location, target = (0, -5, 1.4), (0, 2, 0.7)
    bpy.ops.object.camera_add(location=location)
    camera = bpy.context.object
    camera.name = "reference-camera"
    look_at(camera, target)
    camera.data.lens = 50
    camera.data.sensor_width = 36
    camera.data.sensor_fit = 'HORIZONTAL'
    camera.data.clip_start, camera.data.clip_end = 0.01, 100
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = (Vector(target)-camera.location).length
    camera.data.dof.aperture_fstop = 4
    scene.camera = camera
    bpy.ops.object.light_add(type='AREA', location=(0, -3, 7))
    bpy.context.object.data.energy = 800
    bpy.context.object.data.shape = 'DISK'
    bpy.context.object.data.size = 5
    look_at(bpy.context.object, (0, 0, 0))
    scene["reference_purpose"] = "Baseline fixture; native optical acceptance requires M2/M3"
    return scene


def feature(camera, required):
    present = FEATURE in camera.bl_rna.properties
    if required and not present:
        raise RuntimeError(f"Native RNA {FEATURE!r} absent; M1 contains standalone optics only")
    if present:
        setattr(camera, FEATURE, required)
    return present


def backend(scene, name):
    import _cycles
    if not _cycles.set_device_override(name.upper()):
        raise RuntimeError("Cycles rejected hard device override")
    if name == 'cpu':
        scene.cycles.device = 'CPU'
        return ['CPU']
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'HIP'
    available = prefs.get_devices_for_type('HIP')
    supported_ids = {device.id for device in available
                     if device.type == 'HIP' and device.meets_driver_requirement}
    selected = []
    for device in prefs.devices:
        device.use = device.type == 'HIP' and device.id in supported_ids
        if device.use:
            selected.append(device.name)
    if not selected:
        raise RuntimeError("No HIP device found; refusing CPU fallback")
    scene.cycles.device = 'GPU'
    return selected


def render(args):
    scene = make_scene(args.scene)
    present = feature(scene.camera.data, args.require_feature)
    devices = backend(scene, args.backend)
    folder = WORK / 'renders' / args.label / args.backend
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / f'{args.scene}.exr'
    with tempfile.NamedTemporaryFile(prefix=args.scene+'-', suffix='.exr', dir=folder,
                                     delete=False) as stream:
        temporary = Path(stream.name)
    scene.render.filepath = str(temporary)
    if bpy.ops.render.render(write_still=True) != {'FINISHED'}:
        raise RuntimeError("Render did not finish; refusing prior output as evidence")
    image = bpy.data.images.load(str(temporary), check_existing=False)
    width, height = image.size
    values = array.array('f', image.pixels[:])
    if (width, height) != (320, 240) or len(values) != width*height*4:
        raise RuntimeError("Unexpected rendered pixel dimensions")
    if not all(math.isfinite(x) for x in values):
        raise RuntimeError("Nonfinite rendered pixels")
    rgb = [value for i, value in enumerate(values) if i % 4 != 3]
    if max(rgb) <= 0 or max(rgb)-min(rgb) < 1e-6:
        raise RuntimeError("Pathological empty or constant image; smoke render rejected")
    pixel_file = output.with_suffix('.rgba32f')
    temporary_pixels = temporary.with_suffix('.rgba32f')
    with temporary_pixels.open('wb') as stream:
        values.tofile(stream)
    metadata = dict(scene=args.scene, width=width, height=height, seed=71, samples=32,
                    backend=args.backend, devices=devices, blender_version=bpy.app.version_string,
                    blender_build_hash=bpy.app.build_hash.decode(), feature_present=present,
                    feature_enabled=bool(getattr(scene.camera.data, FEATURE)) if present else False,
                    pixels=pixel_file.name,
                    pixels_sha256=hashlib.sha256(temporary_pixels.read_bytes()).hexdigest(),
                    byteorder=sys.byteorder, mean_rgb=sum(rgb)/len(rgb), max_rgb=max(rgb),
                    generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    camera_settings=dict(lens=scene.camera.data.lens,
                                         sensor_width=scene.camera.data.sensor_width,
                                         focus_distance=scene.camera.data.dof.focus_distance,
                                         aperture_fstop=scene.camera.data.dof.aperture_fstop,
                                         matrix=[list(row) for row in scene.camera.matrix_world]),
                    evidence='render smoke only; no native physical validation')
    temporary_metadata = temporary.with_suffix('.json')
    temporary_metadata.write_text(json.dumps(metadata, indent=2) + '\n')
    temporary.replace(output)
    temporary_pixels.replace(pixel_file)
    temporary_metadata.replace(output.with_suffix('.json'))
    print(json.dumps(metadata, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('validate', 'scenes', 'render'))
    parser.add_argument('--require-feature', action='store_true')
    parser.add_argument('--backend', choices=('cpu', 'hip'), default='cpu')
    parser.add_argument('--scene', choices=NAMES, default='measurable-targets')
    parser.add_argument('--label', default='baseline')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if not args.label.replace('-', '').replace('_', '').isalnum():
        raise RuntimeError("Label must contain letters, numbers, hyphens or underscores")
    if bpy.app.version[:2] != (5, 3):
        raise RuntimeError(f"Expected Blender 5.3; found {bpy.app.version_string}")
    build_hash = bpy.app.build_hash.decode()
    if len(build_hash) < 12 or not PIN.startswith(build_hash):
        raise RuntimeError(f"Expected pinned Blender build {PIN}; found {build_hash}")
    if args.command == 'render':
        render(args)
        return
    folder = WORK / 'scenes'
    folder.mkdir(parents=True, exist_ok=True)
    for name in NAMES if args.command == 'scenes' else ('measurable-targets',):
        scene = make_scene(name)
        present = feature(scene.camera.data, args.require_feature)
        path = folder / f'{name}.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        bpy.ops.wm.open_mainfile(filepath=str(path))
        assert bpy.context.scene.camera.data.lens == 50
        assert bpy.context.scene.render.resolution_x == 320
        if present and bool(getattr(bpy.context.scene.camera.data, FEATURE)) != args.require_feature:
            raise RuntimeError("Native enabled state did not survive save/reopen")
        print(json.dumps(dict(scene=name, saved=str(path), feature_present=present,
                              evidence='baseline RNA/save/reopen smoke only')))


if __name__ == '__main__':
    main()
