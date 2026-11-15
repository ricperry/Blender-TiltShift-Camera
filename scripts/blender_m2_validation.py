# SPDX-License-Identifier: GPL-3.0-or-later
"""Native M2 quantitative fixtures; run using Blender --background -noaudio.

This is separate from the immutable M1 disabled-baseline scene generator.
No user file is opened or edited. Artifacts go to the requested work directory.
"""
import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
PIN = '02f0899d78e374b63e7181d9061e1f7ab03419cc'


def emission():
    mat = bpy.data.materials.new('unit-emission')
    nodes = mat.node_tree.nodes
    nodes.clear()
    emit = nodes.new('ShaderNodeEmission')
    out = nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(emit.outputs[0], out.inputs['Surface'])
    return mat


def quad(name, x, y, z, half_width, half_height, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(x-half_width, y-half_height, -z), (x+half_width, y-half_height, -z),
                      (x+half_width, y+half_height, -z), (x-half_width, y+half_height, -z)],
                     [], [(0, 1, 2, 3)])
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def setup(samples=128):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    import _cycles
    if not _cycles.set_device_override('CPU'):
        raise RuntimeError('Hard CPU override rejected')
    scene.render.resolution_x, scene.render.resolution_y = 320, 192
    scene.render.resolution_percentage = 100
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 2
    scene.cycles.samples = samples
    scene.cycles.seed = 71
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.use_denoising = False
    scene.cycles.pixel_filter_type = 'BOX'
    scene.cycles.filter_width = 1.0
    scene.world = bpy.data.worlds.new('black-world')
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0
    scene.render.image_settings.file_format = 'OPEN_EXR'
    scene.render.image_settings.color_depth = '32'
    scene.render.image_settings.color_mode = 'RGBA'
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    scene.camera = camera
    data = camera.data
    if 'tilt_shift_enabled' not in data.bl_rna.properties:
        raise RuntimeError('Native M2 RNA absent')
    data.lens = 50
    data.sensor_width = 36
    data.sensor_fit = 'HORIZONTAL'
    data.clip_start, data.clip_end = .05, 10
    data.dof.focus_distance = .5
    data.dof.aperture_fstop = 2
    data.dof.use_dof = False
    data.tilt_shift_enabled = True
    return scene, camera, emission()


