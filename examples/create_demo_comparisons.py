# SPDX-License-Identifier: GPL-3.0-or-later
"""Build/render editable native-camera demonstrations; run in patched Blender.

All generated scenes, renders and manifests stay below ignored work/. No image
effects, external assets, load handlers or source modifications are involved.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    'table-native': ('table', 'native', {}),
    'table-ordinary-best': ('table', 'ordinary', {}),
    'table-ordinary-f16': ('table', 'ordinary', {'fstop': 16}),
    'table-native-f16': ('table', 'native', {'fstop': 16}),
    'table-native-zero': ('table', 'native', {'tilt': 0}),
    'swing-native': ('swing', 'native', {}),
    'swing-ordinary-best': ('swing', 'ordinary', {}),
    'axis-native': ('axis', 'native', {}),
    'axis-ordinary-best': ('axis', 'ordinary', {}),
    'city-native': ('city', 'native', {}),
    'city-ordinary-best': ('city', 'ordinary', {}),
    'city-ordinary-blur-fit': ('city', 'ordinary', {'blur_fit': True}),
    'city-native-object': ('city', 'native', {'object_focus': True}),
    'shift-x-native': ('shift-x', 'native', {}),
    'shift-x-ordinary': ('shift-x', 'ordinary', {}),
    'shift-y-native': ('shift-y', 'native', {}),
    'shift-y-ordinary': ('shift-y', 'ordinary', {}),
    'bokeh-hexagon': ('table', 'native', {'blades': 6}),
    'bokeh-rotated': ('table', 'native', {'blades': 6, 'rotation': 30}),
    'bokeh-anamorphic': ('table', 'native', {'blades': 6, 'ratio': 2}),
    'circle-unbounded': ('table', 'native', {'circle': 0, 'shift_x': .24}),
    'circle-finite': ('table', 'native', {'circle': 33, 'shift_x': .24}),
}

# Historical aperture/coverage fixtures remain available only by explicit --case.
LEGACY_CASES = frozenset(('bokeh-hexagon', 'bokeh-rotated', 'bokeh-anamorphic',
                          'circle-unbounded', 'circle-finite'))
ACTIVE_CASES = tuple(name for name in CASES if name not in LEGACY_CASES)


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def material(name, color, rough=.45, metallic=0, emission=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    node = mat.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value = (*color, 1)
    node.inputs['Roughness'].default_value = rough
    node.inputs['Metallic'].default_value = metallic
    node.inputs['Emission Color'].default_value = (*color, 1)
    node.inputs['Emission Strength'].default_value = emission
    return mat


def herbarium_grid_material():
    """Printed ink in sheet-local XY metres; no displacement or optical changes.

    cube() applies scale, so Object coordinates are physical metres. Translation
    and rotation carry the print with the sheet; subsequent scaling scales print.
    Lines are centred on local coordinate multiples, with no UV/world dependency.
    """
    mat = material('Herbarium printed grid / 5 mm', (.78, .72, .60), .8)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    coordinates = nodes.new('ShaderNodeTexCoord')
    axes = nodes.new('ShaderNodeSeparateXYZ')
    links.new(coordinates.outputs['Object'], axes.inputs[0])

    def grid(spacing, width, label):
        lines = []
        for axis in ('X', 'Y'):
            distance = nodes.new('ShaderNodeMath')
            distance.operation, distance.label = 'PINGPONG', f'{label} {axis} / metres'
            distance.inputs[1].default_value = spacing / 2
            links.new(axes.outputs[axis], distance.inputs[0])
            ink = nodes.new('ShaderNodeMath')
            ink.operation = 'LESS_THAN'
            ink.inputs[1].default_value = width / 2
            links.new(distance.outputs[0], ink.inputs[0])
            lines.append(ink)
        union = nodes.new('ShaderNodeMath')
        union.operation, union.label = 'MAXIMUM', label
        for index, line_mask in enumerate(lines):
            links.new(line_mask.outputs[0], union.inputs[index])
        return union.outputs[0]

    minor = nodes.new('ShaderNodeMixRGB')
    minor.label = '5 mm grid / 0.25 mm printed line'
    minor.inputs[1].default_value = (.78, .72, .60, 1)
    minor.inputs[2].default_value = (.43, .48, .37, 1)
    links.new(grid(.005, .00025, 'Minor grid'), minor.inputs[0])
    major = nodes.new('ShaderNodeMixRGB')
    major.label = '25 mm grid / 0.40 mm printed line'
    links.new(minor.outputs[0], major.inputs[1])
    major.inputs[2].default_value = (.25, .34, .25, 1)
    links.new(grid(.025, .00040, 'Major grid'), major.inputs[0])
    links.new(major.outputs[0], nodes.get('Principled BSDF').inputs['Base Color'])
    return mat


def cube(name, position, scale, mat, bevel=.001):
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    obj = bpy.context.object
    obj.name, obj.scale = name, scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new('Soft crafted edges', 'BEVEL')
        mod.width, mod.segments = bevel, 3
        obj.modifiers.new('Weighted surface normals', 'WEIGHTED_NORMAL')
    obj.data.materials.append(mat)
    return obj


def sphere(name, position, scale, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, location=position)
    obj = bpy.context.object
    obj.name, obj.scale = name, scale
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def cylinder(name, position, radius, depth, mat, vertices=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=position)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    mod = obj.modifiers.new('Rounded rim', 'BEVEL')
    mod.width, mod.segments = min(.0007, depth*.15), 3
    obj.modifiers.new('Weighted surface normals', 'WEIGHTED_NORMAL')
    return obj


def line(name, start, end, radius, mat):
    start, end = Vector(start), Vector(end)
    obj = cylinder(name, (start+end)*.5, radius, (end-start).length, mat, 12)
    obj.rotation_euler = (end-start).to_track_quat('Z', 'Y').to_euler()
    return obj


def text(body, position, size, mat, rotation=(0, 0, 0), align='CENTER'):
    data = bpy.data.curves.new(body, 'FONT')
    data.body, data.size, data.align_x = body, size, align
    data.extrude = .000015
    data.materials.append(mat)
    obj = bpy.data.objects.new(body, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location, obj.rotation_euler = position, rotation
    return obj


def look_at(obj, target):
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z', 'Y').to_euler()


def light(name, position, target, power, size, color):
    data = bpy.data.lights.new(name, 'AREA')
    data.energy, data.shape, data.size, data.color = power, 'DISK', size, color
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = position
    look_at(obj, target)


def botanical_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = 'HERBARIUM / morning study'
    ivory = material('Warm cotton paper', (.78, .72, .60), .8)
    ink = material('Deep botanical ink', (.025, .065, .048), .8)
    green = material('Sage leaf', (.16, .28, .115), .62)
    darkgreen = material('Rosemary', (.06, .14, .075), .6)
    wood = material('Honey oak', (.31, .17, .075), .56)
    clay = material('Unglazed terracotta', (.38, .13, .065), .8)
    brass = material('Satin brass', (.55, .31, .10), .29, .72)
    cream = material('Petal cream', (.93, .79, .46), .55)
    amber = material('Amber ceramic', (.24, .072, .022), .22)
    charcoal = material('Bottle cap', (.025, .035, .028), .38)
    cube('Oak workbench', (0, .05, -.019), (1.3, 1.5, .04), wood, .005)
    # A restrained procedural grain belongs to the native material, not postprocessing.
    nodes = wood.node_tree.nodes
    tex = nodes.new('ShaderNodeTexNoise')
    tex.inputs['Scale'].default_value = 95
    tex.inputs['Detail'].default_value = 2
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .15
    bump.inputs['Distance'].default_value = .0003
    wood.node_tree.links.new(tex.outputs['Fac'], bump.inputs['Height'])
    wood.node_tree.links.new(bump.outputs['Normal'], nodes.get('Principled BSDF').inputs['Normal'])
    sheet = cube('Long herbarium cotton sheet', (0, .03, .002), (.30, .58, .0018), ivory)
    # Print only the original top face; carton, label and sheet sides stay plain.
    sheet.data.materials.append(herbarium_grid_material())
    for face in sheet.data.polygons:
        if face.normal.z > .99:
            face.material_index = 1
    text('HERBARIUM', (0, .253, .0031), .023, ink)
    text('FIELD NOTES  /  016', (0, .231, .0031), .006, ink)
    text('SALVIA  ·  ROSMARINUS  ·  CITRUS', (0, -.218, .0031), .005, ink)
    targets = []
    # Fine real geometry and type repeated at three depths make focus assessable.
    for index, y in enumerate((-.17, .015, .19), 1):
        x = (-.082, .075, -.07)[index-1]
        text(f'{index:02} / BOTANICAL STUDY', (x, y-.022, .0032), .004, ink)
        for j in range(17):
            line('Fine printed measurement', (x-.025+j*.003, y-.014, .0032),
                 (x-.025+j*.003, y-.009-(j % 4)*.001, .0032), .00011, ink)
        targets.append((f'Paper detail {index}', Vector((x, y-.011, .0032))))
    # Delicate pressed sprigs lie almost on the intended focus plane.
    rng = random.Random(71)
    for base_x, base_y, count, leafmat in ((-.075, -.16, 8, green), (.075, .015, 9, darkgreen), (-.07, .18, 7, green)):
        end = Vector((base_x+.025, base_y+.07, .005))
        line('Pressed botanical stem', (base_x-.016, base_y-.015, .004), end, .0006, darkgreen)
        for j in range(count):
            t = (j+1)/(count+1)
            for side in (-1, 1):
                p = Vector((base_x-.016, base_y-.015, .004)).lerp(end, t)
                p.x += side*(.008+rng.random()*.004)
                leaf = sphere('Pressed sage leaf', p, (.011, .004, .001), leafmat)
                leaf.rotation_euler.z = side*.6
                line('Leaf vein', p-Vector((.008, 0, 0)), p+Vector((.008, 0, 0)), .00013, darkgreen)
    # Product elements sit to the side, leaving the comparison's detailed paper exposed.
    cylinder('Terracotta saucer', (.153, .15, .008), .055, .012, clay)
    cylinder('Amber botanical bottle', (.152, .15, .045), .020, .067, amber)
    cylinder('Bottle shoulder', (.152, .15, .079), .013, .010, amber)
    cylinder('Bottle cap', (.152, .15, .091), .012, .018, charcoal)
    label = cube('Bottle paper label', (.152, .1296, .045), (.032, .001, .026), ivory, .0003)
    text('SAGE', (.152, .1289, .046), .006, ink, (math.pi/2, 0, 0))
    text('BOTANICAL', (.152, .1289, .037), .0028, ink, (math.pi/2, 0, 0))
    cube('Linen product carton', (-.177, .09, .035), (.052, .060, .068), ivory)
    text('FIELD', (-.177, .0595, .043), .008, ink, (math.pi/2, 0, 0))
    text('BOTANICALS', (-.177, .0595, .030), .0035, ink, (math.pi/2, 0, 0))
    # A brass loupe and small blossoms are physical geometry, with natural bokeh behind.
    bpy.ops.mesh.primitive_torus_add(major_segments=64, minor_segments=12, location=(.17, -.145, .009), major_radius=.025, minor_radius=.002)
    bpy.context.object.name = 'Brass botanist loupe'
    bpy.context.object.data.materials.append(brass)
    line('Loupe handle', (.181, -.168, .008), (.205, -.207, .008), .003, brass)
    for x, y in ((-.16, -.17), (.18, -.035), (-.16, .21)):
        for j in range(8):
            angle = j*math.tau/8
            petal = sphere('Chamomile petal', (x+.008*math.cos(angle), y+.008*math.sin(angle), .008), (.007, .003, .0017), cream)
            petal.rotation_euler.z = angle
        sphere('Chamomile heart', (x, y, .009), (.004, .004, .003), brass)
    for j in range(13):
        x = -.3+j*.05
        sphere('Warm brass glint', (x, -.10, .10+(.015 if j % 2 else 0)), (.0018, .0018, .0018), material(f'Glint {j}', (1, .62, .24), .1, .1, 12))
    light('North window / broad daylight', (-.6, -.1, 1.1), (0, 0, 0), 55, .85, (1, .91, .76))
    light('Soft sky fill', (.7, .3, .8), (0, 0, 0), 18, .9, (.76, .86, 1))
    scene.world = bpy.data.worlds.new('Quiet daylight')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.65, .74, .86, 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .18
    return targets


def camera_normal(data):
    t, s, a = data.tilt_shift_tilt, data.tilt_shift_swing, data.tilt_shift_axis_rotation
    return Vector((math.cos(a)*math.sin(s)*math.cos(t)+math.sin(a)*math.sin(t),
                   -math.sin(a)*math.sin(s)*math.cos(t)+math.cos(a)*math.sin(t), math.cos(s)*math.cos(t)))


def camera_coordinates(camera, world):
    p = camera.matrix_world.inverted() @ Vector(world)
    return Vector((p.x, p.y, -p.z))


def native_sensor_distance(camera):
    bpy.context.view_layer.update()
    evaluated = camera.evaluated_get(bpy.context.evaluated_depsgraph_get())
    result = evaluated.data.tilt_shift_guide_geometry(evaluated)
    if not result[0] or not math.isfinite(result[3]) or result[3] <= 0:
        raise ValueError('Native camera rejected optical geometry')
    return result[3]


def native_coc(camera, world, b):
    """Two-axis circular-pupil RMS diameter reference, sensor metres.

    This diagnostic intentionally excludes polygon shape/anamorphic scaling;
    those controls remain active in actual finite-aperture Cycles renders.
    """
    data = camera.data
    t, s, a = data.tilt_shift_tilt, data.tilt_shift_swing, data.tilt_shift_axis_rotation
    ex = Vector((math.cos(a)*math.cos(s), -math.sin(a)*math.cos(s), -math.sin(s)))
    ey = Vector((math.cos(a)*math.sin(s)*math.sin(t)-math.sin(a)*math.cos(t),
                 -math.sin(a)*math.sin(s)*math.sin(t)-math.cos(a)*math.cos(t), math.cos(s)*math.sin(t)))
    c = Vector((data.sensor_width*.001*data.shift_x, data.sensor_width*.001*data.shift_y, 0))
    q = camera_coordinates(camera, world)-c
    radius = data.lens*.001/(2*data.dof.aperture_fstop)
    diameters = []
    for axis in (ex, ey):
        endpoints = []
        for sign in (-1, 1):
            pupil = axis*(radius*sign)
            g = camera_normal(data).dot(q)/(data.lens*.001)-1
            sensor = pupil-((b+pupil.z)/(q.z+g*pupil.z))*(q+g*pupil)
            endpoints.append(Vector((sensor.x, sensor.y)))
        diameters.append((endpoints[0]-endpoints[1]).length)
    return math.sqrt(sum(d*d for d in diameters)/2)


def visible_surface_targets(camera, b, columns=21, rows=13):
    """Deterministic chief-ray surface grid; no empty-air blur fitting."""
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    data = camera.data
    frames = data.view_frame(scene=scene)
    z = abs(frames[0].z)
    left, right = min(v.x/z for v in frames), max(v.x/z for v in frames)
    bottom, top = min(v.y/z for v in frames), max(v.y/z for v in frames)
    scale = data.lens*.001/b
    centre = Vector((data.sensor_width*.001*data.shift_x, data.sensor_width*.001*data.shift_y, 0))
    origin = camera.matrix_world @ centre
    rotation = camera.matrix_world.to_3x3()
    result = []
    for row in range(rows):
        y = bottom+(top-bottom)*(row+.5)/rows
        for column in range(columns):
            x = left+(right-left)*(column+.5)/columns
            direction = (rotation @ Vector((x*scale, y*scale, -1))).normalized()
            hit, point, _, _, obj, _ = scene.ray_cast(depsgraph, origin, direction, distance=data.clip_end)
            if hit and not obj.hide_render:
                result.append((f'Surface grid {column:02},{row:02} / {obj.name}', point.copy()))
    if len(result) < 20:
        raise ValueError('Insufficient city surface samples for ordinary optimization')
    return result


def blur_fit(depths, diameters, lens_m, fstop_min, fstop_max):
    """Global piecewise fit of scalar sensor blur, with bounded physical pupil.

    For fixed inverse focus q, pupil is the clipped linear least-squares solution.
    Between reciprocal-depth breakpoints its numerator is a*q+c and denominator
    A*q*q-2*B*q+C. Evaluate stationary points and both pupil-bound optima as
    well as breakpoints. A finite 1e9 m focus approximates infinity in Blender.
    """
    x = [1/u for u in depths]
    targets = [d/lens_m for d in diameters]
    A, B, C = len(x), sum(x), sum(u*u for u in x)
    lower_pupil, upper_pupil = lens_m/fstop_max, lens_m/fstop_min
    # Focus closer than the nearest surface is included all the way to 1 um.
    bounds = sorted(set([1e-9, 1e6, *x]))
    candidates = set(bounds)
    for low, high in zip(bounds, bounds[1:]):
        midpoint = (low+high)/2
        a = sum(t*(1 if midpoint > u else -1) for u, t in zip(x, targets))
        c = sum(t*u*(1 if midpoint < u else -1) for u, t in zip(x, targets))
        denominator = a*B+A*c
        if abs(denominator) > 1e-30:
            value = (a*C+c*B)/denominator
            if low <= value <= high:
                candidates.add(value)
        for pupil in (lower_pupil, upper_pupil):
            value = (B+a/pupil)/A
            if low <= value <= high:
                candidates.add(value)
    best = None
    for invfocus in candidates:
        coefficients = [lens_m*abs(u-invfocus) for u in x]
        norm = sum(c*c for c in coefficients)
        pupil = sum(c*d for c, d in zip(coefficients, diameters))/norm if norm else lower_pupil
        pupil = max(lower_pupil, min(upper_pupil, pupil))
        predicted = [pupil*c for c in coefficients]
        residual = sum((p-d)**2 for p, d in zip(predicted, diameters))/len(depths)
        item = (residual, invfocus, pupil, predicted)
        if best is None or item[0] < best[0]:
            best = item
    return {'focus_m': 1/max(best[1], 1e-9), 'fstop': lens_m/best[2],
            'rms_sensor_error_m': math.sqrt(best[0]), 'predicted_sensor_diameters_m': best[3],
            'search_inverse_focus_bounds_per_m': [1e-9, 1e6],
            'fstop_bounds': [fstop_min, fstop_max],
            'bound_reason': 'Cycles effective fstop floor 1e-5; RNA hard maximum; no UI soft-minimum restriction',
            'objective': 'equal-weight squared RMS sensor blur diameter error at named landmarks; global piecewise stationary-point search'}


def build_camera(family, kind, options, targets):
    scene = bpy.context.scene
    data = bpy.data.cameras.new('Camera / editable native comparison')
    camera = bpy.data.objects.new('Camera / editable native comparison', data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    data.type, data.sensor_fit, data.sensor_width = 'PERSP', 'HORIZONTAL', 36
    data.dof.use_dof, data.dof.aperture_fstop, data.dof.aperture_blades = True, 2.8, 0
    data.clip_start, data.clip_end = .03, 2000
    data.tilt_shift_enabled = True
    data.tilt_shift_tilt = math.radians(-10)
    data.tilt_shift_image_circle_diameter = options.get('circle', 0)
    if family == 'city' or family.startswith('shift-'):
        source = bpy.data.objects.get('03 · NATIVE TILT / DOF ON')
        camera.location, camera.rotation_euler = source.location.copy(), source.rotation_euler.copy()
        data.lens, data.tilt_shift_tilt = 50, math.radians(10)
        if family.startswith('shift-'):
            camera.location = (55, -80, 5)
            look_at(camera, (0, 0, 5))
            data.lens, data.tilt_shift_tilt = 40, 0
            data.shift_x = .20 if family == 'shift-x' else 0
            data.shift_y = .18 if family == 'shift-y' else 0
        bpy.context.view_layer.update()
        # The old off-axis crossing has a negative optical-axis conjugate at
        # +10 degrees. Choose a valid axial target for honest manual/object parity.
        anchor = bpy.data.objects.new('FOCUS / axial manual-object equivalence', None)
        scene.collection.objects.link(anchor)
        anchor.location = camera.matrix_world @ Vector((0, 0, -220))
        anchor.empty_display_size = 1
        anchor.hide_render = True
        data.dof.focus_object = anchor
    else:
        data.lens = 90
        elevation = math.radians(20)
        distance = .09/(math.tan(elevation)*math.sin(math.radians(10)))
        camera.location = (0, -distance*math.cos(elevation), .0032+distance*math.sin(elevation))
        look_at(camera, (0, 0, .0032))
        data.dof.focus_distance = distance
        if family == 'swing':
            data.tilt_shift_tilt, data.tilt_shift_swing = 0, math.radians(10)
        elif family == 'axis':
            data.tilt_shift_axis_rotation = math.radians(45)
        elif family.startswith('shift-'):
            data.tilt_shift_tilt = 0
            if family == 'shift-x':
                data.shift_x = .2
            else:
                data.shift_y = .18
    data.tilt_shift_tilt = math.radians(options.get('tilt', math.degrees(data.tilt_shift_tilt)))
    data.shift_x = options.get('shift_x', data.shift_x)
    data.dof.aperture_blades = options.get('blades', 0)
    data.dof.aperture_rotation = math.radians(options.get('rotation', 0))
    data.dof.aperture_ratio = options.get('ratio', 1)
    data.dof.aperture_fstop = options.get('fstop', data.dof.aperture_fstop)
    bpy.context.view_layer.update()
    b = native_sensor_distance(camera)
    f, native_n = data.lens*.001, data.dof.aperture_fstop
    # Manual and object city files share exactly the same conjugate distance.
    manual_distance = f/(camera_normal(data).z-f/b)
    if (family == 'city' or family.startswith('shift-')) and not options.get('object_focus'):
        data.dof.focus_object = None
        data.dof.focus_distance = manual_distance
        b = native_sensor_distance(camera)
    native_data = {'lens_mm': f*1000, 'fstop': native_n, 'sensor_distance_m': b,
                   'manual_conjugate_focus_m': manual_distance, 'normal_cycles': list(camera_normal(data))}
    if family == 'city' or family.startswith('shift-'):
        targets = visible_surface_targets(camera, b)
    depths = [camera_coordinates(camera, p).z for _, p in targets]
    native_diameters = [native_coc(camera, p, b) for _, p in targets]
    optimization = {'objective': 'minimize maximum absolute inverse-depth error at named detail targets',
                    'focus_m': 2*min(depths)*max(depths)/(min(depths)+max(depths))}
    shift = Vector((data.sensor_width*.001*data.shift_x, data.sensor_width*.001*data.shift_y, 0))
    if kind == 'ordinary':
        # Chief-ray field of view matches the tilted sensor distance; translating
        # ordinary lens origin reproduces native shift's actual optical centre.
        camera.location += camera.rotation_euler.to_matrix() @ shift
        data.lens = b*1000
        data.dof.focus_object = None
        data.dof.focus_distance = optimization['focus_m']
        data.dof.aperture_fstop = native_n*b/f
        if family.startswith('shift-'):
            data.dof.focus_distance = manual_distance
            optimization = {'objective': 'match native zero-angle axial sharp plane and physical pupil', 'focus_m': manual_distance}
        if options.get('blur_fit'):
            prop = data.dof.bl_rna.properties['aperture_fstop']
            optimization = blur_fit(depths, native_diameters, b, 1e-5, prop.hard_max)
            data.dof.focus_distance, data.dof.aperture_fstop = optimization['focus_m'], optimization['fstop']
        data.tilt_shift_enabled = False
    if 'fstop' in options:
        data.dof.aperture_fstop = options['fstop']*(b/f if kind == 'ordinary' else 1)
    bpy.context.view_layer.update()
    ordinary_pupil = data.lens*.001/data.dof.aperture_fstop
    predicted = [ordinary_pupil*b*abs(1/u-1/data.dof.focus_distance) for u in depths]
    return {'native_reference': native_data, 'ordinary_optimization': optimization if kind == 'ordinary' else None,
            'landmarks': [{'name': name, 'world_m': list(point), 'camera_depth_m': depth,
                           'native_reference_rms_sensor_blur_diameter_m': diameter,
                           'ordinary_rms_sensor_blur_diameter_m': prediction if kind == 'ordinary' else None}
                          for (name, point), depth, diameter, prediction in zip(targets, depths, native_diameters, predicted)],
            'shift_optical_centre_camera_m': list(shift)}


def gallery(output, focus_overlays=False):
    """Refresh the shared gallery; optionally regenerate geometric guides only."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    if focus_overlays:
        import demo_focus_overlays as guides
        guides.generate(output)
    from build_demo_gallery import build_gallery
    return build_gallery(photos=output)


