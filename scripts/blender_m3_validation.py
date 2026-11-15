# SPDX-License-Identifier: GPL-3.0-or-later
"""M3 native interface/guide/animation fixtures; launch in isolated Blender.

Guide checks inspect the BKE vertices also consumed by the real overlay. Original
M1/M2 fixtures and mathematical headers remain immutable. Generated files belong
in work/. No file is opened except explicit migration inputs or this fixture's own
newly saved round-trip artifact.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import blender_m2_validation as m2

checks = 0
maximum_error = 0.0


def close(actual, expected, tolerance=2e-6, label='numeric'):
    global checks, maximum_error
    checks += 1
    error = abs(actual - expected)
    maximum_error = max(maximum_error, error)
    if not math.isfinite(actual) or error > tolerance:
        raise AssertionError(f'{label}: {actual} expected {expected}, tolerance {tolerance}')


def require(value, label):
    global checks
    checks += 1
    if not value:
        raise AssertionError(label)


def normal(data):
    t, s, a = data.tilt_shift_tilt, data.tilt_shift_swing, data.tilt_shift_axis_rotation
    return Vector((math.cos(a)*math.sin(s)*math.cos(t)+math.sin(a)*math.sin(t),
                   -math.sin(a)*math.sin(s)*math.cos(t)+math.cos(a)*math.sin(t),
                   math.cos(s)*math.cos(t)))


def cycles(v):
    return Vector((v[0], v[1], -v[2]))


def chunks(values):
    return [Vector(values[i:i+3]) for i in range(0, len(values), 3)]


def sensor(data):
    return (data.sensor_height if data.sensor_fit == 'VERTICAL' else data.sensor_width)*.001


def center(data, roll=0, flip=False):
    x, y = sensor(data)*data.shift_x, sensor(data)*data.shift_y
    x, y = math.cos(roll)*x-math.sin(roll)*y, math.sin(roll)*x+math.cos(roll)*y
    return Vector((-x if flip else x, y, 0))


def guide(camera, evaluated=True, roll=0, flip=False):
    bpy.context.view_layer.update()
    obj = camera.evaluated_get(bpy.context.evaluated_depsgraph_get()) if evaluated else camera
    data = obj.data
    result = data.tilt_shift_guide_geometry(obj, view_roll=roll, view_flip_x=flip)
    require(len(result) == 9, 'native geometry API output shape')
    result = (*result[:6], tuple(value for xyz in zip(*result[6:]) for value in xyz))
    return obj, result


def check_geometry(camera, target=None, roll=0, flip=False):
    obj, (valid, focus_valid, circle_valid, b, lens, focus, circle) = guide(camera, roll=roll, flip=flip)
    data = obj.data
    require(valid and focus_valid and circle_valid, 'finite optical guide validity')
    n, c, f = normal(data), center(data, roll, flip), data.lens*.001
    if target is None:
        q = Vector((0, 0, data.dof.focus_distance))
    else:
        world = target(obj)
        camera_matrix = obj.matrix_world.copy()
        for i in range(3):
            camera_matrix.col[i].xyz = camera_matrix.col[i].xyz.normalized()
        q = cycles(camera_matrix.inverted() @ world) - c
    expected_b = f*q.z/(n.dot(q)-f)
    close(b, expected_b, 2e-7, 'native sensor distance')
    m = n-Vector((0, 0, f/b))
    for p in chunks(lens):
        close(n.dot(cycles(p)-c), 0, 3e-7, 'lens vertex in actual lens plane')
    for p in chunks(focus):
        close(m.dot(cycles(p)-c), f, 3e-6, 'focus vertex in sharp plane')
    for p in chunks(circle):
        v = cycles(p)-c
        close(v.z, data.display_size, 3e-7, 'circle at forward display distance')
        rear = v*(-f/n.dot(v))
        close((rear+f*n).length, data.tilt_shift_image_circle_diameter*.0005,
              3e-7, 'exact rear-focal angular coverage')
    # Native focus corners are actual common intersections of sampled-aperture rays.
    for point in chunks(focus):
        q = cycles(point)-c
        p = -q*(b/q.z)
        for aperture in (Vector((.002, -.001, 0)), Vector((-.003, .001, 0))):
            # Project arbitrary aperture offsets into the actual tilted plane.
            a = aperture - n*aperture.dot(n)
            h = 1+n.dot(p)/f
            d = h*a-p
            k = (q.z-a.z)/d.z
            error = (a+k*d-q).length
            close(error, 0, 3e-5, 'native sharp guide converges sampled aperture rays')
    return dict(sensor_distance=b, lens=list(lens), focus=list(focus), circle=list(circle))


def rig(camera):
    bpy.ops.object.armature_add(location=(.03, -.01, -.5))
    obj = bpy.context.object
    obj.name = 'animated-focus-rig'
    obj.data.bones[0].name = 'Focus'
    camera.data.dof.focus_object = obj
    camera.data.dof.focus_subtarget = 'Focus'
    return obj


def geometry_case():
    scene, camera, _ = m2.setup(4)
    data = camera.data
    for field in ('focus_plane', 'lens_plane', 'image_circle'):
        require(not getattr(data, 'tilt_shift_show_'+field), 'display toggle defaults false')
    for axis in ('x', 'y'):
        prop = data.bl_rna.properties['tilt_shift_shift_'+axis+'_mm']
        require(not prop.is_animatable, 'mm alias cannot create competing FCurve')
        require(prop.subtype == 'DISTANCE_CAMERA', 'mm alias uses explicit camera millimetres')
        try:
            data.keyframe_insert('tilt_shift_shift_'+axis+'_mm')
        except TypeError:
            pass
        else:
            raise AssertionError('mm alias unexpectedly accepted keyframe')
    require(data.bl_rna.properties['tilt_shift_image_circle_diameter'].subtype == 'DISTANCE_CAMERA',
            'image-circle field uses explicit camera millimetres')
    data.tilt_shift_tilt = .12
    data.tilt_shift_swing = -.08
    data.tilt_shift_axis_rotation = .37
    data.tilt_shift_image_circle_diameter = 44
    for fit in ('AUTO', 'HORIZONTAL', 'VERTICAL'):
        data.sensor_fit = fit
        for dimensions, pixel_aspect in (((320, 192), (1, 1)), ((192, 320), (1.7, .8))):
            scene.render.resolution_x, scene.render.resolution_y = dimensions
            scene.render.pixel_aspect_x, scene.render.pixel_aspect_y = pixel_aspect
            data.tilt_shift_shift_x_mm = 2.4
            data.tilt_shift_shift_y_mm = -1.2
            close(data.shift_x*sensor(data)*1000, 2.4, 1e-6, 'mm setter canonical x')
            close(data.shift_y*sensor(data)*1000, -1.2, 1e-6, 'mm setter canonical y')
            data.shift_x = .11
            close(data.tilt_shift_shift_x_mm, .11*sensor(data)*1000, 1e-6, 'canonical setter mm getter')
            check_geometry(camera)
    for system, display_scale in (('METRIC', .01), ('IMPERIAL', 100), ('NONE', 1)):
        scene.unit_settings.system = system
        scene.unit_settings.scale_length = display_scale
        close(data.tilt_shift_shift_x_mm, data.shift_x*sensor(data)*1000,
              1e-6, 'scene display units do not alter physical shift')
        check_geometry(camera)
    # Parameterized roll/flip matches actual shared BKE offset transform; this is
    # geometry evidence, not acceptance of final rolled rendered-viewport framing.
    check_geometry(camera, roll=.45, flip=True)
    camera.scale = (2, 3, 4)
    camera.location = (.2, -.3, .1)
    camera.rotation_euler = (.1, -.2, .3)
    bpy.ops.object.empty_add(location=camera.matrix_world @ Vector((.02, -.03, -.6)))
    target = bpy.context.object
    data.dof.focus_object = target
    check_geometry(camera, lambda obj: obj.data.dof.focus_object.matrix_world.translation)
    data.dof.focus_object = None
    camera.location = (0, 0, 0)
    camera.rotation_euler = (0, 0, 0)
    camera.scale = (1, 1, 1)
    target = rig(camera)
    check_geometry(camera, lambda obj: obj.data.dof.focus_object.matrix_world @
                   obj.data.dof.focus_object.pose.bones['Focus'].matrix.translation)
    data.dof.focus_object = None
    data.tilt_shift_tilt, data.tilt_shift_swing, data.tilt_shift_axis_rotation = .2, 0, 0
    bpy.ops.object.empty_add()
    vertical_target = bpy.context.object
    data.dof.focus_object = vertical_target
    vertical_target.location = (.01, center(data).y + .05/math.sin(data.tilt_shift_tilt), -2)
    check_geometry(camera, lambda obj: obj.data.dof.focus_object.matrix_world.translation)
    require(guide(camera)[1][1], 'vertical sharp plane retained at zero axial component')
    vertical_target.location.y += .08
    check_geometry(camera, lambda obj: obj.data.dof.focus_object.matrix_world.translation)
    obj, state = guide(camera)
    require(normal(obj.data).z-.05/state[3] < 0, 'negative axis-intercept focus plane retained')
    vertical_target.location.z = .5
    require(not guide(camera)[1][0], 'behind-camera focus target rejected')
    vertical_target.location.z = -2
    bpy.context.view_layer.update()
    # Shared datablocks must accept either owning camera; reject unrelated data.
    other = bpy.data.objects.new('shared-camera', data)
    scene.collection.objects.link(other)
    require(data.tilt_shift_guide_geometry(other)[0], 'shared camera ownership')
    foreign = bpy.data.cameras.new('foreign-data')
    require(not foreign.tilt_shift_guide_geometry(camera)[0], 'foreign camera ownership rejected')
    data.dof.focus_object = None
    data.tilt_shift_tilt = data.tilt_shift_swing = data.tilt_shift_axis_rotation = 0
    data.dof.focus_distance = 1e12
    require(not guide(camera)[1][1], 'near-infinite focus plane suppressed')
    data.dof.focus_distance = 0
    require(not guide(camera)[1][0], 'zero manual focus rejected')
    data.dof.focus_distance = .5
    data.tilt_shift_image_circle_diameter = 0
    require(not guide(camera)[1][2], 'unbounded image circle absent')
    data.tilt_shift_tilt = math.radians(80)
    data.tilt_shift_image_circle_diameter = 100
    require(not guide(camera)[1][2], 'coverage asymptote suppressed')
    data.tilt_shift_tilt = math.pi
    require(not guide(camera)[1][0], 'backward lens rejected')
    data.tilt_shift_tilt = 0
    data.tilt_shift_enabled = False
    require(not guide(camera)[1][0], 'disabled guides absent')
    return {'checks': checks, 'maximum_absolute_numeric_error': maximum_error}


def persistence_case(folder, upstream_file=None, m2_file=None):
    inputs = []
    for label, path in (('upstream', upstream_file), ('m2', m2_file)):
        if path:
            bpy.ops.wm.open_mainfile(filepath=str(path.resolve()))
            for data in bpy.data.cameras:
                for field in ('focus_plane', 'lens_plane', 'image_circle'):
                    require(not getattr(data, 'tilt_shift_show_'+field), label+' false migration')
                close(data.lens, 42, 1e-6, label+' preserved original lens')
                close(data.shift_x, .13, 1e-6, label+' preserved canonical shift x')
                close(data.shift_y, -.09, 1e-6, label+' preserved canonical shift y')
                require(data.sensor_fit == 'VERTICAL', label+' preserved sensor fit')
                if label == 'upstream':
                    require(not data.tilt_shift_enabled, 'upstream remains disabled')
                else:
                    require(data.tilt_shift_enabled, 'M2 enable preserved')
                    for name, value in (('tilt', .123), ('swing', -.045),
                                        ('axis_rotation', .27), ('image_circle_diameter', 47.5)):
                        close(getattr(data, 'tilt_shift_'+name), value, 1e-6, 'M2 optical field preserved')
            inputs.append({'kind': label, 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    scene, camera, _ = m2.setup(4)
    data = camera.data
    data.tilt_shift_tilt, data.tilt_shift_swing, data.tilt_shift_axis_rotation = .12, -.07, .32
    data.tilt_shift_image_circle_diameter = 42
    data.tilt_shift_shift_x_mm, data.tilt_shift_shift_y_mm = 2.5, -1.3
    for field in ('focus_plane', 'lens_plane', 'image_circle'):
        setattr(data, 'tilt_shift_show_'+field, True)
    data.keyframe_insert('tilt_shift_tilt', frame=1)
    data.keyframe_insert('shift_x', frame=1)
    data.tilt_shift_tilt = .16
    data.shift_x += .03
    data.keyframe_insert('tilt_shift_tilt', frame=5)
    data.keyframe_insert('shift_x', frame=5)
    scene.frame_set(1)
    expected = data.tilt_shift_guide_geometry(camera)
    expected_shift = (data.shift_x, data.shift_y)
    path = folder/'m3-roundtrip.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene, camera = bpy.context.scene, bpy.context.scene.camera
    data = camera.data
    actual = data.tilt_shift_guide_geometry(camera)
    require(actual == expected, 'native roundtrip exact guide geometry')
    require((data.shift_x, data.shift_y) == expected_shift, 'canonical shift roundtrip')
    for field in ('focus_plane', 'lens_plane', 'image_circle'):
        require(getattr(data, 'tilt_shift_show_'+field), 'display toggles persisted')
    scene.frame_set(5)
    require(abs(data.tilt_shift_tilt-.16) < 1e-6, 'animation persisted')
    require(abs(data.shift_x-expected_shift[0]-.03) < 1e-6, 'canonical shift animation persisted')
    return {'checks': checks, 'migration_inputs': inputs, 'roundtrip': str(path)}


def animation_case(folder):
    scene, camera, mat = m2.setup(32)
    data = camera.data
    data.tilt_shift_image_circle_diameter = 50
    data.shift_x, data.shift_y = .02, -.01
    target_position = (.035, .012, .5)
    m2.quad('animated-centroid', *target_position, .002, .002, mat)
    records = []
    for frame, tilt, swing, axis, shift, distance in ((1, .04, -.03, .1, .02, .45),
                                                   (5, .13, .05, .4, -.025, .7)):
        data.tilt_shift_tilt, data.tilt_shift_swing, data.tilt_shift_axis_rotation = tilt, swing, axis
        data.shift_x, data.dof.focus_distance = shift, distance
        for path in ('tilt_shift_tilt', 'tilt_shift_swing', 'tilt_shift_axis_rotation', 'shift_x', 'dof.focus_distance'):
            data.keyframe_insert(path, frame=frame)
    # Repeated frame 1 proves evaluated animation returns rather than retaining stale state.
    for frame in (1, 5, 1):
        scene.frame_set(frame)
        obj, state = guide(camera)
        b = state[3]
        c = center(obj.data)
        result = m2.render(scene, folder, f'animation-manual-{frame}-{len(records)}')
        expected = [160+320*(b*(target_position[0]-c.x)/target_position[2]-c.x)/.036,
                    96+192*(b*(target_position[1]-c.y)/target_position[2]-c.y)/(.036*192/320)]
        for axis in range(2):
            close(result['centroid'][axis], expected[axis], .22, 'evaluated animation centroid')
        result.update(frame=frame, expected_centroid=expected, sensor_distance=b)
        records.append(result)
    require(records[0]['pixels_sha256'] == records[2]['pixels_sha256'], 'repeat animated frame deterministic')
    for field in ('focus_plane', 'lens_plane', 'image_circle'):
        setattr(data, 'tilt_shift_show_'+field, True)
    toggled = m2.render(scene, folder, 'animation-guides-on')
    require(toggled['pixels_sha256'] == records[0]['pixels_sha256'],
            'all visualization toggles leave rendered pixels bitwise identical')
    toggled.update(frame=1, visualization_only_bitwise_equal=True)
    records.append(toggled)
    # Focus-object dependencies update while aperture is disabled, with no new camera edits.
    data.animation_data_clear()
    data.tilt_shift_tilt, data.tilt_shift_swing, data.tilt_shift_axis_rotation = .09, -.04, .2
    data.shift_x = .02
    bpy.ops.object.empty_add(location=(.04, -.02, -.4))
    target = bpy.context.object
    data.dof.focus_object = target
    target.keyframe_insert('location', frame=1)
    target.location = (-.03, .025, -.8)
    target.keyframe_insert('location', frame=5)
    for frame in (1, 5):
        scene.frame_set(frame)
        obj, state = guide(camera)
        b, c = state[3], center(obj.data)
        check_geometry(camera, lambda ob: ob.data.dof.focus_object.matrix_world.translation)
        result = m2.render(scene, folder, f'animation-target-{frame}')
        expected = [160+320*(b*(target_position[0]-c.x)/target_position[2]-c.x)/.036,
                    96+192*(b*(target_position[1]-c.y)/target_position[2]-c.y)/(.036*192/320)]
        for axis in range(2):
            close(result['centroid'][axis], expected[axis], .22, 'evaluated focus target centroid')
        result.update(frame=frame, expected_centroid=expected, sensor_distance=b)
        records.append(result)
    require(abs(records[-1]['sensor_distance']-records[-2]['sensor_distance']) > .001,
            'target-only animation changed physical sensor distance')
    # Bone evaluation uses the same unconditional dependency relation, DOF still off.
    data.dof.focus_object = None
    target = rig(camera)
    bone = target.pose.bones['Focus']
    bone.location = (0, 0, 0)
    bone.keyframe_insert('location', frame=1)
    bone.location = (.02, -.3, -.2)
    bone.keyframe_insert('location', frame=5)
    bone_distances = []
    for frame in (1, 5, 1):
        scene.frame_set(frame)
        result = check_geometry(camera, lambda ob: ob.data.dof.focus_object.matrix_world @
                                ob.data.dof.focus_object.pose.bones['Focus'].matrix.translation)
        bone_distances.append(result['sensor_distance'])
    require(abs(bone_distances[1]-bone_distances[0]) > 1e-4, 'bone-only animation updates guides')
    close(bone_distances[0], bone_distances[2], 1e-8, 'bone frame return deterministic')
    return {'checks': checks, 'renders': records, 'bone_sensor_distances': bone_distances}


def m2_regression_case(folder):
    """Reuse immutable measured M2 functions while recording this M3 source patch."""
    results = [m2.centroid_case(folder, 'disabled-centroid', False),
               m2.centroid_case(folder, 'physical-centroid'),
               m2.centroid_case(folder, 'physical-shift', shift=(.12, -.08)),
               m2.centroid_case(folder, 'vertical-fit', shift=(.08, .06), fit='VERTICAL'),
               m2.centroid_case(folder, 'pixel-aspect', shift=(.08, -.03), fit='AUTO', pixel_aspect=(1, 2)),
               m2.centroid_case(folder, 'offaxis-focus-object', shift=(.08, -.03), dof=True, focus_object=True),
               m2.coc_case(folder), m2.tilted_focus_case(folder), m2.projection_case(folder)]
    results.extend(m2.coverage_case(folder))
    results.extend(m2.volume_and_clip_cases(folder))
    return {'results': results, 'immutable_m2_functions_reused': True}


def gui_scene(folder):
    # The caller starts an isolated factory GUI. A nested read_factory_settings
    # invalidates its window context, so construct the fixture through datablocks.
    scene = bpy.context.scene
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    import _cycles
    if not _cycles.set_device_override('CPU'):
        raise RuntimeError('Hard CPU override rejected')
    scene.render.resolution_x, scene.render.resolution_y = 320, 192
    scene.render.resolution_percentage = 100
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 2
    scene.cycles.samples = 16
    scene.cycles.seed = 71
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.use_denoising = False
    scene.world = bpy.data.worlds.new('m3-gui-world')
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0
    data = bpy.data.cameras.new('M3 Physical Camera')
    camera = bpy.data.objects.new('M3 Physical Camera', data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    data.lens, data.sensor_width = 50, 36
    data.sensor_fit = 'HORIZONTAL'
    data.clip_start, data.clip_end = .05, 10
    data.dof.use_dof = False
    data.dof.aperture_fstop = 2
    data.tilt_shift_enabled = True
    mat = m2.emission()
    bpy.context.view_layer.update()
    camera.data.tilt_shift_tilt = .14
    camera.data.tilt_shift_swing = -.06
    camera.data.tilt_shift_axis_rotation = .3
    camera.data.tilt_shift_shift_x_mm = 2
    camera.data.tilt_shift_image_circle_diameter = 44
    camera.data.dof.focus_distance = 2.0
    camera.data.display_size = 1.0
    for field in ('focus_plane', 'lens_plane', 'image_circle'):
        setattr(camera.data, 'tilt_shift_show_'+field, True)
    m2.quad('visible-subject', 0, 0, 2, .2, .2, mat)
    bpy.context.view_layer.objects.active = camera
    camera.select_set(True)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'PROPERTIES':
                area.spaces.active.context = 'DATA'
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_distance = 4
                area.spaces.active.region_3d.view_location = (0, 0, -1)
                from mathutils import Quaternion
                area.spaces.active.region_3d.view_rotation = Quaternion((.8924, .2391, -.3696, -.099))
    path = folder/'m3-interface.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    return {'scene': str(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', choices=('geometry', 'persistence', 'animation', 'gui-scene', 'm2-regression', 'm2-guards'), required=True)
    parser.add_argument('--upstream-file', type=Path)
    parser.add_argument('--m2-file', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    args.output = args.output.resolve()
    if not args.output.is_relative_to(ROOT/'work'):
        raise ValueError('Validation artifacts must be below ignored work/')
    args.output.mkdir(parents=True, exist_ok=True)
    provenance_paths = {'binary_sha256': Path(bpy.app.binary_path),
                        'script_sha256': Path(__file__),
                        'immutable_m2_script_sha256': ROOT/'scripts/blender_m2_validation.py',
                        'patch_sha256': ROOT/'patches/blender-v5.3.0-tilt-shift-m3.patch'}
    for name, path in (('upstream_input_sha256', args.upstream_file), ('m2_input_sha256', args.m2_file)):
        if path:
            provenance_paths[name] = path.resolve()
    provenance = {key: hashlib.sha256(path.read_bytes()).hexdigest()
                  for key, path in provenance_paths.items()}
    if args.case == 'geometry':
        result = geometry_case()
    elif args.case == 'persistence':
        result = persistence_case(args.output, args.upstream_file, args.m2_file)
    elif args.case == 'animation':
        result = animation_case(args.output)
    elif args.case == 'm2-guards':
        result = {'results': m2.rejection_cases(args.output)}
    elif args.case == 'm2-regression':
        result = m2_regression_case(args.output)
    else:
        result = gui_scene(args.output)
    for key, path in provenance_paths.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != provenance[key]:
            raise RuntimeError('Validation input changed during run: '+str(path))
    result.update(case=args.case, source_pin=m2.PIN, blender=str(bpy.app.binary_path), **provenance)
    (args.output/(args.case+'.json')).write_text(json.dumps(result, indent=2)+'\n')
    print('M3_VALIDATION', json.dumps(result))


if __name__ == '__main__':
    main()
