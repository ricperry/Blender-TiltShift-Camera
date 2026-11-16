# SPDX-License-Identifier: GPL-3.0-or-later
"""Build Little Meridian, a self-contained native-Cycles tilt-shift playground.

Run with the project's patched Blender, not system Blender. Generation saves the
file and a JSON inventory; it does not render or install handlers. All generated
artifacts must live in ignored work/. See CITY.md for commands and camera notes.
"""
import argparse
import json
import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
RNG = random.Random(71)
MATERIALS = {}
MESHES = {}
COLLECTIONS = {}
ACTIVE_COLLECTION = None


def material(name, color, roughness=.65, metallic=0, emission=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Emission Color'].default_value = (*color, 1)
    bsdf.inputs['Emission Strength'].default_value = emission
    MATERIALS[name] = mat
    return mat


def collection(name):
    global ACTIVE_COLLECTION
    if name not in COLLECTIONS:
        child = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(child)
        COLLECTIONS[name] = child
    ACTIVE_COLLECTION = COLLECTIONS[name]
    return ACTIVE_COLLECTION


def primitive_mesh(kind, mat):
    key = kind, mat.name
    if key in MESHES:
        return MESHES[key]
    # Once per primitive/material: subsequent objects share the same mesh.
    if kind in ('box', 'softbox'):
        bpy.ops.mesh.primitive_cube_add(size=1)
        if kind == 'softbox':
            modifier = bpy.context.object.modifiers.new('Tiny rounded corners', 'BEVEL')
            modifier.width, modifier.segments = .06, 2
            bpy.ops.object.modifier_apply(modifier=modifier.name)
    elif kind == 'cylinder':
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=1, depth=1)
    elif kind == 'cone':
        bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=1, radius2=0, depth=1)
    elif kind == 'leaf':
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1)
    elif kind == 'sphere':
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, radius=1)
    else:
        raise ValueError(kind)
    source = bpy.context.object
    mesh = source.data
    mesh.name = f'{kind} / {mat.name} / shared'
    mesh.materials.append(mat)
    bpy.data.objects.remove(source, do_unlink=True)
    MESHES[key] = mesh
    return mesh


def shape(name, kind, xyz, scale, mat, rotation=None, parent=None):
    obj = bpy.data.objects.new(name, primitive_mesh(kind, mat))
    ACTIVE_COLLECTION.objects.link(obj)
    obj.location, obj.scale = xyz, scale
    if rotation:
        obj.rotation_euler = rotation
    if parent:
        obj.parent = parent
    return obj


def box(name, xyz, size, mat, **kwargs):
    return shape(name, 'box', xyz, size, mat, **kwargs)


def cylinder(name, xyz, radius, depth, mat, **kwargs):
    return shape(name, 'cylinder', xyz, (radius, radius, depth), mat, **kwargs)


def empty(name, xyz=(0, 0, 0)):
    obj = bpy.data.objects.new(name, None)
    ACTIVE_COLLECTION.objects.link(obj)
    obj.location = xyz
    obj.empty_display_size = .025
    return obj


def text(name, body, xyz, size, mat, rotation=(0, 0, 0)):
    data = bpy.data.curves.new(name, 'FONT')
    data.body, data.size, data.align_x = body, size, 'CENTER'
    data.extrude = .00025
    data.materials.append(mat)
    obj = bpy.data.objects.new(name, data)
    ACTIVE_COLLECTION.objects.link(obj)
    obj.location, obj.rotation_euler = xyz, rotation
    return obj


def line(name, a, b, radius, mat, parent=None):
    a, b = Vector(a), Vector(b)
    obj = cylinder(name, (a+b)/2, radius, (b-a).length, mat, parent=parent)
    obj.rotation_euler = (b-a).to_track_quat('Z', 'Y').to_euler()
    return obj


def tree(x, y, size=1, name='Street tree'):
    h = .065*size
    cylinder(name+' trunk', (x, y, .016+h*.42), .003*size, h*.84, MATERIALS['bark'])
    for dx, dy, dz, scale in ((0, 0, 1, 1), (-.012, .002, .8, .75), (.01, -.007, .85, .8)):
        shape(name+' canopy', 'leaf', (x+dx*size, y+dy*size, .018+h*dz),
              (.026*size*scale, .023*size*scale, .028*size*scale),
              MATERIALS[RNG.choice(('sage', 'leaf', 'leaf', 'olive'))])


def bench(x, y, angle=0):
    root = empty('Bench', (x, y, .016))
    root.rotation_euler.z = angle
    for dy in (-.004, .004):
        box('Bench / cedar slat', (0, dy, .009), (.038, .005, .003), MATERIALS['cedar'], parent=root)
    box('Bench / back', (0, .007, .018), (.038, .003, .011), MATERIALS['cedar'], parent=root)
    for dx in (-.013, .013):
        box('Bench / foot', (dx, 0, .004), (.003, .011, .008), MATERIALS['iron'], parent=root)