def render(scene, folder, name):
    path = folder / (name + '.exr')
    scene.render.filepath = str(path)
    if bpy.ops.render.render(write_still=True) != {'FINISHED'}:
        raise RuntimeError('Render failed: ' + name)
    image = bpy.data.images.load(str(path), check_existing=False)
    width, height = image.size
    values = array.array('f', image.pixels[:])
    if len(values) != width*height*4 or not all(math.isfinite(x) for x in values):
        raise RuntimeError('Invalid pixels: ' + name)
    values.tofile(path.with_suffix('.rgba32f').open('wb'))
    # Linear EXR is the measurement; PNG is for visual inspection only.
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_depth = '8'
    image.save_render(str(path.with_suffix('.png')), scene=scene)
    scene.render.image_settings.file_format = 'OPEN_EXR'
    scene.render.image_settings.color_depth = '32'
    pixels = [(i % width + .5, i // width + .5, max(0, values[4*i]))
              for i in range(width*height)]
    total = sum(v for _, _, v in pixels)
    if total <= 0:
        raise RuntimeError('Empty fixture: ' + name)
    cx = sum(x*v for x, _, v in pixels)/total
    cy = sum(y*v for _, y, v in pixels)/total
    vx = sum((x-cx)**2*v for x, _, v in pixels)/total
    vy = sum((y-cy)**2*v for _, y, v in pixels)/total
    return dict(name=name, width=width, height=height, centroid=[cx, cy],
                variance=[vx, vy], flux=total,
                pixels_sha256=hashlib.sha256(values.tobytes()).hexdigest())


def assert_close(actual, expected, tolerance, label):
    if abs(actual-expected) > tolerance:
        raise RuntimeError(f'{label}: {actual} versus {expected}, tolerance {tolerance}')


def centroid_case(folder, name, enabled=True, shift=(0, 0), fit='HORIZONTAL',
                  pixel_aspect=(1, 1), dof=False, focus_object=False):
    scene, camera, mat = setup(128)
    data = camera.data
    data.tilt_shift_enabled = enabled
    data.shift_x, data.shift_y = shift
    data.sensor_fit = fit
    scene.render.pixel_aspect_x, scene.render.pixel_aspect_y = pixel_aspect
    target = (.045, .018, .5)
    quad('centroid-target', *target, .0015, .0015, mat)
    if focus_object:
        data.tilt_shift_tilt = .10
        data.tilt_shift_swing = -.07
        bpy.ops.object.empty_add(location=(target[0], target[1], -target[2]))
        data.dof.focus_object = bpy.context.object
    data.dof.use_dof = dof
    result = render(scene, folder, name)
    f, sensor = .05, (.036 if fit != 'VERTICAL' else .024)
    aspect = (320*pixel_aspect[0])/(192*pixel_aspect[1])
    horizontal = fit == 'HORIZONTAL' or (fit == 'AUTO' and aspect > 1)
    sw, sh = (sensor, sensor/aspect) if horizontal else (sensor*aspect, sensor)
    cx, cy = sensor*shift[0], sensor*shift[1]
    b = f*.5/(.5-f) if enabled else f
    if focus_object:
        # Independent double Rz(0)Ry(swing)Rx(tilt), reflected Y.
        tilt, swing = data.tilt_shift_tilt, data.tilt_shift_swing
        n = (math.sin(swing)*math.cos(tilt), math.sin(tilt),
             math.cos(swing)*math.cos(tilt))
        q = (target[0]-cx, target[1]-cy, target[2])
        b = f*q[2]/(sum(a*v for a, v in zip(n, q))-f)
    ox, oy = (cx, cy) if enabled else (0, 0)
    expected = [160+320*(b*(target[0]-ox)/target[2]-cx)/sw,
                96+192*(b*(target[1]-oy)/target[2]-cy)/sh]
    result.update(expected_centroid=expected, centroid_tolerance_px=.22,
                  physical_lens_center_m=[ox, oy, 0], sensor_distance_m=b)
    for axis in range(2):
        assert_close(result['centroid'][axis], expected[axis], .22, name+' centroid')
    if focus_object:
        # Object on the true tilted focus plane stays sharp with f/2 aperture.
        pinhole_var = ((320*b*.003/(target[2]*sw))**2)/12
        if sum(result['variance']) > 2*pinhole_var+1.2:
            raise RuntimeError('Offaxis focus object remained defocused')
    return result


def coc_case(folder):
    scene, camera, mat = setup(1024)
    camera.data.dof.use_dof = True
    z, half_size = .3, .0009
    quad('small-square', 0, 0, z, half_size, half_size, mat)
    result = render(scene, folder, 'untilted-coc')
    f, focus, radius, sw = .05, .5, .0125, .036
    b = f*focus/(focus-f)
    expected = 2*radius*abs(1-b*(1/f-1/z))*320/sw
    square_width = 2*half_size*b/z*320/sw
    # Convolution adds second moments; a uniform disk has VarX+VarY=D^2/8,
    # while the resolved emitter square contributes width^2/6. Pixel filter and
    # Monte Carlo residual are covered by the explicit .8 px bound.
    measured = math.sqrt(max(0, 8*(sum(result['variance'])-square_width**2/6)))
    result.update(expected_coc_diameter_px=expected, measured_coc_diameter_px=measured,
                  emitter_width_px=square_width, coc_tolerance_px=.8)
    assert_close(measured, expected, .8, 'Physical CoC second moment')
    return result


def tilted_focus_case(folder):
    scene, camera, mat = setup(256)
    data = camera.data
    data.tilt_shift_tilt = .18
    data.tilt_shift_swing = -.12
    data.dof.use_dof = True
    f, d = .05, .5
    tilt, swing = data.tilt_shift_tilt, data.tilt_shift_swing
    n = (math.sin(swing)*math.cos(tilt), math.sin(tilt), math.cos(swing)*math.cos(tilt))
    targets = []
    for x, y in [(-.055, .025), (0, 0), (.055, -.025)]:
        z = d*(1-(n[0]*x+n[1]*y)/f)
        targets.append(quad('on-sharp-plane', x, y, z, .0009, .0009, mat))
    sharp = render(scene, folder, 'scheimpflug-sharp')
    # Use local windows separated by >50px. Compare each render's localized
    # second moments on the same physical targets, first optically tilted then
    # untilted. The independent float reference establishes the plane law.
    data.tilt_shift_tilt = data.tilt_shift_swing = 0
    blurred = render(scene, folder, 'scheimpflug-untilted')
    def windows(name):
        values = array.array('f')
        with (folder/(name+'.rgba32f')).open('rb') as stream:
            values.fromfile(stream,320*192*4)
        result=[]
        for left,right in [(0,130),(130,190),(190,320)]:
            pts=[(i%320+.5,i//320+.5,max(0,values[4*i]))
                 for i in range(320*192) if left<=i%320<right]
            total=sum(v for _,_,v in pts)
            cx=sum(x*v for x,_,v in pts)/total
            cy=sum(y*v for _,y,v in pts)/total
            result.append(sum(((x-cx)**2+(y-cy)**2)*v for x,y,v in pts)/total)
        return result
    a,b=windows('scheimpflug-sharp'),windows('scheimpflug-untilted')
    if not (a[0]<b[0]*.55 and a[2]<b[2]*.55):
        raise RuntimeError(f'Tilted-plane sharpness failed: tilted {a}, untilted {b}')
    return dict(name='scheimpflug-plane', tilted_window_variances=a,
                untilted_window_variances=b, required_outer_variance_ratio=.55,
                renders=[sharp,blurred])


def projection_case(folder):
    scene,camera,_=setup(64)
    camera.data.shift_x,camera.data.shift_y=.12,-.08
    camera.data.tilt_shift_tilt=.1
    camera.data.tilt_shift_swing=-.06
    camera.location=(.3,.1,.2)
    camera.rotation_euler=(.1,.2,.3)
    nodes=scene.world.node_tree.nodes
    coords=nodes.new('ShaderNodeTexCoord')
    background=nodes.get('Background')
    scene.world.node_tree.links.new(coords.outputs['Window'],background.inputs['Color'])
    background.inputs['Strength'].default_value=1
    result=render(scene,folder,'shifted-world-window')
    values=array.array('f')
    with (folder/'shifted-world-window.rgba32f').open('rb') as stream:
        values.fromfile(stream,320*192*4)
    means=[sum(values[channel::4])/(320*192) for channel in (0,1)]
    for value in means: assert_close(value,.5,.0002,'world Window projection mean')
    result.update(mean_window_xy=means,expected_window_xy=[.5,.5],mean_tolerance=.0002)
    return result


def coverage_case(folder):
    results=[]
    for name,tilt,swing in [('coverage-untilted',0,0),('coverage-tilted',.07,-.04)]:
        scene,camera,mat=setup(32)
        data=camera.data
        data.tilt_shift_tilt,data.tilt_shift_swing=tilt,swing
        data.tilt_shift_image_circle_diameter=16
        quad('uniform-emission',0,0,.8,2,2,mat)
        result=render(scene,folder,name)
        values=array.array('f')
        with (folder/(name+'.rgba32f')).open('rb') as stream:
            values.fromfile(stream,320*192*4)
        f,sw,sh,radius=.05,.036,.036*192/320,.008
        n=(math.sin(swing)*math.cos(tilt),math.sin(tilt),math.cos(swing)*math.cos(tilt))
        b=f/(n[2]-f/.5)
        expected_area=0
        interior_errors=[]
        exterior_errors=[]
        for y in range(192):
            for x in range(320):
                point=(-sw*((x+.5)/320-.5),-sh*((y+.5)/192-.5),-b)
                np=sum(a*v for a,v in zip(n,point))
                rear=[-f*v/np+f*a for a,v in zip(n,point)]
                radial=math.sqrt(sum(v*v for v in rear))
                value=values[4*(y*320+x)]
                expected_area+=radial<=radius
                if radial<radius-.0003: interior_errors.append(abs(value-1))
                if radial>radius+.0003: exterior_errors.append(abs(value))
        if max(interior_errors)>2e-4 or max(exterior_errors)>2e-4:
            raise RuntimeError('Angular coverage mask failed: '+name)
        assert_close(result['flux'],expected_area,expected_area*.015,name+' covered area')
        result.update(expected_center_sample_area_px=expected_area,
                      relative_area_tolerance=.015,edge_exclusion_rear_plane_m=.0003,
                      max_interior_error=max(interior_errors),max_exterior_error=max(exterior_errors))
        results.append(result)
    return results


def volume_and_clip_cases(folder):
    scene,camera,mat=setup(64)
    camera.data.dof.use_dof=True
    camera.data.tilt_shift_tilt=.15
    camera.data.tilt_shift_swing=.07
    camera.data.clip_start=.1
    quad('uniform-background',0,0,.8,2,2,mat)
    volume=bpy.data.materials.new('homogeneous-absorption')
    nodes=volume.node_tree.nodes
    nodes.clear()
    absorb=nodes.new('ShaderNodeVolumeAbsorption')
    absorb.inputs['Color'].default_value=(0,0,0,1)
    absorb.inputs['Density'].default_value=2
    out=nodes.new('ShaderNodeOutputMaterial')
    volume.node_tree.links.new(absorb.outputs[0],out.inputs['Volume'])
    bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,-.19))
    slab=bpy.context.object
    slab.scale=(2,2,.22) # Camera-Z slab .08 to .30; near ray starts inside it.
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    slab.data.materials.append(volume)
    result=render(scene,folder,'tilted-aperture-volume')
    values=array.array('f')
    with (folder/'tilted-aperture-volume.rgba32f').open('rb') as stream:
        values.fromfile(stream,320*192*4)
    center=sum(values[4*(y*320+x)] for y in range(92,100) for x in range(156,164))/64
    expected=math.exp(-2*(.3-.1))
    # The actual sampled tilted aperture and 8x8 center window change d.z by
    # <.001. This .005 radiance bound includes that effect and float integration.
    assert_close(center,expected,.005,'volume stack initialized from clipped physical ray')
    result.update(center_mean=center,analytic_axial_transmittance=expected,radiance_tolerance=.005)

    scene,camera,white=setup(256)
    data=camera.data
    data.dof.use_dof=True
    data.tilt_shift_tilt=.15
    data.tilt_shift_swing=.07
    data.clip_start,data.clip_end=.1,.3
    red,blue=emission(),emission()
    red.node_tree.nodes.get('Emission').inputs['Color'].default_value=(1,0,0,1)
    blue.node_tree.nodes.get('Emission').inputs['Color'].default_value=(0,0,1,1)
    quad('before-near',-.01782,0,.099,.003,.01,red)
    quad('inside-clips',0,0,.2,.003,.01,white)
    quad('beyond-far',.05418,0,.301,.004,.02,blue)
    clips=render(scene,folder,'tilted-aperture-clips')
    values=array.array('f')
    with (folder/'tilted-aperture-clips.rgba32f').open('rb') as stream:
        values.fromfile(stream,320*192*4)
    left=sum(values[4*i] for i in range(320*192) if i%320<120)
    right=sum(values[4*i+2] for i in range(320*192) if i%320>200)
    if left>1e-8 or right>1e-8:
        raise RuntimeError(f'Tilted aperture clipping leaked near/far targets: {left}, {right}')
    clips.update(pre_near_red_flux=left,post_far_blue_flux=right,excluded_flux_tolerance=1e-8)
    return [result,clips]


