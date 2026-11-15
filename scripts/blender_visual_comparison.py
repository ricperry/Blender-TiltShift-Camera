# SPDX-License-Identifier: GPL-3.0-or-later
"""Large, same-scene native Cycles DOF comparison (not an image-space effect).

Run the preserved M3 binary, with host resource limits, e.g.:
  work/install-blender-m3/blender --background -noaudio --factory-startup \
    --python-exit-code 1 --python scripts/blender_visual_comparison.py -- \
    --output work/visual-comparison --case all

Every case keeps the scene, seed, rigid camera transform, lens, f-stop and manual
focus distance fixed. Only physical-camera enable and lens tilt differ. Geometry
is camera-local metres, X right, Y up, -Z scene-going. The receding tabletop is
Z_world = -(d + slope*Y), slope = -d*sin(tilt)/f. This is the independent exact
manual-focus sharp-plane law, not a fitted image-space blur. Camera scale is one.
Rotation order is native fixed Rz(axis) Ry(swing) Rx(tilt); swing/axis stay zero.
Image circle zero is unbounded. The fixture is far from all optical singularities.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
PIN = '02f0899d78e374b63e7181d9061e1f7ab03419cc'
FOCAL_M = .050
FOCUS_M = .650
TILT = math.radians(-8)
SLOPE = -FOCUS_M * math.sin(TILT) / FOCAL_M
CASES = {'ordinary': (False, 0.0), 'physical-zero': (True, 0.0),
         'physical-tilted': (True, TILT)}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def material(name, color):
    result = bpy.data.materials.new(name)
    nodes = result.node_tree.nodes
    nodes.clear()
    emit = nodes.new('ShaderNodeEmission')
    emit.inputs['Color'].default_value = (*color, 1)
    emit.inputs['Strength'].default_value = 1
    out = nodes.new('ShaderNodeOutputMaterial')
    result.node_tree.links.new(emit.outputs[0], out.inputs['Surface'])
    return result


def point(u, v, lift=0):
    # Lift is camera-local Z: disjoint printed layers differ by <=30 micrometres.
    return (u, v, -(FOCUS_M + SLOPE*v) + lift)


def rectangles(name, rects, mat, lift=0):
    vertices, faces = [], []
    for x, y, w, h in rects:
        start = len(vertices)
        vertices.extend(point(u, v, lift) for u, v in
                        [(x, y), (x+w, y), (x+w, y+h), (x, y+h)])
        faces.append(tuple(range(start, start+4)))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    mesh.materials.append(mat)
    return obj


def label(name, value, x, y, size, mat):
    text = bpy.data.curves.new(name, 'FONT')
    text.body = value
    text.size = size
    text.align_x = 'CENTER'
    text.align_y = 'CENTER'
    text.resolution_u = 4
    obj = bpy.data.objects.new(name, text)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = point(x, y, .00003)
    obj.rotation_euler.x = -math.atan(SLOPE)
    text.materials.append(mat)
    return obj


def setup(samples, width, height):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    import _cycles
    if not _cycles.set_device_override('CPU'):
        raise RuntimeError('CPU override rejected')
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 2
    scene.cycles.samples = samples
    scene.cycles.seed = 203
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.use_denoising = False
    scene.cycles.max_bounces = 1
    scene.cycles.pixel_filter_type = 'BOX'
    scene.cycles.filter_width = 1.0
    scene.render.use_compositing = False
    scene.render.use_sequencer = False
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.world = bpy.data.worlds.new('Dark surroundings')
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .02
    bpy.ops.object.camera_add(location=(0, 0, 0), rotation=(0, 0, 0))
    camera = bpy.context.object
    camera.name = 'Same fixed camera - only native enable and tilt change'
    scene.camera = camera
    data = camera.data
    if 'tilt_shift_enabled' not in data.bl_rna.properties:
        raise RuntimeError('This fixture needs the native M3 binary')
    data.lens = FOCAL_M*1000
    data.sensor_width = 36
    data.sensor_fit = 'HORIZONTAL'
    data.clip_start, data.clip_end = .03, 10
    data.shift_x = data.shift_y = 0
    data.dof.use_dof = True
    data.dof.focus_distance = FOCUS_M
    data.dof.aperture_fstop = 1.4
    data.dof.aperture_blades = 0
    data.dof.aperture_ratio = 1
    data.tilt_shift_swing = data.tilt_shift_axis_rotation = 0
    data.tilt_shift_image_circle_diameter = 0
    white = material('Warm white paper', (.90, .88, .82))
    black = material('Charcoal ink', (.006, .009, .014))
    red = material('Vermilion depth markers', (.75, .055, .024))
    blue = material('Blue table', (.025, .12, .18))
    gray = material('Muted calibration lines', (.3, .34, .36))
    rectangles('Physical tabletop', [(-.8, -.2, 1.6, .8)], blue)
    rectangles('One receding printed chart', [(-.65, -.15, 1.3, .65)], white, .00001)
    # Whole-table millimetre grid gives context between the target cards.
    grid = [(-.65+i*.01, -.15, .00015, .65) for i in range(131)]
    grid += [(-.65, -.15+i*.01, 1.3, .00015) for i in range(66)]
    rectangles('10 mm grid and fine rules', grid, gray, .000015)
    rows = []
    b0 = FOCAL_M*FOCUS_M/(FOCUS_M-FOCAL_M)
    half_sensor_height = .036*height/width/2
    for row, screen_y in enumerate((-.78, -.39, 0, .39, .78)):
        ray_y = screen_y*half_sensor_height/b0
        v = FOCUS_M*ray_y/(1-SLOPE*ray_y)
        depth = FOCUS_M+SLOPE*v
        # Geometry sizes grow with depth for similar on-screen readability.
        scale = depth/FOCUS_M
        card_w = .115*scale
        card_h = .018*scale*scale
        for col in (-1, 0, 1):
            x = col*.17*scale
            name = f'row-{row+1}-column-{col+2}'
            rectangles(name+' paper', [(x-card_w/2, v-card_h, card_w,
                                        card_h*2)], white, .00002)
            # 10 x 6 checkerboard; tile edges stay genuinely sharp on-plane.
            start_x = x-card_w*.43
            start_v = v-card_h*.67
            tile_x = card_w*.045
            tile_v = card_h*.22
            squares = [(start_x+i*tile_x, start_v+j*tile_v, tile_x, tile_v)
                       for i in range(10) for j in range(6) if (i+j)%2 == 0]
            # Adjacent graded line-pair target: coarse to fine, all actual mesh.
            for group, fraction in enumerate((.018, .010, .006)):
                gx = x+card_w*(.08+group*.115)
                bar_w = card_w*fraction
                for bar in range(4):
                    squares.append((gx+2*bar*bar_w, start_v, bar_w,
                                    tile_v*6))
            rectangles(name+' checker and line pairs', squares, black, .000025)
            label(name+' readable depth', f'{depth:.2f} m  /  {row+1}', x,
                  v+card_h*.78, .007*scale, black)
            rectangles(name+' depth accent', [(x-card_w*.49, v-card_h*.88,
                        card_w*.98, card_h*.07)], red, .000025)
        rows.append({'row': row+1, 'camera_local_y_m': v,
                     'camera_axis_depth_m': depth})
    return scene, camera, rows


def rna(camera):
    data = camera.data
    return {'tilt_shift_enabled': data.tilt_shift_enabled,
            'tilt_shift_tilt_rad': data.tilt_shift_tilt,
            'tilt_shift_swing_rad': data.tilt_shift_swing,
            'tilt_shift_axis_rotation_rad': data.tilt_shift_axis_rotation,
            'tilt_shift_image_circle_diameter_mm': data.tilt_shift_image_circle_diameter,
            'lens_mm': data.lens, 'sensor_width_mm': data.sensor_width,
            'sensor_fit': data.sensor_fit, 'shift_x': data.shift_x,
            'shift_y': data.shift_y, 'dof_use_dof': data.dof.use_dof,
            'dof_focus_distance_m': data.dof.focus_distance,
            'dof_aperture_fstop': data.dof.aperture_fstop,
            'camera_matrix_world': [list(row) for row in camera.matrix_world]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'work/visual-comparison')
    parser.add_argument('--case', choices=['all', *CASES], default='all')
    parser.add_argument('--samples', type=int, default=128)
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--height', type=int, default=800)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    folder = args.output.resolve()
    if not folder.is_relative_to((ROOT/'work').resolve()):
        raise ValueError('Generated artifacts must stay in the ignored project work/ directory')
    folder.mkdir(parents=True, exist_ok=True)
    scene, camera, rows = setup(args.samples, args.width, args.height)
    manifest = {'fixture': 'same-scene native Cycles tabletop focus comparison',
                'upstream_pin': PIN, 'binary': bpy.app.binary_path,
                'binary_sha256': sha256(bpy.app.binary_path),
                'blender_version': bpy.app.version_string,
                'script_sha256': sha256(__file__),
                'render': {'engine': 'CYCLES', 'device': 'CPU', 'threads': 2,
                           'samples': args.samples, 'seed': scene.cycles.seed,
                           'resolution': [args.width, args.height],
                           'denoising': False, 'adaptive_sampling': False,
                           'compositing': False, 'view_transform': 'Standard'},
                'tabletop': {'plane': 'camera Z = -(0.65 + slope * camera Y)',
                             'slope': SLOPE, 'matched_tilt_deg': math.degrees(TILT),
                             'printed_layer_max_camera_z_offset_m': .00003,
                             'depth_rows': rows}, 'cases': []}
    patch = ROOT/'patches/blender-v5.3.0-tilt-shift-m3.patch'
    manifest['native_patch_sha256'] = sha256(patch)
    for name in (CASES if args.case == 'all' else [args.case]):
        enabled, tilt = CASES[name]
        camera.data.tilt_shift_enabled = enabled
        camera.data.tilt_shift_tilt = tilt
        scene.render.filepath = str(folder/(name+'.png'))
        blend = folder/(name+'.blend')
        bpy.ops.wm.save_as_mainfile(filepath=str(blend), check_existing=False)
        if bpy.ops.render.render(write_still=True) != {'FINISHED'}:
            raise RuntimeError('Rendering failed: '+name)
        record = {'name': name, 'rna': rna(camera), 'image': name+'.png',
                  'image_sha256': sha256(scene.render.filepath),
                  'blend': blend.name, 'blend_sha256': sha256(blend)}
        manifest['cases'].append(record)
        # A completed per-case ledger survives interruption of later renders.
        (folder/(name+'-manifest.json')).write_text(json.dumps(
            dict(manifest, cases=[record]), indent=2)+'\n')
        (folder/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('VISUAL_COMPARISON_COMPLETE', json.dumps(manifest['cases']))


if __name__ == '__main__':
    main()