def building(name, x, y, width, depth, height, color, floors, roof='garden'):
    base = .018
    box(name, (x, y, base+height/2), (width, depth, height), MATERIALS[color])
    box(name+' / foundation', (x, y, base+.008), (width+.005, depth+.005, .016), MATERIALS['cream'])
    box(name+' / cornice', (x, y, base+height-.004), (width+.008, depth+.008, .012), MATERIALS['cream'])
    box(name+' / roof', (x, y, base+height+.003), (width*.93, depth*.93, .007), MATERIALS['roof'])
    # Deep, dark blue panes surrounded by the warm facade, visible on two faces.
    cols = max(2, round(width/.043))
    rows = max(1, floors)
    for row in range(rows):
        z = base+.033+row*(height-.044)/rows
        for col in range(cols):
            wx = x+(col-(cols-1)/2)*(width/(cols+.5))
            box(name+' / south window', (wx, y-depth/2-.0007, z),
                (width/(cols+1)*.52, .0018, min(.023, height/(rows+1)*.48)), MATERIALS['glass'])
        for col in range(2):
            wy = y+(col-.5)*depth*.41
            box(name+' / east window', (x+width/2+.0007, wy, z),
                (.0018, depth*.21, min(.023, height/(rows+1)*.48)), MATERIALS['glass'])
    if height < .25:
        for col in range(cols):
            wx = x+(col-(cols-1)/2)*(width/(cols+.5))
            box(name+' / shopfront', (wx, y-depth/2-.001, base+.016),
                (width/(cols+1)*.67, .002, .026), MATERIALS['glass'])
        box(name+' / storefront awning', (x, y-depth/2-.010, base+.034),
            (width*.95, .023, .004), MATERIALS['awning'])
    if roof == 'garden':
        box(name+' / roof garden', (x-width*.19, y, base+height+.009),
            (width*.39, depth*.69, .007), MATERIALS['sage'])
        for dx, dy in ((-.2, -.22), (-.2, .22)):
            cylinder(name+' / roof planter', (x+width*dx, y+depth*dy, base+height+.016),
                     .009, .014, MATERIALS['terracotta'])
            shape(name+' / roof shrub', 'leaf', (x+width*dx, y+depth*dy, base+height+.03),
                  (.013, .013, .018), MATERIALS['leaf'])
        box(name+' / skylight', (x+width*.22, y, base+height+.012),
            (width*.23, depth*.42, .013), MATERIALS['glass'])
    elif roof == 'water':
        for dx in (-.019, .019):
            for dy in (-.019, .019):
                box(name+' / tank support', (x+dx, y+dy, base+height+.023), (.004, .004, .044), MATERIALS['iron'])
        cylinder(name+' / water tank', (x, y, base+height+.064), .035, .045, MATERIALS['cedar'])
        for z in (.049, .078):
            cylinder(name+' / tank band', (x, y, base+height+z), .0357, .0025, MATERIALS['iron'])
        shape(name+' / tank cap', 'cone', (x, y, base+height+.097), (.039, .039, .022), MATERIALS['roof'])
    else:
        box(name+' / rooftop service room', (x, y, base+height+.018),
            (width*.39, depth*.38, .03), MATERIALS[color])


def city_base():
    collection('01 · Tabletop and waterfront')
    box('Little Meridian / floating maple plinth', (0, 0, -.032), (1.64, 1.34, .064), MATERIALS['cedar'])
    box('Little Meridian / stone edge', (0, 0, .004), (1.62, 1.32, .014), MATERIALS['paving'])
    box('Studio surface', (0, 0, -.082), (200, 200, .035), MATERIALS['background'])
    box('Canal / quiet turquoise water', (0, -.544, .009), (1.59, .155, .012), MATERIALS['water'])
    for y in (-.632, -.459):
        box('Canal / limestone quay', (0, y, .022), (1.6, .021, .028), MATERIALS['cream'])
    for i in range(36):
        x, y = RNG.uniform(-.77, .77), RNG.uniform(-.604, -.484)
        box('Canal / painted ripple', (x, y, .0153), (RNG.uniform(.008, .035), .0009, .0005), MATERIALS['foam'])
    for x in (-.32, .28):
        box('Canal / pedestrian bridge deck', (x, -.545, .038), (.071, .21, .012), MATERIALS['paving'])
        for dx in (-.038, .038):
            box('Bridge / rail', (x+dx, -.545, .065), (.003, .206, .003), MATERIALS['iron'])
            for y in (-.63, -.585, -.54, -.495, -.45):
                box('Bridge / baluster', (x+dx, y, .052), (.002, .002, .026), MATERIALS['iron'])
    # A little launch and striped canopy: intentionally simple solid geometry.
    boat = empty('Canal launch', (.49, -.548, .025))
    shape('Launch / hull', 'softbox', (0, 0, 0), (.115, .046, .023), MATERIALS['navy'], parent=boat)
    shape('Launch / white cabin', 'softbox', (-.007, 0, .019), (.062, .035, .022), MATERIALS['cream'], parent=boat)
    box('Launch / roof', (-.006, 0, .034), (.073, .043, .004), MATERIALS['coral'], parent=boat)
    for x in (-.02, 0, .02):
        box('Launch / windows', (x, -.018, .02), (.013, .002, .013), MATERIALS['glass'], parent=boat)
    text('Plinth / name', 'L I T T L E   M E R I D I A N', (0, -.673, -.028), .025,
         MATERIALS['cream'], (math.pi/2, 0, 0))