def rejection_cases(folder):
    results=[]
    for name, expected in [('invalid-focus','singular sensor'),('near-aperture','clip planes'),
                           ('motion-blur','motion blur'),('motion-pass','motion'),
                           ('orthographic','perspective'),('multiview','stereo'),
                           ('adaptive-subdivision','adaptive subdivision'),
                           ('adaptive-dicing-camera','adaptive subdivision')]:
        scene,camera,mat=setup(1)
        obj=quad('guard-target',0,0,.5,.03,.03,mat)
        if name=='invalid-focus': camera.data.dof.focus_distance=.02
        elif name=='near-aperture':
            camera.data.dof.use_dof=True
            camera.data.tilt_shift_tilt=.2
            camera.data.clip_start=.001
        elif name=='motion-blur': scene.render.use_motion_blur=True
        elif name=='motion-pass': scene.view_layers[0].use_pass_vector=True
        elif name=='orthographic': camera.data.type='ORTHO'
        elif name=='multiview': scene.render.use_multiview=True
        elif name in ('adaptive-subdivision','adaptive-dicing-camera'):
            obj.modifiers.new('adaptive','SUBSURF').use_adaptive_subdivision=True
            if name=='adaptive-dicing-camera':
                camera.data.tilt_shift_enabled=False
                dicing=bpy.data.objects.new('physical-dicing-camera',camera.data.copy())
                dicing.data.tilt_shift_enabled=True
                scene.collection.objects.link(dicing)
                scene.cycles.dicing_camera=dicing
        try:
            bpy.ops.render.render()
        except RuntimeError as error:
            if expected not in str(error): raise
            results.append(dict(name=name,rejected=True,error=str(error)))
        else:
            raise RuntimeError('Unsupported configuration rendered silently: '+name)
    return results


