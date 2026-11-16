# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a metre-scale city district with three matched finite-aperture cameras.

Uses create_city's primitive geometry and deterministic traffic, with a real 50x
world-space enlargement. Generation saves only; see FULL_SCALE_CITY.md to render.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import create_city as city

SCALE = 50.0
ROOT = Path(__file__).resolve().parents[1]

NOTES = '''FULL-SCALE MERIDIAN — lens tilt versus standard perspective DOF
SPDX-License-Identifier: GPL-3.0-or-later

Open in the project's patched Blender 5.3. F12 renders the selected camera.
Choose Scene Properties > Camera, or select a camera and Ctrl Numpad 0:
01 ORDINARY: upstream perspective camera, tilt-shift movement disabled, DOF ON.
02 NATIVE ZERO: tilt-shift enabled, zero movements, DOF ON; a baseline comparison.
03 NATIVE TILT: tilt-shift enabled, +5 degrees tilt, DOF ON; active on opening.
All three share the same position, orientation, 50 mm lens, 36 mm sensor,
f/2.8 aperture and off-axis focus object. Image circle 0 is unbounded.
Ordinary DOF stays enabled on every camera: this compares optical lens tilt,
not DOF on/off. Physical breathing is accepted; frames may differ slightly.
At actual city distances, ordinary 50 mm DOF is broad. Tilt changes the focus
plane and can move much of this district away from focus at the same f-stop.
Change tilt in small increments (0.25 degrees) or move FOCUS to experiment.
All blur comes from Cycles finite-aperture rays; no compositor is used.

SCALE: 1 Blender unit = 1 metre, right-handed Z-up; streets along X/Y.
The original 1.64 x 1.34 m district is physically enlarged to 82 x 67 m.
Cars are about 3.3 m long, standing people 2 m tall, buildings about 5–22 m.
The WORLD SCALE empty scales geometry and animated translation by 50, not
units metadata. Camera scale is 1; camera/focus positions are metres.
Terrain and through streets continue into surrounding simple building blocks.
No display plinth, nameplate or studio tabletop remains.

Camera -Z points forward, +Y up. Tilt-shift angles store radians, shown as degrees;
active lens-frame rotation order is Rz(axis) Ry(swing) Rx(tilt). Extreme poses
may approach singular focus geometry and are rejected by the tilt-shift camera.
Original paint/surface separations become 15–50 mm; physics tolerances unchanged.

CPU, two threads, 1600 x 1000, 128 samples, seed 71, frame 40. Motion blur and
Vector passes remain disabled. HIP needs separate hardware/build verification.
Space plays deterministic 1–240 keyframes at 24 fps, with a positional wrap.
Signals green 1–84 / 201–240, amber 85–92, red 93–200. Cars hold 85–200;
crossing pedestrians walk 105–184. Animation is inherited without handlers.
No textures, linked libraries, drivers, add-ons or execute-on-load scripts.
'''


def extend_district():
    """Reuse the original coordinate grid, before enlarging its actual geometry."""
    for obj in tuple(bpy.context.scene.objects):
        if (obj.type == 'CAMERA' or obj.name.startswith('FOCUS ·') or
                obj.name in {'Little Meridian / floating maple plinth',
                             'Little Meridian / stone edge', 'Studio surface',
                             'Plinth / name'}):
            old_camera = obj.data if obj.type == 'CAMERA' else None
            bpy.data.objects.remove(obj, do_unlink=True)
            if old_camera is not None and old_camera.users == 0:
                bpy.data.cameras.remove(old_camera)
    city.COLLECTIONS['01 · Tabletop and waterfront'].name = '01 · Continuous terrain and waterfront'
    city.COLLECTIONS['10 · Lighting / golden hour studio'].name = '10 · Outdoor sky and soft daylight'
    city.collection('11 · Surrounding city blocks')
    city.box('Continuous city terrain', (0, .1, -.001), (6, 5, .024), city.MATERIALS['paving'])
    # Continue existing road surfaces rather than overlaying coplanar duplicates.
    for obj in bpy.context.scene.objects:
        if obj.name.startswith('North–south avenue'):
            obj.location.y, obj.scale.y = .1, 5
        elif obj.name.startswith('East–west avenue'):
            obj.scale.x = 6
        elif obj.name == 'Canal / quiet turquoise water':
            obj.scale.x = 6
        elif obj.name.startswith('Canal / limestone quay'):
            obj.scale.x = 6
    for y in (.82, 1.40, -.94):
        city.box('District connector road', (0, y, .0121), (6, .104, .008), city.MATERIALS['asphalt'])
    for x in (-1.1, 1.05):
        city.box('Outer avenue', (x, .1, .012), (.104, 5, .008), city.MATERIALS['asphalt'])
    # Modest repetitive architecture provides city context without added assets.
    index = 0
    for y in (.99, 1.64):
        for x in (-1.55, -1.32, -.78, -.53, -.02, .23, .75, 1.33, 1.57):
            index += 1
            height = (.16, .22, .28, .19)[index % 4]
            city.building(f'Surrounding block {index:02}', x, y, .18, .23,
                          height, ('cream', 'ochre', 'teal')[index % 3],
                          max(2, round(height/.05)), roof='service')
    for x in (-1.48, -1.24, 1.29, 1.53):
        index += 1
        city.building(f'Surrounding block {index:02}', x, .13, .19, .28,
                      .15, 'cream', 3, roof='service')
    for x in (-1.45, -.70, .02, .72, 1.45):
        city.tree(x, 1.24, 1.1, 'Outer street tree')