def streets():
    collection('02 · Streets and pedestrian crossings')
    for x in (-.32, .28):
        box('North–south avenue', (x, .075, .012), (.104, 1.03, .008), MATERIALS['asphalt'])
    for y in (-.19, .26):
        box('East–west avenue', (0, y, .0121), (1.59, .104, .008), MATERIALS['asphalt'])
    for y in (-.19, .26):
        for i in range(28):
            x = -.77+i*.057
            if min(abs(x+.32), abs(x-.28)) > .072:
                box('Lane marking / warm white dash', (x, y, .0166), (.026, .0016, .0007), MATERIALS['line'])
        for x in (-.32, .28):
            for sign in (-1, 1):
                for j in range(7):
                    box('Zebra crossing / horizontal', (x+(j-3)*.011, y+sign*.064, .0168),
                        (.0054, .024, .0007), MATERIALS['line'])
                    box('Zebra crossing / vertical', (x+sign*.064, y+(j-3)*.011, .0168),
                        (.024, .0054, .0007), MATERIALS['line'])
    for x in (-.32, .28):
        for i in range(18):
            y = -.40+i*.055
            if min(abs(y+.19), abs(y-.26)) > .079:
                box('Lane marking / avenue dash', (x, y, .0166), (.0016, .025, .0007), MATERIALS['line'])
    # Raised park squares and waterfront promenade.
    box('Meridian Square / pale stone plaza', (-.01, .034, .017), (.43, .28, .014), MATERIALS['cream'])
    box('Pocket park / lawn', (.55, .42, .019), (.36, .22, .012), MATERIALS['sage'])
    box('Pocket park / walking path', (.55, .42, .026), (.025, .22, .003), MATERIALS['paving'])
    box('Promenade', (0, -.419, .018), (1.6, .044, .013), MATERIALS['paving'])


