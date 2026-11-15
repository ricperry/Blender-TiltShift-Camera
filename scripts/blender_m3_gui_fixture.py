# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare the real native camera UI in an agent-owned GUI and stay open.

Launch only on the authorized private display with isolated Blender resources.
The parent harness owns screenshots/window teardown. This script writes readiness
and native geometry evidence after redraw; it never closes the application.
"""
import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils import Quaternion

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from blender_m3_validation import gui_scene

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
args.output = args.output.resolve()
if not args.output.is_relative_to(ROOT/'work'):
    raise ValueError('GUI artifacts must be below ignored work/')
args.output.mkdir(parents=True, exist_ok=True)
gui_scene(args.output)

# Keep built-in panel classes and actual registered UI unchanged. Enlarge the
# Properties area through the normal layout operator when a suitable area exists.
def ready():
    scene = bpy.context.scene
    camera = scene.camera
    scene.render.engine = 'CYCLES'
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'PROPERTIES':
                area.spaces.active.context = 'DATA'
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                space.overlay.show_extras = True
                space.region_3d.view_perspective = 'PERSP'
                space.region_3d.view_distance = 4
                space.region_3d.view_location = (0, 0, -.9)
                space.region_3d.view_rotation = Quaternion((.8924, .2391, -.3696, -.099)).normalized()
            area.tag_redraw()
    obj = camera.evaluated_get(bpy.context.evaluated_depsgraph_get())
    geometry = obj.data.tilt_shift_guide_geometry(obj)
    state = {'ready': True, 'native_panel': hasattr(bpy.types, 'DATA_PT_tilt_shift'),
             'native_animation_panel': hasattr(bpy.types, 'DATA_PT_tilt_shift_animation'),
             'dof_enabled': camera.data.dof.use_dof,
             'guide_validity': list(geometry[:3]),
             'camera': camera.name, 'engine': scene.render.engine,
             'areas': [{'type': a.type, 'width': a.width, 'height': a.height}
                       for a in bpy.context.screen.areas]}
    (args.output/'gui-ready.json').write_text(json.dumps(state, indent=2)+'\n')
    print('M3_GUI_READY', json.dumps(state), flush=True)
    return None

bpy.app.timers.register(ready, first_interval=4)