def enlarge_world():
    scene = bpy.context.scene
    city.collection('12 · Physical scale / geometry and animation')
    root = city.empty('WORLD SCALE · geometry and animated travel ×50')
    for obj in tuple(scene.objects):
        if obj == root:
            continue
        if obj.type == 'LIGHT':
            obj.location *= SCALE
            obj.data.size *= SCALE
            obj.data.energy *= SCALE*SCALE
            obj.name = obj.name.replace('Sunset / large warm window', 'Daylight / broad warm sky')
            obj.name = obj.name.replace('Camera / soft bounce', 'Sky / warm reflected light')
        elif obj.parent is None:
            # Child translations and mesh extents inherit this scale, including
            # existing animated local translations; focal length never scales.
            obj.parent = root
    root.scale = (SCALE,)*3
    return root


def matched_cameras(tilt_degrees):
    city.collection('09 · Cameras / matched full-scale comparison')
    scene = bpy.context.scene
    focus = city.empty('FOCUS · full-scale central crossing', Vector((.015, -.12, .035))*SCALE)
    focus.hide_render = True
    pose, target = Vector((2.05, -2.64, 3))*SCALE, Vector((0, .025, -.12))*SCALE
    cameras = []
    for name, enabled, tilt in (
            ('01 · ORDINARY / DOF ON / native disabled', False, 0),
            ('02 · NATIVE ZERO / DOF ON / zero movements', True, 0),
            ('03 · NATIVE TILT / DOF ON', True, tilt_degrees)):
        data = bpy.data.cameras.new(name)
        obj = bpy.data.objects.new(name, data)
        city.ACTIVE_COLLECTION.objects.link(obj)
        obj.location = pose
        city.look_at(obj, target)
        data.type, data.lens, data.sensor_width, data.sensor_fit = 'PERSP', 50, 36, 'HORIZONTAL'
        data.clip_start, data.clip_end = .1, 2000
        data.dof.use_dof, data.dof.aperture_fstop = True, 2.8
        data.dof.focus_object = focus
        data.dof.focus_distance = (focus.location-pose).length
        data.dof.aperture_blades = 7
        data.tilt_shift_enabled = enabled
        data.tilt_shift_tilt = math.radians(tilt)
        data.tilt_shift_swing = data.tilt_shift_axis_rotation = 0
        data.tilt_shift_image_circle_diameter = 0
        obj['usage'] = 'Matched pose, lens, f/2.8 and focus; ordinary DOF ON. Physical breathing accepted.'
        cameras.append(obj)
    scene.camera = cameras[-1]
    bpy.ops.object.select_all(action='DESELECT')
    scene.camera.select_set(True)
    bpy.context.view_layer.objects.active = scene.camera
    return cameras, focus


