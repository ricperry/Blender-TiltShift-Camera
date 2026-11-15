# SPDX-License-Identifier: GPL-3.0-or-later
"""M4 same-executable CPU/HIP fixtures; run only in isolated Blender resources.

The immutable M2 suite is imported, with setup/render adapters in memory only.
No native source or historical fixtures are modified. Host owns resource caps.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import blender_m2_validation as m2
import blender_visual_comparison as visual

ORIGINAL_SETUP = m2.setup
ORIGINAL_RENDER = m2.render
BACKEND = None
DEVICE_RECORDS = []
TIMINGS = []


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_backend(scene):
    import _cycles
    if not _cycles.set_device_override(BACKEND.upper()):
        raise RuntimeError('Hard backend override rejected: '+BACKEND)
    prefs = bpy.context.preferences.addons['cycles'].preferences
    if BACKEND == 'cpu':
        scene.cycles.device = 'CPU'
        record = dict(backend='CPU', selected=['CPU'], hard_override='CPU')
    else:
        prefs.compute_device_type = 'HIP'
        prefs.use_hiprt = False
        available = prefs.get_devices_for_type('HIP')
        supported = [d for d in available if d.type == 'HIP' and d.meets_driver_requirement]
        if len(supported) != 1:
            raise RuntimeError('M4 requires exactly one HIP device; refusing fallback or aggregate')
        selected = supported[0]
        for device in prefs.devices:
            device.use = device.type == 'HIP' and device.id == selected.id
        if any(d.use and d.type != 'HIP' for d in prefs.devices):
            raise RuntimeError('Unexpected non-HIP execution device')
        scene.cycles.device = 'GPU'
        record = dict(backend='HIP', selected=[selected.name], selected_ids=[selected.id],
                      hard_override='HIP', use_hiprt=prefs.use_hiprt,
                      preferences=[dict(name=d.name, id=d.id, type=d.type, use=d.use)
                                   for d in prefs.devices])
    if record not in DEVICE_RECORDS:
        DEVICE_RECORDS.append(record)
    return record


def setup(samples=128):
    scene, camera, mat = ORIGINAL_SETUP(samples)
    select_backend(scene)
    return scene, camera, mat


def render(scene, folder, name):
    data = scene.camera.data
    camera_settings = {key:getattr(data,key) for key in (
        'lens','sensor_width','sensor_height','sensor_fit','shift_x','shift_y',
        'tilt_shift_enabled','tilt_shift_tilt','tilt_shift_swing',
        'tilt_shift_axis_rotation','tilt_shift_image_circle_diameter','clip_start','clip_end')}
    camera_settings['dof'] = {key:getattr(data.dof,key) for key in (
        'use_dof','focus_distance','focus_subtarget','aperture_fstop','aperture_blades',
        'aperture_rotation','aperture_ratio')}
    focus = data.dof.focus_object
    camera_settings['focus_object'] = (dict(name=focus.name,
        matrix_world=[list(row) for row in focus.matrix_world]) if focus else None)
    camera_settings['matrix_world'] = [list(row) for row in scene.camera.matrix_world]
    raster_settings = dict(pixel_aspect=[scene.render.pixel_aspect_x,scene.render.pixel_aspect_y],
                           pixel_filter_type=scene.cycles.pixel_filter_type,
                           filter_width=scene.cycles.filter_width,
                           resolution_percentage=scene.render.resolution_percentage)
    started = time.perf_counter()
    result = ORIGINAL_RENDER(scene, folder, name)
    TIMINGS.append(dict(name=name, elapsed_including_export_s=time.perf_counter()-started))
    result.update(seed=scene.cycles.seed, samples=scene.cycles.samples,
                  adaptive_sampling=scene.cycles.use_adaptive_sampling,
                  denoising=scene.cycles.use_denoising,
                  backend=BACKEND, camera_enabled=scene.camera.data.tilt_shift_enabled,
                  camera_settings=camera_settings, raster_settings=raster_settings)
    return result


m2.setup, m2.render = setup, render


def boundary_cases(folder):
    results = []
    # f/b is approximately 2e-5: valid, but only twice the unchanged 1e-5
    # host singularity margin. Uniform world avoids a guessed intersection.
    # Near-aperture case puts near clip just beyond the tilted f/2 pupil's Z
    # extent (~2.5mm), exercising clipped origins without crossing that pupil.
    for name, focus, tilt, dof, clip in (
            ('boundary-sensor', .050001, 0, False, .05),
            ('boundary-near-aperture', .5, .2, True, .003)):
        scene, camera, _ = setup(64)
        data = camera.data
        data.dof.focus_distance, data.tilt_shift_tilt = focus, tilt
        data.dof.use_dof, data.clip_start = dof, clip
        background = scene.world.node_tree.nodes.get('Background')
        background.inputs['Color'].default_value = (1, 1, 1, 1)
        background.inputs['Strength'].default_value = 1
        result = render(scene, folder, name)
        import array
        values = array.array('f')
        with (folder/(name+'.rgba32f')).open('rb') as stream:
            values.fromfile(stream, 320*192*4)
        error = max(abs(x-1) for i,x in enumerate(values) if i%4 != 3)
        if error > 2e-4:
            raise RuntimeError('Finite near-boundary unit weight failed: '+name)
        result.update(max_unit_radiance_error=error, tolerance=2e-4,
                      focus_distance_m=float(data.dof.focus_distance), clip_start_m=float(data.clip_start))
        results.append(result)
    return results


def movement_case(folder):
    scene, camera, mat = setup(256)
    data = camera.data
    data.tilt_shift_tilt, data.tilt_shift_swing = .13, -.09
    data.tilt_shift_axis_rotation = .37
    data.shift_x, data.shift_y = .09, -.06
    data.dof.use_dof = True
    data.dof.aperture_blades = 7
    data.dof.aperture_rotation = .23
    data.dof.aperture_ratio = 1.4
    data.tilt_shift_image_circle_diameter = 34
    for x, y, z in ((-.035, .02, .3), (0, 0, .5), (.05, -.025, .8)):
        m2.quad('combined-movement-target', x, y, z, .0015, .0015, mat)
    result = render(scene, folder, 'combined-movements')
    result.update(tilt_rad=.13, swing_rad=-.09, axis_rotation_rad=.37,
                  shifts=[.09, -.06], aperture_blades=7, aperture_ratio=1.4)
    return result


def chart_scene(samples=128):
    scene, camera, _ = setup(samples)
    scene.render.resolution_x, scene.render.resolution_y = 960, 600
    data = camera.data
    data.tilt_shift_tilt, data.tilt_shift_swing = .15, -.08
    data.tilt_shift_axis_rotation = .25
    data.shift_x, data.shift_y = .06, -.025
    data.dof.use_dof = True
    data.dof.aperture_fstop = 2.8
    data.dof.aperture_blades = 7
    data.dof.aperture_ratio = 1.2
    # Image-texture grid and depth rows expose pupil blur and filtering as well
    # as framing. UVs are explicit; emission avoids lighting/BVH noise hiding
    # camera differences. Coordinates below are Blender camera-local metres.
    image = bpy.data.images.new('deterministic-filter-chart', width=512, height=512)
    pixels = []
    for y in range(512):
        for x in range(512):
            cell = ((x//4) ^ (y//4)) & 1
            border = x < 12 or y < 12 or x >= 500 or y >= 500
            value = 1.0 if border or cell else .015
            pixels.extend((value, value, value, 1))
    image.pixels[:] = pixels
    for row, z in enumerate((.32, .5, .8)):
        for col in range(5):
            x = (col-2)*.085*z
            y = (row-1)*.085*z
            mat = m2.emission()
            texture = mat.node_tree.nodes.new('ShaderNodeTexImage')
            texture.image = image
            texture.interpolation = 'Linear'
            mat.node_tree.links.new(texture.outputs['Color'], mat.node_tree.nodes['Emission'].inputs['Color'])
            obj = m2.quad(f'filter-chart-{row}-{col}', x, y, z, .032*z, .032*z, mat)
            uv = obj.data.uv_layers.new(name='UVMap')
            for loop, coordinate in zip(uv.data, ((0,0), (1,0), (1,1), (0,1))):
                loop.uv = coordinate
    return scene


def benchmark(folder, repeats):
    scene = chart_scene(samples=64)
    camera = scene.camera.data
    variants = ('ordinary', 'enabled-zero', 'enabled-tilt')
    results = []
    def configure(name):
        camera.tilt_shift_enabled = name != 'ordinary'
        camera.tilt_shift_tilt = .15 if name == 'enabled-tilt' else 0
        camera.tilt_shift_swing = -.08 if name == 'enabled-tilt' else 0
    # Every mode gets its own warm-up, then order is rotated by repetition to
    # reduce drift bias. These are completed-render wall times, not GPU events.
    for name in variants:
        configure(name)
        if bpy.ops.render.render() != {'FINISHED'}:
            raise RuntimeError('Benchmark warm-up failed')
    for repeat in range(repeats):
        for index in range(3):
            name = variants[(repeat+index)%3]
            configure(name)
            started = time.perf_counter()
            if bpy.ops.render.render() != {'FINISHED'}:
                raise RuntimeError('Benchmark render failed')
            results.append(dict(name=name, repeat=repeat, elapsed_s=time.perf_counter()-started))
    medians = {name: statistics.median(item['elapsed_s'] for item in results if item['name']==name)
               for name in variants}
    return dict(name='paired-camera-benchmark', width=960, height=600, samples=64, seed=71,
                warmups_per_variant=1, repeats=repeats, timings=results, median_s=medians,
                ratio_to_ordinary={name:value/medians['ordinary'] for name,value in medians.items()},
                timing_scope='bpy completed-render wall time; includes synchronization/session overhead; no exports',
                interpretation='backend-specific camera overhead in this emission/image-texture workload only')


def visual_case(folder):
    scene, camera, rows = visual.setup(128,1280,800)
    select_backend(scene)
    camera.data.tilt_shift_enabled = True
    camera.data.tilt_shift_tilt = visual.TILT
    scene.render.image_settings.file_format = 'OPEN_EXR'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '32'
    result = render(scene,folder,'physical-focus-chart')
    result.update(physical_chart_rows=rows, matched_tilt_rad=visual.TILT,
                  sharp_plane_slope=visual.SLOPE)
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/'physical-focus-chart.blend'))
    return result


def main():
    global BACKEND
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--backend', choices=('cpu','hip'), required=True)
    parser.add_argument('--case', choices=('all','centroid','coc','tilted','projection','coverage',
                                         'volume-clips','boundaries','movements','chart','visual','guards','benchmark'), default='all')
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    BACKEND = args.backend
    folder = args.output.resolve()
    if not folder.is_relative_to(ROOT/'work'):
        raise ValueError('Artifacts must be below ignored work/')
    if args.repeats < 3:
        raise ValueError('Benchmark requires at least three paired repeats')
    folder.mkdir(parents=True, exist_ok=True)
    paths = dict(binary_sha256=Path(bpy.app.binary_path), fixture_script_sha256=Path(__file__),
                 immutable_m2_script_sha256=ROOT/'scripts/blender_m2_validation.py',
                 immutable_visual_script_sha256=ROOT/'scripts/blender_visual_comparison.py',
                 patch_sha256=ROOT/'patches/blender-v5.3.0-tilt-shift-m4.patch')
    kernels = list((Path(bpy.app.binary_path).parent/'5.3/scripts/addons_core/cycles/lib').glob('kernel_gfx1030.fatbin.zst'))
    if BACKEND == 'hip' and len(kernels) != 1:
        raise RuntimeError('Expected one installed gfx1030 kernel: '+repr(kernels))
    if kernels:
        paths['hip_kernel_sha256'] = kernels[0]
    provenance = {key:digest(path) for key,path in paths.items()}
    results = []
    if args.case in ('all','centroid'):
        results.extend([m2.centroid_case(folder,'disabled-centroid',False),
                        m2.centroid_case(folder,'physical-centroid'),
                        m2.centroid_case(folder,'physical-shift',shift=(.12,-.08)),
                        m2.centroid_case(folder,'vertical-fit',shift=(.08,.06),fit='VERTICAL'),
                        m2.centroid_case(folder,'pixel-aspect',shift=(.08,-.03),fit='AUTO',pixel_aspect=(1,2)),
                        m2.centroid_case(folder,'offaxis-focus-object',shift=(.08,-.03),dof=True,focus_object=True)])
    if args.case in ('all','coc'): results.append(m2.coc_case(folder))
    if args.case in ('all','tilted'): results.append(m2.tilted_focus_case(folder))
    if args.case in ('all','projection'): results.append(m2.projection_case(folder))
    if args.case in ('all','coverage'): results.extend(m2.coverage_case(folder))
    if args.case in ('all','volume-clips'): results.extend(m2.volume_and_clip_cases(folder))
    if args.case in ('all','boundaries'): results.extend(boundary_cases(folder))
    if args.case in ('all','movements'): results.append(movement_case(folder))
    if args.case == 'chart': results.append(render(chart_scene(),folder,'large-filter-chart'))
    if args.case == 'visual': results.append(visual_case(folder))
    if args.case == 'benchmark': results.append(benchmark(folder,args.repeats))
    if args.case == 'guards': results.extend(m2.rejection_cases(folder))
    for key,path in paths.items():
        if digest(path) != provenance[key]:
            raise RuntimeError('Validation input changed during run: '+str(path))
    summary = dict(source_pin=m2.PIN, blender=str(bpy.app.binary_path), backend=BACKEND,
                   **provenance, devices=DEVICE_RECORDS, results=results, render_timings=TIMINGS,
                   byteorder=sys.byteorder)
    (folder/(args.case+'-results.json')).write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
