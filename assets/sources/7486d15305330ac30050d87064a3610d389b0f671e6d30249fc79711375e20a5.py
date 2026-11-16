# SPDX-License-Identifier: GPL-3.0-or-later
"""Animate native optical controls from immutable comparison scenes in Blender."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from create_demo_comparisons import backend, camera_normal, file_hash, settings

# Bounds are finite photographic examples, never a claim about the full RNA domain.
SPECS = {
    'tilt': dict(label='Lens tilt', path='tilt_shift_tilt', unit='deg', bounds=[-20, 20]),
    'swing': dict(label='Lens swing', path='tilt_shift_swing', unit='deg', bounds=[-20, 20]),
    'axis': dict(label='Movement axis rotation', path='tilt_shift_axis_rotation', unit='deg', bounds=[-180, 180], range_note='Full RNA movement-axis cycle'),
    'shift-x': dict(label='Horizontal shift', path='shift_x', unit='sensor widths', bounds=[-.5, .5]),
    'shift-y': dict(label='Vertical shift', path='shift_y', unit='sensor widths', bounds=[-.5, .5]),
    'focus': dict(label='Focus distance', path='dof.focus_distance', unit='m', bounds=[1, 2.2]),
    'lens': dict(label='Focal length', path='lens', unit='mm', bounds=[35, 135]),
    'fstop': dict(label='Aperture', path='dof.aperture_fstop', unit='f/', bounds=[1, 32], interpolation='log'),
}


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def below_work(path):
    path = path.resolve()
    if not path.is_relative_to(ROOT / 'work'):
        raise ValueError('Generated artifacts must remain below ignored work/')
    return path


def source_scene(directory, name):
    """Require saved scene, image and captured source to match the render record."""
    path = directory / (name + '.json')
    record = json.loads(path.read_text())
    hashes = {'manifest_sha256': file_hash(path)}
    for suffix, key in (('blend', 'blend_sha256'), ('png', 'image_sha256')):
        artifact = directory / f'{name}.{suffix}'
        hashes[key] = file_hash(artifact)
        if hashes[key] != record[key]:
            raise ValueError(f'Immutable source {artifact} differs from its manifest')
    candidates = list(directory.glob('*generator-source.py'))
    snapshots = [p for p in candidates if file_hash(p) == record['source_sha256']]
    if not snapshots:
        raise ValueError(f'{name}: captured render-generator source missing or changed')
    hashes['captured_generator_sha256'] = record['source_sha256']
    handler_names = ('load_post', 'frame_change_pre', 'frame_change_post')
    handlers_before = {name: tuple(getattr(bpy.app.handlers, name)) for name in handler_names}
    bpy.ops.wm.open_mainfile(filepath=str(directory / f'{name}.blend'), load_ui=False, use_scripts=False)
    if bpy.data.libraries or any(image.filepath for image in bpy.data.images if image.source == 'FILE'):
        raise ValueError('Animation inputs must be self-contained')
    if any(tuple(getattr(bpy.app.handlers, name)) != handlers_before[name] for name in handler_names):
        raise ValueError('Animation input changed load/frame handlers')
    if any(text.use_module for text in bpy.data.texts):
        raise ValueError('Animation inputs must not contain execute-on-load text modules')
    return dict(case=name, directory=str(directory), **hashes)


def owner_property(data, path):
    parts = path.split('.')
    owner = data
    for part in parts[:-1]:
        owner = getattr(owner, part)
    return owner, parts[-1]


def optical_state(camera):
    data = camera.data
    paths = [spec['path'] for spec in SPECS.values()]
    values = {path: float(getattr(*owner_property(data, path))) for path in paths}
    return dict(values=values, matrix_world=[list(row) for row in camera.matrix_world],
                clip=[data.clip_start, data.clip_end], sensor=[data.sensor_width, data.sensor_height],
                sensor_fit=data.sensor_fit, focus_object=None if data.dof.focus_object is None else data.dof.focus_object.name,
                dof=data.dof.use_dof, native=data.tilt_shift_enabled,
                circle=data.tilt_shift_image_circle_diameter, blades=data.dof.aperture_blades,
                aperture_rotation=data.dof.aperture_rotation, ratio=data.dof.aperture_ratio)


def preflight(scene, camera):
    """Evaluated RNA guide plus a mirror of Cycles Camera::tilt_shift_error.

    The native C++ gate is internal, with no Python entry point. Actual rendering
    still executes it; this preflight does not claim to call that internal gate.
    The restricted fixture uses horizontal fit, square pixels and no crop/roll.
    """
    bpy.context.view_layer.update()
    camera = camera.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data = camera.data
    if not data.tilt_shift_enabled or data.type != 'PERSP' or not data.dof.use_dof:
        raise ValueError('Expected enabled native perspective camera with DOF')
    if data.dof.focus_object is not None or data.sensor_fit != 'HORIZONTAL':
        raise ValueError('Fixture requires manual focus and horizontal sensor fit')
    if scene.render.use_motion_blur or scene.render.use_multiview or any(v.use_pass_vector for v in scene.view_layers):
        raise ValueError('Motion or stereo unsupported by native camera')
    if scene.render.use_border or scene.render.pixel_aspect_x != 1 or scene.render.pixel_aspect_y != 1:
        raise ValueError('Fixture requires full raster and square pixels')
    if any(getattr(mod, 'use_adaptive_subdivision', False) for obj in scene.objects for mod in obj.modifiers):
        raise ValueError('Adaptive subdivision unsupported by native camera')
    result = data.tilt_shift_guide_geometry(camera)
    if not result[0] or not result[1] or not math.isfinite(result[3]) or result[3] <= 0:
        raise ValueError(f'Frame {scene.frame_current}: invalid evaluated native guide')
    f, b, n = data.lens * .001, result[3], camera_normal(data)
    # Reconstruct the manual conjugate independently, then use its stable plane
    # coefficient f/D rather than subtracting n.z-f/b after RNA rounds b to f32.
    # At zero tilt and 220 m that subtraction amplifies b's rounding to metres.
    expected_b = f / (n.z-f/data.dof.focus_distance)
    b_error = abs(b-expected_b)
    b_tolerance = 2e-6 * max(f, abs(expected_b))
    if not math.isfinite(expected_b) or b_error > b_tolerance:
        raise ValueError('Evaluated sensor distance disagrees with manual conjugate')
    if not all(math.isfinite(v) for v in optical_state(camera)['values'].values()):
        raise ValueError('Nonfinite optical parameter')
    epsilon = 1e-5
    if n.z <= epsilon or f / b <= epsilon:
        raise ValueError('Singular sensor distance')
    radius = f / (2 * max(data.dof.aperture_fstop, 1e-5))
    ratio = data.dof.aperture_ratio
    t, s = data.tilt_shift_tilt, data.tilt_shift_swing
    az = radius * math.sqrt((math.sin(s)/ratio)**2 + (math.cos(s)*math.sin(t))**2)
    scale = max(f, b, radius/ratio, radius)
    if data.clip_start <= az + epsilon * scale or data.clip_end <= data.clip_start:
        raise ValueError('Clip planes intersect tilted aperture')
    # view_frame gives the unbreathed nominal perspective raster; native sensor
    # inversion multiplies its slopes by -f and uses the actual sensor distance b.
    frame = data.view_frame(scene=scene)
    xlo, xhi = min(p.x/abs(p.z) for p in frame), max(p.x/abs(p.z) for p in frame)
    ylo, yhi = min(p.y/abs(p.z) for p in frame), max(p.y/abs(p.z) for p in frame)
    padding = 1.5 * scene.cycles.filter_width + 1
    dx = (xhi-xlo) * padding / scene.render.resolution_x
    dy = (yhi-ylo) * padding / scene.render.resolution_y
    margins = []
    for x in (xlo-dx, xhi+dx):
        for y in (ylo-dy, yhi+dy):
            p = Vector((-f*x, -f*y, -b))
            np = n.dot(p)
            h = 1 + np/f
            local = max(scale, abs(p.x), abs(p.y))
            margin = min(-np-epsilon*local, b-abs(h)*az-epsilon*local, b-az-epsilon*local)
            if not math.isfinite(margin) or margin <= 0:
                raise ValueError(f'Frame {scene.frame_current}: sensor/aperture backward-ray domain')
            margins.append(margin)
    centre = Vector((data.sensor_width*.001*data.shift_x, data.sensor_width*.001*data.shift_y, 0))
    m = Vector((n.x, n.y, f/data.dof.focus_distance))
    vertices = [Vector((result[5][i], result[5][i+1], -result[5][i+2])) for i in range(0, 12, 3)]
    error = max(abs(m.dot(p-centre)-f)/m.length for p in vertices)
    tolerance = 2e-4 * max(1, data.dof.focus_distance)
    if error > tolerance:
        raise ValueError('Evaluated focus guide disagrees with optical plane')
    return dict(guide_valid=True, focus_guide_valid=True, sensor_distance_m=b,
                expected_manual_sensor_distance_m=expected_b, sensor_distance_error_m=b_error,
                sensor_distance_tolerance_m=b_tolerance,
                normal_cycles=list(n), focus_guide_error_m=error, guide_tolerance_m=tolerance,
                guard_mirror_valid=True, minimum_raster_guard_margin_m=min(margins),
                aperture_forward_extent_m=az, near_clip_margin_m=data.clip_start-az-epsilon*scale)


def animate(name, spec, args):
    directory = args.output / name
    directory.mkdir(parents=True, exist_ok=True)
    source = source_scene(args.source, name + '-native' if name in ('shift-x', 'shift-y') else 'table-native')
    scene, camera = bpy.context.scene, bpy.context.scene.camera
    data = camera.data
    for obj in scene.objects:
        obj.animation_data_clear()
        if obj.data and hasattr(obj.data, 'animation_data_clear'):
            obj.data.animation_data_clear()
    data.dof.focus_object = None
    data.tilt_shift_tilt = math.radians(-10)
    data.tilt_shift_swing = data.tilt_shift_axis_rotation = 0
    if name in ('tilt', 'swing', 'shift-x', 'shift-y'):
        data.tilt_shift_tilt = 0
    if name in ('shift-x', 'shift-y'):
        data.shift_x = data.shift_y = 0
    settings(scene, args)
    scene.cycles.use_animated_seed = False
    scene.render.fps, scene.render.fps_base = args.fps, 1
    count = args.fps * args.seconds
    scene.frame_start, scene.frame_end = 1, count
    scene.render.use_file_extension = True
    owner, prop = owner_property(data, spec['path'])
    lo, hi = spec['bounds']
    values = []
    for index in range(count):
        fraction = index / (count-1)
        value = math.exp(math.log(lo)+(math.log(hi)-math.log(lo))*fraction) if spec.get('interpolation') == 'log' else lo+(hi-lo)*fraction
        stored = math.radians(value) if spec['unit'] == 'deg' else value
        setattr(owner, prop, stored)
        if not math.isclose(getattr(owner, prop), stored, rel_tol=2e-6, abs_tol=1e-7):
            raise ValueError(f'{name}: RNA clamped requested value {value}')
        owner.keyframe_insert(data_path=prop, frame=index+1, group=spec['label'])
        values.append(value)
    # Blender 5 layered action stores channels in channel bags.
    for layer in data.animation_data.action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:
                        key.interpolation = 'LINEAR'
    frames, baseline = [], None
    for number, value in enumerate(values, 1):
        scene.frame_set(number)
        state = optical_state(camera)
        fixed = json.loads(json.dumps(state))
        fixed['values'].pop(spec['path'])
        if baseline is None:
            baseline = fixed
        elif fixed != baseline:
            raise ValueError(f'{name}: another camera setting or pose changed at frame {number}')
        actual = state['values'][spec['path']]
        expected = math.radians(value) if spec['unit'] == 'deg' else value
        if not math.isclose(actual, expected, rel_tol=2e-6, abs_tol=1e-7):
            raise ValueError(f'{name}: evaluated animation value differs from requested frame {number}')
        display = math.degrees(actual) if spec['unit'] == 'deg' else actual
        frames.append(dict(frame=number, time_s=(number-1)/args.fps, requested_value=value,
                           value=display, native_value=actual, optical_state=state,
                           preflight=preflight(scene, camera)))
        if name in ('shift-x', 'shift-y'):
            frames[-1]['shift_mm'] = actual * data.sensor_width
    generator = file_hash(__file__)
    configuration = dict(clip=name, spec=spec, source=source, frames=count, fps=args.fps,
                         resolution=args.resolution, samples=args.samples, seed=71,
                         backend=args.backend, generator_sha256=generator,
                         helper_sha256=file_hash(ROOT/'examples/create_demo_comparisons.py'),
                         blender_binary_sha256=file_hash(bpy.app.binary_path),
                         cumulative_patch_sha256=file_hash(ROOT/'patches/blender-v5.3.0-tilt-shift-m4.patch'))
    signature = canonical_hash(configuration)
    manifest = directory / 'animation.json'
    previous = json.loads(manifest.read_text()) if manifest.exists() else None
    if previous and previous['configuration_sha256'] != signature:
        raise ValueError(f'{name}: existing output has different configuration; choose a new --output')
    record = dict(schema=1, configuration=configuration, configuration_sha256=signature,
                  duration_s=args.seconds, range_kind='full RNA axis cycle' if name == 'axis' else 'representative photographic range',
                  guard_method='evaluated RNA guides plus Python mirror of internal Cycles camera gate; actual render calls native gate',
                  frames=frames, saved_device='CPU', denoising=False, adaptive_sampling=False,
                  animated_seed=False, compositor=False, motion_blur=False, render_devices=[])
    scene.frame_set(1)
    scene.render.filepath = '//raw/frame-'
    blend = directory / (name + '.blend')
    if previous:
        if not blend.exists() or file_hash(blend) != previous['blend_sha256']:
            raise ValueError(f'{name}: existing animated blend changed')
        record['blend_sha256'] = previous['blend_sha256']
        for current, old in zip(frames, previous['frames']):
            if current != {k:v for k,v in old.items() if k not in ('render',)}:
                raise ValueError(f'{name}: evaluated preflight differs from previous run')
            if 'render' in old:
                current['render'] = old['render']
    else:
        bpy.ops.wm.save_as_mainfile(filepath=str(blend), check_existing=False)
        record['blend_sha256'] = file_hash(blend)
    write_json(manifest, record)
    if args.preflight_only:
        print(f'ANIMATION PREFLIGHT {name}: {count} valid frames', flush=True)
        return
    devices = backend(scene, args.backend)
    record['render_devices'] = devices
    selected = set(args.frames or range(1, count+1))
    if any(number < 1 or number > count for number in selected):
        raise ValueError('--frames entries must be within the complete clip')
    raw = directory / 'raw'
    raw.mkdir(exist_ok=True)
    scene.render.use_persistent_data = True
    for frame in frames:
        if frame['frame'] not in selected:
            continue
        image = raw / f"frame-{frame['frame']:04d}.png"
        if 'render' in frame:
            if not image.exists() or file_hash(image) != frame['render']['sha256']:
                raise ValueError(f'Recorded frame missing or changed: {image}')
            print(f'ANIMATION RESUME {name} {frame["frame"]}', flush=True)
            continue
        if image.exists():
            raise ValueError(f'Unrecorded frame exists; refusing arbitrary resume: {image}')
        scene.frame_set(frame['frame'])
        preflight(scene, camera)
        scene.render.filepath = str(image)
        start = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        frame['render'] = dict(sha256=file_hash(image), elapsed_s=time.perf_counter()-start,
                               backend=args.backend, devices=devices, native_gate_passed=True)
        write_json(manifest, record)
        print(f'ANIMATION FRAME {name} {frame["frame"]}/{count} {frame["render"]["elapsed_s"]:.3f}s', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clip', choices=['all', *SPECS], action='append')
    parser.add_argument('--source', type=Path, default=ROOT/'work/demo-comparisons/4k')
    parser.add_argument('--output', type=Path, default=ROOT/'work/demo-animations/960x540')
    parser.add_argument('--ranges', type=Path, help='JSON mapping clip names to [min,max], or spec overrides including bounds/interpolation')
    parser.add_argument('--preflight-only', action='store_true')
    parser.add_argument('--frames', nargs='+', type=int, help='Subset to render; full-clip animation and preflight always retained')
    parser.add_argument('--samples', type=int, default=256)
    parser.add_argument('--backend', choices=['CPU', 'HIP'], default='HIP')
    parser.add_argument('--resolution', nargs=2, type=int, default=[960, 540])
    parser.add_argument('--fps', choices=[5, 6, 7, 8, 9, 10], type=int, default=5)
    parser.add_argument('--seconds', type=int, default=10)
    parser.add_argument('--threads', type=int, default=2)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    args.source, args.output = below_work(args.source), below_work(args.output)
    if args.output == args.source or args.output.is_relative_to(args.source):
        raise ValueError('Animation output must be separate from immutable input directory')
    if args.samples < 1 or args.seconds < 1 or min(args.resolution) < 1:
        raise ValueError('Positive samples, duration and resolution required')
    specs = json.loads(json.dumps(SPECS))
    if args.ranges:
        for name, override in json.loads(args.ranges.read_text()).items():
            if name not in specs:
                raise ValueError(f'Unknown clip {name}')
            if isinstance(override, list):
                specs[name]['bounds'] = override
            else:
                if set(override) - {'bounds', 'interpolation', 'range_note'}:
                    raise ValueError('Only bounds, interpolation and range_note can be overridden')
                specs[name].update(override)
    for name, spec in specs.items():
        lo, hi = spec['bounds']
        if not math.isfinite(lo) or not math.isfinite(hi) or lo >= hi or (spec.get('interpolation') == 'log' and lo <= 0):
            raise ValueError(f'{name}: invalid finite bounds')
    selected = list(specs) if not args.clip or 'all' in args.clip else list(dict.fromkeys(args.clip))
    for name in selected:
        animate(name, specs[name], args)


if __name__ == '__main__':
    main()