def architecture():
    collection('03 · Architecture / pastel district')
    specs = [
        ('The Pearl / corner apartments', -.66, .45, .19, .21, .255, 'cream', 5, 'garden'),
        ('Terracotta House', -.46, .45, .17, .21, .34, 'coral', 7, 'water'),
        ('Meridian Hotel', -.14, .46, .20, .23, .39, 'ochre', 8, 'service'),
        ('Mint Studios', .09, .46, .19, .23, .28, 'teal', 6, 'garden'),
        ('Old Post Office', -.66, .025, .18, .24, .20, 'ochre', 4, 'service'),
        ('Seabird Apartments', -.46, .025, .17, .24, .28, 'teal', 6, 'garden'),
        ('The Lantern / corner cafe', .49, .028, .19, .24, .24, 'coral', 5, 'garden'),
        ('Bluebird House', .69, .028, .15, .24, .31, 'cream', 6, 'water'),
        ('Canal Books', -.66, -.337, .18, .13, .112, 'teal', 2, 'garden'),
        ('The Bread Shop', -.46, -.337, .17, .13, .15, 'ochre', 3, 'service'),
        ('Coral Workshop', -.115, -.337, .21, .13, .125, 'coral', 2, 'garden'),
        ('The Glasshouse', .12, -.337, .17, .13, .17, 'cream', 3, 'garden'),
        ('Canal Corner', .49, -.337, .18, .13, .13, 'ochre', 2, 'service'),
        ('Riverside Cycles', .69, -.337, .16, .13, .10, 'teal', 2, 'garden'),
    ]
    for spec in specs:
        building(*spec)
    # Hotel crown and inset banding make a clear landmark behind the clock tower.
    box('Hotel / stepped crown', (-.14, .46, .423), (.13, .15, .035), MATERIALS['ochre'])
    box('Hotel / cream cap', (-.14, .46, .443), (.14, .16, .008), MATERIALS['cream'])
    text('Hotel / sign', 'MERIDIAN', (-.14, .338, .352), .021, MATERIALS['cream'], (math.pi/2, 0, 0))
    text('Books / sign', 'BOOKS', (-.66, -.404, .084), .019, MATERIALS['cream'], (math.pi/2, 0, 0))
    text('Cafe / sign', 'CAFE', (.49, -.094, .075), .021, MATERIALS['cream'], (math.pi/2, 0, 0))

    collection('04 · Meridian Square / clock fountain market')
    cylinder('Clock tower / octagonal podium', (-.10, .08, .032), .055, .018, MATERIALS['paving'])
    box('Clock tower / shaft', (-.10, .08, .14), (.052, .052, .205), MATERIALS['cream'])
    box('Clock tower / cornice', (-.10, .08, .245), (.072, .072, .012), MATERIALS['ochre'])
    shape('Clock tower / copper roof', 'cone', (-.10, .08, .279), (.055, .055, .06), MATERIALS['teal'])
    cylinder('Clock tower / south dial', (-.10, .0528, .216), .018, .002, MATERIALS['line'], rotation=(math.pi/2, 0, 0))
    line('Clock / minute hand', (-.10, .0508, .216), (-.10, .0508, .230), .0012, MATERIALS['iron'])
    line('Clock / hour hand', (-.10, .0504, .216), (-.090, .0504, .220), .0014, MATERIALS['iron'])
    cylinder('Fountain / stone basin', (.07, .045, .032), .047, .018, MATERIALS['paving'])
    cylinder('Fountain / turquoise pool', (.07, .045, .042), .039, .003, MATERIALS['water'])
    cylinder('Fountain / central column', (.07, .045, .061), .008, .043, MATERIALS['cream'])
    cylinder('Fountain / upper bowl', (.07, .045, .077), .023, .006, MATERIALS['cream'])
    for x in (-.16, -.05, .06, .17):
        bench(x, -.075)
    for x, y in ((-.19, .14), (.18, .14), (.18, -.02)):
        cylinder('Square / planter', (x, y, .029), .021, .02, MATERIALS['terracotta'])
        tree(x, y, .9, 'Square tree')
    for i, x in enumerate((-.17, -.055, .065, .18)):
        y = .16
        box('Market / stall counter', (x, y, .041), (.07, .034, .034), MATERIALS['cedar'])
        for dx in (-.03, .03):
            for dy in (-.015, .015):
                cylinder('Market / upright', (x+dx, y+dy, .064), .0015, .061, MATERIALS['cream'])
        for stripe in range(7):
            box('Market / striped canopy', (x+(stripe-3)*.0105, y, .097), (.0107, .055, .005),
                MATERIALS['cream' if stripe%2 else ('coral' if i%2 else 'teal')])
        for j in range(3):
            shape('Market / basket of produce', 'leaf', (x+(j-1)*.019, y-.003, .061),
                  (.008, .009, .006), MATERIALS['ochre' if j%2 else 'leaf'])


def landscape():
    collection('05 · Trees furniture and streetlights')
    for x in (-.76, -.24, .20, .77):
        for y in (-.405, -.11, .16, .58):
            if x == .20 and y == .16:
                continue
            cylinder('Street / tree planter', (x, y, .022), .022, .012, MATERIALS['terracotta'])
            tree(x, y, RNG.uniform(.8, 1.15))
    for x, y in ((.41, .35), (.42, .49), (.68, .49), (.70, .35), (.61, .54), (.48, .55)):
        tree(x, y, RNG.uniform(1.05, 1.4), 'Pocket park tree')
    for x in (-.69, -.45, -.1, .12, .49, .7):
        bench(x, -.427, math.pi)
    for x, y in ((-.25, -.10), (.205, -.10), (-.25, .17), (.205, .17), (-.75, -.425), (.75, -.425)):
        cylinder('Streetlight / post', (x, y, .068), .002, .105, MATERIALS['iron'])
        box('Streetlight / lantern', (x, y, .123), (.011, .011, .014), MATERIALS['warm lamp'])
        shape('Streetlight / roof', 'cone', (x, y, .135), (.011, .011, .008), MATERIALS['iron'])


def linear_keys(obj, path, values):
    for frame, value in values:
        setattr(obj, path, value)
        obj.keyframe_insert(data_path=path, frame=frame)
    action = obj.animation_data.action
    # Blender 5 action slots expose curves through channel bags, not action.fcurves.
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:
                        key.interpolation = 'LINEAR'