def settings(scene, args):
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = args.samples
    scene.cycles.seed = 71
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.use_denoising = False
    scene.cycles.max_bounces, scene.cycles.diffuse_bounces = 8, 4
    scene.render.resolution_x, scene.render.resolution_y = args.resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '16'
    scene.render.film_transparent = False
    scene.render.use_motion_blur = False
    scene.render.use_compositing = False
    scene.render.use_sequencer = False
    scene.use_nodes = False
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.render.threads_mode, scene.render.threads = 'FIXED', args.threads
    scene.unit_settings.system, scene.unit_settings.scale_length = 'METRIC', 1


def backend(scene, requested):
    import _cycles
    if requested == 'CPU':
        scene.cycles.device = 'CPU'
        _cycles.set_device_override('CPU')
        return ['CPU']
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = requested
    prefs.use_hiprt = False
    prefs.get_devices()
    found = []
    for device in prefs.devices:
        device.use = device.type == requested
        if device.use:
            found.append(device.name)
    if len(found) != 1:
        raise RuntimeError(f'Expected exactly one {requested} device, found {found}; refusing mixed/fallback execution')
    _cycles.set_device_override(requested)
    scene.cycles.device = 'GPU'
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', action='append', choices=['all', *CASES], default=[])
    parser.add_argument('--output', type=Path, default=ROOT/'work/demo-comparisons')
    parser.add_argument('--resolution', nargs=2, type=int, default=[3840, 2160], metavar=('WIDTH', 'HEIGHT'))
    parser.add_argument('--samples', type=int, default=256)
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--backend', choices=['CPU', 'HIP'], default='HIP')
    parser.add_argument('--save-only', action='store_true')
    parser.add_argument('--gallery-only', action='store_true',
                        help='Refresh the unified gallery from existing manifests; do not save scenes or render.')
    parser.add_argument('--focus-overlays', action='store_true',
                        help='Read saved scenes and regenerate optional optical guides; requires --gallery-only. No rendering or saving.')
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if args.focus_overlays and not args.gallery_only:
        parser.error('--focus-overlays requires --gallery-only')
    if args.list:
        print('\n'.join(CASES))
        return
    output = args.output.resolve()
    if not output.is_relative_to((ROOT/'work').resolve()):
        raise ValueError('Generated artifacts must remain below ignored work/')
    if min(args.resolution) < 1 or args.samples < 1:
        raise ValueError('Resolution and samples must be positive')
    output.mkdir(parents=True, exist_ok=True)
    if args.gallery_only:
        gallery_path = gallery(output, focus_overlays=args.focus_overlays)
        print('DEMO_GALLERY_COMPLETE', str(gallery_path), flush=True)
        return
    provenance = {
        'generator_sha256': file_hash(__file__),
        'blender_binary_path': bpy.app.binary_path,
        'blender_binary_sha256': file_hash(bpy.app.binary_path),
        'cumulative_patch_path': 'patches/blender-v5.3.0-tilt-shift-m4.patch',
        'cumulative_patch_sha256': file_hash(ROOT/'patches/blender-v5.3.0-tilt-shift-m4.patch'),
        'city_source_path': 'examples/full-scale-city/full-scale-city.blend',
        'city_source_sha256': file_hash(ROOT/'examples/full-scale-city/full-scale-city.blend'),
        'source_revision': json.loads((ROOT/'docs/source-revision.json').read_text()),
    }
    selected = list(ACTIVE_CASES) if not args.case or 'all' in args.case else list(dict.fromkeys(args.case))
    for name in selected:
        started = time.monotonic()
        family, kind, options = CASES[name]
        if family == 'city' or family.startswith('shift-'):
            bpy.ops.wm.open_mainfile(filepath=str(ROOT/'examples/full-scale-city/full-scale-city.blend'))
            scene = bpy.context.scene
            scene.frame_set(40)
            targets = [('Central crossing', (.75, -6, 1.75)),
                       ('Near avenue', (0, -25, 1.5)), ('Far avenue', (0, 25, 1.5)),
                       ('West district', (-25, 0, 6)), ('East district', (25, 0, 6)),
                       ('North roof', (0, 17, 13)), ('South roof', (0, -17, 13))]
            targets = [(label, Vector(point)) for label, point in targets]
        else:
            targets = botanical_scene()
            scene = bpy.context.scene
        settings(scene, args)
        optics = build_camera(family, kind, options, targets)
        camera, data = scene.camera, scene.camera.data
        blend_path, image_path = output/f'{name}.blend', output/f'{name}.png'
        scene.render.filepath = '//'+image_path.name
        data.tilt_shift_show_focus_plane = data.tilt_shift_show_lens_plane = True
        data.tilt_shift_show_image_circle = True
        for obj in scene.objects:
            obj.select_set(False)
        camera.select_set(True)
        bpy.context.view_layer.objects.active = camera
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    area.spaces.active.region_3d.view_perspective = 'CAMERA'
        note = bpy.data.texts.new('START HERE / '+name)
        note.write('Native Cycles optical comparison. F12 renders this variant.\n'
                   'Original files: GPL-3.0-or-later. Units metres, camera -Z forward / +Y up.\n'
                   'Native lens frame: Rz(axis) Ry(swing) Rx(tilt), radians, reference Y-down then reflected.\n'
                   'Images use finite-aperture native rays; no compositor. Ordinary comparisons use DOF.\n'
                   'Shift, aperture shape and anamorphic ratio also exist in ordinary Cycles.\n'
                   'Stopped down comparisons do not simulate diffraction or exposure penalties.\n'
                   'See the adjacent JSON manifest for target depths and ordinary optimization.\n')
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), check_existing=False)
        record = {'case': name, 'family': family, 'kind': kind, 'options': options,
                  'generator': 'examples/create_demo_comparisons.py', 'source_sha256': provenance['generator_sha256'],
                  'provenance': provenance, 'blend_sha256': file_hash(blend_path),
                  'blender': bpy.app.version_string, 'blender_build_hash': bpy.app.build_hash.decode(),
                  'scene': str(blend_path), 'image': str(image_path), 'saved_device': 'CPU',
                  'resolution': list(args.resolution), 'samples': args.samples, 'seed': 71,
                  'denoising': False, 'adaptive_sampling': False, 'compositor': False, 'motion_blur': False,
                  'native_enabled': data.tilt_shift_enabled, 'dof_enabled': data.dof.use_dof,
                  'camera': {'position_m': list(camera.location), 'rotation_euler_xyz_rad': list(camera.rotation_euler),
                             'lens_mm': data.lens, 'sensor_width_mm': data.sensor_width,
                             'focus_distance_m': data.dof.focus_distance,
                             'focus_object': data.dof.focus_object.name if data.dof.focus_object else None,
                             'fstop': data.dof.aperture_fstop, 'pupil_diameter_m': data.lens*.001/data.dof.aperture_fstop,
                             'tilt_deg': math.degrees(data.tilt_shift_tilt), 'swing_deg': math.degrees(data.tilt_shift_swing),
                             'axis_deg': math.degrees(data.tilt_shift_axis_rotation), 'shift': [data.shift_x, data.shift_y],
                             'image_circle_mm': data.tilt_shift_image_circle_diameter,
                             'blades': data.dof.aperture_blades, 'aperture_rotation_deg': math.degrees(data.dof.aperture_rotation),
                             'aperture_ratio': data.dof.aperture_ratio}, **optics,
                  'limitations': ['Thin-lens geometric optics; no diffraction/exposure penalty at f/16',
                                  'Blur-fit uses finite named landmarks and RMS diameter, not full image equivalence',
                                  'Ordinary Cycles supports shift and aperture shape; these demonstrate parity controls']}
        if not args.save_only:
            record['render_backend'], record['render_devices'] = args.backend, backend(scene, args.backend)
            scene.render.filepath = str(image_path)
            bpy.ops.render.render(write_still=True)
            record['image_sha256'] = hashlib.sha256(image_path.read_bytes()).hexdigest()
        record['elapsed_s'] = time.monotonic()-started
        (output/f'{name}.json').write_text(json.dumps(record, indent=2)+'\n')
        gallery(output)
        print('DEMO_COMPLETE', name, json.dumps({'elapsed_s': record['elapsed_s'], 'image': str(image_path)}), flush=True)


if __name__ == '__main__':
    main()