def persistence(folder, upstream_file=None, write_upstream=False):
    if write_upstream:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.object.camera_add()
        data=bpy.context.object.data
        data.lens=42
        data.shift_x,data.shift_y=.13,-.09
        data.sensor_fit='VERTICAL'
        data.dof.focus_distance=2.5
        path=folder/'upstream-camera.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        return dict(name='upstream-file',path=str(path),native_feature_present='tilt_shift_enabled' in data.bl_rna.properties)
    if upstream_file:
        bpy.ops.wm.open_mainfile(filepath=str(upstream_file.resolve()))
        data=next(iter(bpy.data.cameras))
        assert_close(data.lens,42,1e-6,'old lens')
        assert_close(data.shift_x,.13,1e-6,'old shift X')
        assert_close(data.shift_y,-.09,1e-6,'old shift Y')
        if data.sensor_fit!='VERTICAL': raise RuntimeError('old sensor fit changed')
    else:
        _,camera,_=setup(1)
        data=camera.data
        data.tilt_shift_enabled=False
    if data.tilt_shift_enabled or any(getattr(data,name)!=0 for name in (
            'tilt_shift_tilt','tilt_shift_swing','tilt_shift_axis_rotation','tilt_shift_image_circle_diameter')):
        raise RuntimeError('Disabled-safe native defaults/migration failed')
    expected=dict(tilt_shift_enabled=True,tilt_shift_tilt=.123,tilt_shift_swing=-.045,
                  tilt_shift_axis_rotation=.27,tilt_shift_image_circle_diameter=47.5)
    for name,value in expected.items(): setattr(data,name,value)
    path=folder/'native-camera.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    bpy.ops.wm.open_mainfile(filepath=str(path))
    data=next(iter(bpy.data.cameras))
    for name,value in expected.items():
        assert_close(float(getattr(data,name)),float(value),1e-6,'roundtrip '+name)
    return dict(name='native-persistence',disabled_defaults=True,
                old_file_migration=bool(upstream_file),roundtrip=expected,path=str(path))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',choices=['all','centroid','coc','tilted','guards','projection','coverage','volume-clips','persistence','write-upstream'],default='all')
    parser.add_argument('--upstream-file',type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    folder=args.output.resolve()
    if not folder.is_relative_to(ROOT/'work'):
        raise ValueError('Validation artifacts must be below ignored work/')
    folder.mkdir(parents=True,exist_ok=True)
    # Capture provenance before work. A later install or patch export must not
    # label an already mapped process with the hash of a different artifact.
    provenance_paths=dict(binary_sha256=Path(bpy.app.binary_path),
                          fixture_script_sha256=Path(__file__))
    patch=ROOT/'patches/blender-v5.3.0-tilt-shift.patch'
    if patch.exists(): provenance_paths['patch_sha256']=patch
    provenance={key:hashlib.sha256(path.read_bytes()).hexdigest()
                for key,path in provenance_paths.items()}
    results=[]
    if args.case in ('all','persistence','write-upstream'):
        results.append(persistence(folder,args.upstream_file,args.case=='write-upstream'))
    if args.case in ('all','centroid'):
        results.extend([centroid_case(folder,'disabled-centroid',False),
                        centroid_case(folder,'physical-centroid'),
                        centroid_case(folder,'physical-shift',shift=(.12,-.08)),
                        centroid_case(folder,'vertical-fit',shift=(.08,.06),fit='VERTICAL'),
                        centroid_case(folder,'pixel-aspect',shift=(.08,-.03),fit='AUTO',pixel_aspect=(1,2)),
                        centroid_case(folder,'offaxis-focus-object',shift=(.08,-.03),dof=True,focus_object=True)])
    if args.case in ('all','coc'): results.append(coc_case(folder))
    if args.case in ('all','tilted'): results.append(tilted_focus_case(folder))
    if args.case in ('all','projection'): results.append(projection_case(folder))
    if args.case in ('all','coverage'): results.extend(coverage_case(folder))
    if args.case in ('all','volume-clips'): results.extend(volume_and_clip_cases(folder))
    if args.case in ('all','guards'): results.extend(rejection_cases(folder))
    for key,path in provenance_paths.items():
        if hashlib.sha256(path.read_bytes()).hexdigest()!=provenance[key]:
            raise RuntimeError('Validation input changed during run: '+str(path))
    summary=dict(source_pin=PIN, blender=str(bpy.app.binary_path),
                 **provenance, results=results)
    (folder/(args.case+'-results.json')).write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