def vehicle(name, color, bus=False):
    root = empty(name)
    length, width = (.102, .035) if bus else (.066, .031)
    shape(name+' / body', 'softbox', (0, 0, .032), (length, width, .022), MATERIALS[color], parent=root)
    shape(name+' / cream cabin', 'softbox', (-.004, 0, .049),
          (length*.68, width*.87, .023 if bus else .018), MATERIALS['cream'], parent=root)
    box(name+' / windscreen', (length*.29, 0, .052), (.003, width*.76, .012), MATERIALS['glass'], parent=root)
    for side in (-1, 1):
        box(name+' / side glazing', (-.003, side*width*.445, .052),
            (length*.58, .0014, .011), MATERIALS['glass'], parent=root)
        for dx in (-length*.32, length*.32):
            cylinder(name+' / tire', (dx, side*width*.51, .023), .008, .005,
                     MATERIALS['rubber'], rotation=(math.pi/2, 0, 0), parent=root)
        box(name+' / headlights', (length*.505, side*width*.30, .034),
            (.0015, .006, .004), MATERIALS['warm lamp'], parent=root)
    return root


def person(name, xyz, color, walking=None, angle=0):
    root = empty(name, xyz)
    root.rotation_euler.z = angle
    cylinder(name+' / coat', (0, 0, .023), .0048, .016, MATERIALS[color], parent=root)
    shape(name+' / head', 'sphere', (0, 0, .036), (.0045, .0045, .0049), MATERIALS['skin'], parent=root)
    for dx in (-.0026, .0026):
        line(name+' / leg', (dx, 0, .015), (dx, .002 if dx<0 else -.002, .003), .0018, MATERIALS['navy'], parent=root)
        line(name+' / arm', (dx*2, 0, .029), (dx*2.1, -.0015, .017), .0015, MATERIALS[color], parent=root)
    if walking:
        linear_keys(root, 'location', walking)
    return root


def traffic():
    collection('06 · Animated traffic / kinematic 240 frame loop')
    # All main-road through traffic shares a deterministic traffic-signal schedule.
    # Main intersections: green 1..84 / 201..240, amber 85..92, red 93..200.
    # Each car advances up to a stop line, holds, then crosses after green.
    colors = ('coral', 'ochre', 'teal', 'navy', 'cream')
    for j, y in enumerate((-.214, .236)):
        for k, stop in enumerate((-.42, .18)):
            for follower in range(2):
                root = vehicle(f'Eastbound {j+1}.{k+1}.{follower+1}', colors[(j+k+follower)%5], bus=j==1 and k==0 and follower==0)
                start = stop-.24-follower*.105
                waiting = stop-follower*.105
                linear_keys(root, 'location', [(1, (start, y, 0)), (85, (waiting, y, 0)),
                    (200, (waiting, y, 0)), (240, (start+.60, y, 0)), (241, (start, y, 0))])
    for j, y in enumerate((-.166, .284)):
        for k, stop in enumerate((-.22, .38)):
            root = vehicle(f'Westbound {j+1}.{k+1}', colors[(j+k+2)%5])
            root.rotation_euler.z = math.pi
            start = stop+.24
            linear_keys(root, 'location', [(1, (start, y, 0)), (85, (stop, y, 0)),
                (200, (stop, y, 0)), (240, (start-.60, y, 0)), (241, (start, y, 0))])
    # Parked cars add variety without complicating the intersection schedule.
    for i, x in enumerate((-.73, -.58, -.10, .06, .60, .74)):
        obj = vehicle(f'Parked / canal street {i+1}', colors[(i+1)%5])
        obj.location = (x, -.256, 0)

    collection('07 · Traffic signals / pedestrian phase')
    for x in (-.32, .28):
        for y in (-.19, .26):
            for sign in (-1, 1):
                sx, sy = x-sign*.064, y-sign*.065
                cylinder('Signal / pole', (sx, sy, .056), .0022, .079, MATERIALS['iron'])
                box('Signal / housing', (sx, sy, .101), (.013, .012, .035), MATERIALS['iron'])
                for color, z in (('red', .111), ('amber', .101), ('green', .091)):
                    # Animated shader strength: exactly red/green states, no handlers.
                    rgb = {'red':(.85,.025,.014),'amber':(1,.34,.015),'green':(.04,.65,.19)}[color]
                    dim = tuple(channel*.04 for channel in rgb)
                    mat = material(f'Signal {x} {y} {sign} / {color}', rgb, emission=0)
                    bsdf = mat.node_tree.nodes['Principled BSDF']
                    bsdf.inputs['Base Color'].default_value = (*dim, 1)
                    node = bsdf.inputs['Emission Strength']
                    for frame in (1, 84, 85, 92, 93, 200, 201, 240):
                        on = ((color=='green' and (frame<=84 or frame>=201)) or
                              (color=='amber' and 85<=frame<=92) or
                              (color=='red' and 93<=frame<=200))
                        node.default_value = 3 if on else 0
                        node.keyframe_insert('default_value', frame=frame)
                        # Solid material-color view also shows the actual phase.
                        mat.diffuse_color = (*(rgb if on else dim), 1)
                        mat.keyframe_insert('diffuse_color', frame=frame)
                    for animated in (mat.node_tree, mat):
                        for layer in animated.animation_data.action.layers:
                            for strip in layer.strips:
                                for bag in strip.channelbags:
                                    for curve in bag.fcurves:
                                        for key in curve.keyframe_points:
                                            key.interpolation='CONSTANT'
                    cylinder('Signal / '+color, (sx, sy-.0065, z), .0033, .0018, mat, rotation=(math.pi/2, 0, 0))

    collection('08 · People and cyclists')
    for i in range(24):
        if i < 10:
            x, y = RNG.uniform(-.20, .19), RNG.uniform(-.10, .14)
        elif i < 18:
            x, y = RNG.uniform(-.75, .75), -.423
        else:
            x, y = RNG.uniform(.40, .72), RNG.uniform(.33, .53)
        person(f'Citizen {i+1:02}', (x, y, .022), colors[i%5], angle=RNG.uniform(-math.pi, math.pi))
    for i, x in enumerate((-.345, -.308, .258, .295)):
        # Cross a horizontal avenue only while traffic is stationary and red.
        start, end = (x, -.267, .018), (x, -.111, .018)
        person(f'Crossing pedestrian {i+1}', start, colors[i%5],
               [(1,start),(105,start),(184,end),(240,end),(241,start)])
    for i, x in enumerate((-.58, .12)):
        cyclist = empty(f'Cyclist {i+1}', (x, -.423, .018))
        for dx in (-.014, .014):
            # Twelve-sided wheels, open centre suggested by contrasting small hub.
            cylinder('Bicycle / wheel', (dx, 0, .011), .010, .002, MATERIALS['iron'], rotation=(math.pi/2,0,0), parent=cyclist)
            cylinder('Bicycle / hub', (dx, -.0012, .011), .0075, .0022, MATERIALS['paving'], rotation=(math.pi/2,0,0), parent=cyclist)
        line('Bicycle / frame', (-.014, 0, .011), (0, 0, .024), .0015, MATERIALS['coral'], parent=cyclist)
        line('Bicycle / frame', (0, 0, .024), (.014, 0, .011), .0015, MATERIALS['coral'], parent=cyclist)
        rider = person(f'Cyclist {i+1} / rider', (0,0,.020), 'ochre')
        rider.parent = cyclist
        linear_keys(cyclist, 'location', [(1,(x,-.423,.018)),(240,(x+.20,-.423,.018)),(241,(x,-.423,.018))])