def world_bounds(objects):
    corners = [obj.matrix_world @ Vector(corner) for obj in objects if obj.type == 'MESH'
               for corner in obj.bound_box]
    low = [min(point[i] for point in corners) for i in range(3)]
    high = [max(point[i] for point in corners) for i in range(3)]
    return {'min_m': low, 'max_m': high, 'dimensions_m': [high[i]-low[i] for i in range(3)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=ROOT/'work/examples/full-scale-city/full-scale-city.blend')
    parser.add_argument('--tilt-degrees', type=float, default=5,
                        help='Native comparison tilt (default 5 degrees).')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    output = args.output.resolve()
    if not output.is_relative_to((ROOT/'work').resolve()) or output.suffix != '.blend':
        raise ValueError('Save the generated .blend below this project\'s ignored work/')
    output.parent.mkdir(parents=True, exist_ok=True)
    # The reusable source generator saves its intermediate in this example's
    # ignored directory, never replacing the original miniature or user scenes.
    original_argv = sys.argv
    sys.argv = [str(Path(city.__file__)), '--', '--output', str(output.parent/'source-miniature.blend')]
    try:
        city.main()
    finally:
        sys.argv = original_argv
    extend_district()
    enlarge_world()
    cameras, focus = matched_cameras(args.tilt_degrees)
    scene = bpy.context.scene
    scene.name = 'FULL-SCALE MERIDIAN · native versus ordinary DOF'
    scene.use_nodes = False
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.render.filepath = str(output.parent/'full-scale-native-tilt.png')
    scene.frame_set(40)
    bpy.context.view_layer.update()
    for text in tuple(bpy.data.texts):
        if text.name.startswith('START HERE'):
            bpy.data.texts.remove(text)
    bpy.data.texts.new('START HERE · Full-scale Meridian').write(
        NOTES.replace('+5 degrees', f'{args.tilt_degrees:+g} degrees'))
    scene['README'] = 'Text Editor > START HERE · Full-scale Meridian. Three matched cameras; DOF ON throughout.'
    scene['generator'] = 'examples/create_full_scale_city.py; reuses create_city.py; physical geometry scale 50'
    scene['scale_note'] = '1 BU = 1 m; core district 82 × 67 m; geometry and animation enlarged 50×'
    summary = {
        'blend': str(output), 'objects': len(scene.objects), 'frame': scene.frame_current,
        'frames': [1, 240], 'fps': 24, 'units': 'metres; 1 Blender unit = 1 metre',
        'geometry_scale': SCALE, 'core_district_dimensions_m': [82, 67],
        'terrain_dimensions_m': [300, 250], 'focus_position_m': list(focus.location),
        'representative_geometry': {
            'car_body': world_bounds([bpy.data.objects['Eastbound 1.1.1 / body']]),
            'standing_person': world_bounds(bpy.data.objects['Citizen 01'].children_recursive),
            'hotel_body': world_bounds([bpy.data.objects['Meridian Hotel']]),
            'hotel_cap': world_bounds([bpy.data.objects['Hotel / cream cap']]),
        },
        'render': {'engine': 'CYCLES', 'saved_device': 'CPU', 'threads': 2,
                   'resolution': [1600, 1000], 'samples': 128, 'seed': 71,
                   'motion_blur': False, 'compositor': False},
        'active_camera': scene.camera.name,
        'cameras': [{
            'name': obj.name, 'position_m': list(obj.location), 'scale': list(obj.scale),
            'rotation_euler_xyz_radians': list(obj.rotation_euler),
            'native': obj.data.tilt_shift_enabled, 'dof_enabled': obj.data.dof.use_dof,
            'lens_mm': obj.data.lens, 'sensor_width_mm': obj.data.sensor_width,
            'fstop': obj.data.dof.aperture_fstop, 'focus_object': focus.name,
            'focus_distance_m': obj.data.dof.focus_distance,
            'tilt_degrees': math.degrees(obj.data.tilt_shift_tilt),
            'swing_degrees': math.degrees(obj.data.tilt_shift_swing),
            'axis_degrees': math.degrees(obj.data.tilt_shift_axis_rotation),
            'shift': [obj.data.shift_x, obj.data.shift_y],
            'image_circle_diameter_mm': obj.data.tilt_shift_image_circle_diameter,
        } for obj in cameras],
        'animation_targets': [obj.name for obj in scene.objects if obj.animation_data],
        'external_images': [image.filepath for image in bpy.data.images if image.source == 'FILE'],
        'comparison': 'Ordinary DOF ON throughout; physical breathing accepted; no postprocess blur',
    }
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)
    output.with_suffix('.json').write_text(json.dumps(summary, indent=2)+'\n')
    print('FULL_SCALE_CITY_SAVED', json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