def look_at(obj, target):
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()


def cameras():
    collection('09 · Cameras / choose in Scene properties')
    focus = empty('FOCUS · central crossing / move me to refocus', (.015, -.12, .035))
    focus.hide_render = True
    def camera(name, xyz, target, fstop, tilt=0, swing=0, native=True, lens=50):
        data = bpy.data.cameras.new(name)
        obj = bpy.data.objects.new(name, data)
        ACTIVE_COLLECTION.objects.link(obj)
        obj.location = xyz
        look_at(obj, target)
        data.type, data.lens, data.sensor_width, data.sensor_fit = 'PERSP', lens, 36, 'HORIZONTAL'
        data.clip_start, data.clip_end = .008, 1000
        data.dof.use_dof, data.dof.aperture_fstop = True, fstop
        data.dof.focus_object = focus
        data.dof.focus_distance = (Vector(target)-obj.location).length
        data.dof.aperture_blades = 7
        data.tilt_shift_enabled = native
        data.tilt_shift_tilt, data.tilt_shift_swing = math.radians(tilt), math.radians(swing)
        data.tilt_shift_axis_rotation = 0
        data.tilt_shift_image_circle_diameter = 0
        return obj
    pose, target = (2.05, -2.64, 3.0), (0, .025, -.12)
    hero = camera('01 · HERO / native tilt +1.7° / f1.4', pose, target, 1.4, 1.7)
    zero = camera('02 · COMPARE / native zero tilt / same pose f1.4', pose, target, 1.4)
    swing = camera('03 · SWING / native -1.6° / same pose f1.4', pose, target, 1.4, swing=-1.6)
    overview = camera('04 · OVERVIEW / ordinary camera / f8', pose, target, 8, native=False)
    # The body stays level: native vertical shift raises the view without aiming up.
    architecture = camera('05 · ARCHITECTURE / level body +4 mm shift', (.9,-1.35,.10), (-.1,.2,.10), 5.6, lens=60)
    architecture.data.shift_y = 4/36
    architecture['usage'] = 'Level body; canonical shift_y = 4 / 36 = +4 mm. Select then Ctrl Numpad 0.'
    street_focus = empty('FOCUS · streetlife crossing', (.28, -.19, .035))
    street_focus.hide_render = True
    street = camera('06 · STREETLIFE / native camera / 35 mm f2.8',
                    (1.10, -.19, .22), (.1, -.19, .035), 2.8, lens=35)
    street.data.dof.focus_object = street_focus
    street['usage'] = 'Low avenue view with its own focus target; try frame 145 for the pedestrian crossing.'
    for obj in (hero, zero, swing, overview):
        obj['usage'] = 'Choose as Scene Camera; F12. Hero and comparison have identical pose, focus, lens and aperture.'
    bpy.context.scene.camera = hero
    bpy.ops.object.select_all(action='DESELECT')
    hero.select_set(True)
    bpy.context.view_layer.objects.active = hero
    return hero


def lighting():
    collection('10 · Lighting / golden hour studio')
    world = bpy.data.worlds.new('Cool open sky')
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (.58, .72, .88, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = .48
    bpy.context.scene.world = world
    def area(name, xyz, target, power, size, color):
        data = bpy.data.lights.new(name, 'AREA')
        data.energy, data.shape, data.size, data.color = power, 'DISK', size, color
        obj = bpy.data.objects.new(name, data)
        ACTIVE_COLLECTION.objects.link(obj)
        obj.location = xyz
        look_at(obj, target)
    area('Sunset / large warm window', (-1.3,-1.1,2.4), (0,0,0), 170, 1.45, (1,.78,.55))
    area('Sky / soft blue fill', (1.4,.7,1.6), (0,0,.1), 90, 1.8, (.62,.78,1))
    area('Camera / soft bounce', (.3,-1.8,.9), (0,0,.1), 28, 1.25, (1,.92,.79))


README = '''LITTLE MERIDIAN — a small city for the tilt-shift camera
SPDX-License-Identifier: GPL-3.0-or-later

Open with this project's patched Blender 5.3 build. Press F12 to render.
The file starts on frame 40 with the HERO camera and CPU rendering for portability.
Render > Render Animation samples the animated city, frames 1–240 at 24 fps.
Motion blur MUST remain disabled; tilt-shift M4 does not support it or Vector passes.
This is deterministic keyframed traffic, not a rigid-body/traffic-engine simulation.
Traffic is stationary while the crossing pedestrians walk. Positional resets
occur at the playback boundary between frames 240 and 1; this is a visible wrap.
Signals: green 1–84 / 201–240, amber 85–92, red 93–200. Cars hold from 85 to 200.

CAMERAS (select in Scene Properties > Camera; or select camera, Ctrl Numpad 0):
01 HERO: tilt-shift positive tilt 1.7 degrees, 50 mm, f/1.4, central crossing focus.
02 COMPARE: same pose, lens, f-stop and focus target; tilt-shift angles zero.
03 SWING: same pose, swing -1.6 degrees, otherwise same settings.
04 OVERVIEW: ordinary upstream camera with tilt disabled; f/8 for city inspection.
05 ARCHITECTURE: level body, 60 mm, f/5.6, +4 mm vertical lens shift.
06 STREETLIFE: low avenue view, 35 mm, f/2.8; own focus target at the crossing.
Hero/comparison breathing is physical; this is not a pixel-aligned blur filter.

Select HERO and open Camera Data > Tilt-Shift. Move the FOCUS empty to change the
sharp plane; start with tiny movements, 0.25 degrees per step. All depth blur comes from
Cycles finite-aperture camera rays. No compositor blur or external assets.
Tilt-Shift display guides require Viewport Overlays > Extras, enabled in this file.
For single-device HIP: choose the AMD device in Preferences > System, then GPU
Compute in Render Properties. The saved file uses CPU so F12 needs no GPU setup.
Do not enable motion blur, Vector passes, HIP RT or multiple enabled HIP devices.

UNITS / GEOMETRY: right-handed Z-up city; streets follow world X and Y; 1 BU = 1 m.
The display is a real miniature: plinth 1.64 x 1.34 m; buildings 0.10–0.39 m tall.
Camera -Z looks forward, +Y is up. Lens controls store radians, displayed degrees.
Optical active rotation is Rz(axis) Ry(swing) Rx(tilt) in the documented lens frame.
Focus uses a tilt-shift off-axis focus object. Image-circle 0 means unbounded. These
gentle poses avoid singular focus geometry; extreme angles may validly be rejected.
Ground offsets 0.3–1 mm separate paint and surfaces to avoid coplanar flicker.

OUTLINER: numbered collections group board, streets, buildings, square, vegetation,
vehicles, signals, citizens, cameras and lighting. Meshes share small primitive
datablocks. All objects/materials/animation are local, with no linked resources,
drivers, handlers, add-ons, textures or execute-on-load code.
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'work/examples/harbor-city/harbor-city.blend')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    output = args.output.resolve()
    if not output.is_relative_to((ROOT/'work').resolve()) or output.suffix != '.blend':
        raise ValueError('Save the generated .blend below this project\'s ignored work/')
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=False)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    if 'tilt_shift_enabled' not in bpy.types.Camera.bl_rna.properties:
        raise RuntimeError('This scene requires the project native tilt-shift Blender build')
    scene = bpy.context.scene
    scene.name = 'LITTLE MERIDIAN · native camera playground'
    scene.unit_settings.system, scene.unit_settings.scale_length = 'METRIC', 1
    scene.render.engine, scene.cycles.device = 'CYCLES', 'CPU'
    scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.fps = 24
    scene.render.use_motion_blur = False
    scene.render.threads_mode, scene.render.threads = 'FIXED', 2
    scene.cycles.samples, scene.cycles.seed = 128, 71
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.cycles.diffuse_bounces, scene.cycles.glossy_bounces = 3, 3
    scene.frame_start, scene.frame_end = 1, 240
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    palette = {
        'cream':(.83,.76,.59), 'coral':(.62,.24,.17), 'teal':(.13,.38,.36),
        'ochre':(.72,.45,.19), 'navy':(.055,.12,.17), 'glass':(.045,.115,.14),
        'roof':(.20,.25,.24), 'paving':(.48,.48,.40), 'asphalt':(.10,.14,.15),
        'line':(.91,.84,.63), 'sage':(.30,.43,.25), 'leaf':(.13,.31,.16),
        'olive':(.37,.43,.16), 'bark':(.24,.14,.08), 'cedar':(.39,.24,.13),
        'iron':(.08,.115,.12), 'terracotta':(.47,.23,.13), 'awning':(.75,.51,.30),
        'rubber':(.022,.028,.028), 'skin':(.66,.40,.24), 'background':(.24,.31,.32),
        'water':(.08,.40,.43), 'foam':(.32,.62,.61), 'warm lamp':(1,.78,.37),
    }
    for name, color in palette.items():
        material(name, color, roughness=.25 if name in ('water','glass') else .7,
                 metallic=.15 if name in ('water','iron') else 0, emission=.4 if name=='warm lamp' else 0)
    city_base()
    streets()
    architecture()
    landscape()
    traffic()
    hero = cameras()
    lighting()
    notes = bpy.data.texts.new('START HERE · Little Meridian')
    notes.write(README)
    for frame, label in ((1,'GREEN · traffic moves'),(40,'HERO still'),(85,'AMBER · traffic holds'),(93,'RED · traffic holds'),
                         (105,'Pedestrians start crossing'),(184,'Crossing clear'),(201,'GREEN · traffic resumes')):
        scene.timeline_markers.new(label, frame=frame)
    scene.frame_set(40)
    scene.render.filepath = str(output.parent/'little-meridian-hero.png')
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'PROPERTIES':
                area.spaces.active.context = 'DATA'
            elif area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_perspective = 'CAMERA'
                area.spaces.active.region_3d.view_camera_zoom = 8
                area.spaces.active.shading.type = 'SOLID'
                area.spaces.active.shading.color_type = 'MATERIAL'
                area.spaces.active.overlay.show_extras = True
    scene['README'] = 'Open Text Editor > START HERE · Little Meridian. F12 renders the HERO camera.'
    scene['simulation'] = 'Deterministic keyframes, 24 fps, 240 frames; no physics engine or motion blur.'
    scene['license'] = 'GPL-3.0-or-later'
    scene['generator'] = 'examples/create_city.py; random seed 71; all local primitive assets'
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)
    summary = {'blend':str(output), 'objects':len(scene.objects), 'meshes':len(bpy.data.meshes),
        'materials':len(bpy.data.materials), 'frame':scene.frame_current, 'frames':[1,240], 'fps':24,
        'render':{'engine':'CYCLES','saved_device':'CPU','resolution':[1600,1000],'samples':128,
                  'motion_blur':False,'postprocess_blur':False,'seed':71},
        'active_camera':hero.name, 'cameras':[{'name':obj.name, 'native':obj.data.tilt_shift_enabled,
            'lens_mm':obj.data.lens, 'fstop':obj.data.dof.aperture_fstop,
            'tilt_degrees':math.degrees(obj.data.tilt_shift_tilt),
            'swing_degrees':math.degrees(obj.data.tilt_shift_swing),
            'shift': [obj.data.shift_x,obj.data.shift_y]} for obj in scene.objects if obj.type=='CAMERA'],
        'animation_objects':sum(obj.animation_data is not None for obj in scene.objects),
        'animation_targets':[obj.name for obj in scene.objects if obj.animation_data is not None],
        'traffic_phases':{'green':[[1,84],[201,240]],'amber':[[85,92]],'red':[[93,200]],
                          'vehicles_hold':[85,200],'pedestrians_cross':[105,184],
                          'loop_reset':'Between frames 240 and 1; discrete positional wrap'},
        'external_images':[image.filepath for image in bpy.data.images if image.source=='FILE']}
    output.with_suffix('.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('CITY_SAVED',json.dumps(summary),flush=True)


if __name__ == '__main__':
    main()
