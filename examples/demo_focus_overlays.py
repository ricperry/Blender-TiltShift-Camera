# SPDX-License-Identifier: GPL-3.0-or-later
"""Intersect the saved sharp plane with visible scene surfaces, without rendering.

Run with patched Blender --background --python this_file -- --output work/... .
The comparison gallery calls generate() with --gallery-only --focus-overlays.
"""
import argparse
from array import array
import hashlib
import html
import json
import math
from pathlib import Path
import struct
import sys
import zlib

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
CASES = ('table-native', 'table-ordinary-best', 'table-ordinary-f16',
         'swing-native', 'swing-ordinary-best', 'axis-native', 'axis-ordinary-best',
         'city-native', 'city-ordinary-best', 'city-ordinary-blur-fit')
PAIR_NOTES = {
    ('table-native', 'table-ordinary-best'):
        'Native tilt follows the printed paper. Ordinary focus intersects the scene in a band across one camera-facing plane.',
    ('table-native', 'table-ordinary-f16'):
        'Stopping down broadens ordinary depth of field without rotating its exact sharp plane. The overlay shows the plane, so it does not expand at f/16. These renders do not simulate diffraction or exposure penalties.',
    ('swing-native', 'swing-ordinary-best'):
        'Swing turns the sharp plane sideways. Compare where the green plane crosses the same paper, leaves and product surfaces in both photographs.',
    ('axis-native', 'axis-ordinary-best'):
        'Rotating the movement axis turns the sharp plane diagonally through the scene. Ordinary focus moves a camera-facing plane toward or away from the camera.',
    ('city-native', 'city-ordinary-best'):
        'Tilt intersects roofs, buildings and streets along a different plane. Ordinary focus and aperture can also keep a broad area sharp; this overlay identifies the exact plane rather than the whole depth of field.',
    ('city-native', 'city-ordinary-blur-fit'):
        'The ordinary camera fits both focus and aperture to approximate native blur. Its sharp plane remains camera-facing. The enormous fitted pupil changes occlusion, so the chief-ray surface overlay is only a geometric reference.',
}
# Display thickness is shared by both cameras in each family, independent of f-stop.
PLANE_HALF_WIDTH_M = {'table': .004, 'swing': .004, 'axis': .004, 'city': .65}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def optical(value):
    return Vector((value.x, value.y, -value.z))


def normal(data):
    t, s, a = data.tilt_shift_tilt, data.tilt_shift_swing, data.tilt_shift_axis_rotation
    return Vector((math.cos(a)*math.sin(s)*math.cos(t)+math.sin(a)*math.sin(t),
                   -math.sin(a)*math.sin(s)*math.cos(t)+math.cos(a)*math.sin(t),
                   math.cos(s)*math.cos(t)))


def geometry(camera, scene):
    """All vectors use lens-relative camera +X right, +Y up, +Z forward, metres."""
    data = camera.data
    f = data.lens * .001
    centre, b = Vector((0, 0, 0)), f
    guide_error = None
    if data.tilt_shift_enabled:
        guide = data.tilt_shift_guide_geometry(camera)
        if not guide[0] or not guide[1] or not math.isfinite(guide[3]) or guide[3] <= 0:
            raise ValueError('Invalid evaluated native guide')
        b = guide[3]
        lens = [optical(Vector(guide[4][i:i+3])) for i in range(0, 12, 3)]
        centre = sum(lens, Vector()) / 4
        m = normal(data) - Vector((0, 0, f/b))
        k = f
        vertices = [optical(Vector(guide[5][i:i+3])) for i in range(0, 12, 3)]
        guide_error = max(abs(m.dot(p-centre)-k) / m.length for p in vertices)
        # RNA guide vertices and b are float32, so compare distance at scene scale.
        tolerance = 2e-4 * max(1, data.dof.focus_distance)
        if guide_error > tolerance:
            raise ValueError(f'Focus plane disagrees with evaluated guide: {guide_error} m')
    else:
        m, k = Vector((0, 0, 1)), data.dof.focus_distance
    frame = data.view_frame(scene=scene)
    frame = [(p.x/abs(p.z)*f/b, p.y/abs(p.z)*f/b) for p in frame]
    bounds = (min(p[0] for p in frame), max(p[0] for p in frame),
              min(p[1] for p in frame), max(p[1] for p in frame))
    return centre, b, m, k, bounds, guide_error



def png_rgba(path, width, height, pixels):
    """Write untagged sRGB display colours; diagnostics never alter rendered PNGs."""
    def chunk(kind, payload):
        return struct.pack('>I', len(payload))+kind+payload+struct.pack('>I', zlib.crc32(kind+payload))
    rows = b''.join(b'\0'+pixels[y*width*4:(y+1)*width*4] for y in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))+
                     chunk(b'sRGB', b'\0')+chunk(b'IDAT', zlib.compress(rows, 6))+chunk(b'IEND', b''))


def scene_overlay(output, name):
    manifest_path = output/f'{name}.json'
    record = json.loads(manifest_path.read_text())
    blend_path, image_path = output/f'{name}.blend', output/f'{name}.png'
    source = {'blend_sha256': digest(blend_path), 'image_sha256': digest(image_path),
              'manifest_sha256': digest(manifest_path), 'helper_sha256': digest(__file__)}
    if source['blend_sha256'] != record['blend_sha256'] or source['image_sha256'] != record['image_sha256']:
        raise ValueError(f'{name}: original artifact does not match render manifest')
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    camera = scene.camera.evaluated_get(deps)
    data = camera.data
    if data.sensor_fit != 'HORIZONTAL' or scene.render.pixel_aspect_x != scene.render.pixel_aspect_y:
        raise ValueError('Surface overlay requires horizontal fit and square pixels')
    centre, b, m, k, bounds, error = geometry(camera, scene)
    if m.length < 1e-10:
        raise ValueError('Singular focus plane normal')
    left, right, bottom, top = bounds
    width, height = record['resolution']
    columns = min(960, width)
    rows = max(1, round(columns*height/width))
    half_width = PLANE_HALF_WIDTH_M[record['family']]
    inverse = camera.matrix_world.inverted()
    origin = camera.matrix_world @ optical(centre)
    rotation = camera.matrix_world.to_3x3()
    pixels = bytearray(columns*rows*4)
    # Interleaved little-endian float32: camera-forward depth, signed plane distance.
    # Missing first-surface hits use NaN for both values. No interpolation or fill.
    surfaces = array('f')
    max_reprojection_error = 0.0
    hits, marked, core = 0, 0, 0
    signed_min, signed_max = math.inf, -math.inf
    for row in range(rows):
        v = (row+.5)/rows
        for column in range(columns):
            u = (column+.5)/columns
            direction = rotation @ Vector((left+u*(right-left), top-v*(top-bottom), -1))
            hit, point, _, _, obj, _ = scene.ray_cast(deps, origin, direction.normalized(), distance=data.clip_end)
            if not hit or obj.hide_render:
                surfaces.extend((math.nan, math.nan))
                continue
            q = optical(inverse @ point)-centre
            if q.z <= 1e-10:
                raise ValueError(f'{name}: nonpositive visible surface depth')
            projected = ((q.x/q.z-left)/(right-left), (top-q.y/q.z)/(top-bottom))
            max_reprojection_error = max(max_reprojection_error, abs(projected[0]-u), abs(projected[1]-v))
            distance = (m.dot(q)-k)/m.length
            surfaces.extend((q.z, distance))
            hits += 1
            signed_min, signed_max = min(signed_min, distance), max(signed_max, distance)
            fraction = abs(distance)/half_width
            if fraction >= 1:
                continue
            marked += 1
            core += fraction <= .12
            # Opaque colour plus smooth alpha taper; the gallery sets global opacity.
            # The brighter centre gives a visual reference without inventing a depth edge.
            feather = 1-fraction*fraction*(3-2*fraction)
            colour = (182, 255, 216) if fraction <= .12 else (76, 243, 163)
            offset = (row*columns+column)*4
            pixels[offset:offset+4] = bytes((*colour, round(255*feather)))
        if row and row % 180 == 0:
            print('FOCUS_SURFACE_PROGRESS', name, row, '/', rows, flush=True)
    if not hits or max_reprojection_error > 2e-5:
        raise ValueError(f'{name}: invalid visible hits or reprojection {max_reprojection_error}')
    mask_path = output/f'{name}.focus.png'
    png_rgba(mask_path, columns, rows, pixels)
    if sys.byteorder != 'little':
        surfaces.byteswap()
    depth_path = output/f'{name}.focus-surface.f32.z'
    depth_path.write_bytes(zlib.compress(surfaces.tobytes(), 6))
    result = {'case': name, 'source': source, 'resolution': [width, height],
              'mask_file': mask_path.name, 'mask_sha256': digest(mask_path),
              'surface_file': depth_path.name, 'surface_sha256': digest(depth_path),
              'surface_format': 'zlib compressed row-major interleaved little-endian float32 [camera-forward depth m, signed plane distance m]; top-left first; NaN means no visible mesh hit',
              'sensor_distance_m': b, 'chief_ray_bounds': list(bounds),
              'optical_centre_camera_m': list(centre),
              'camera_matrix_world': [list(row) for row in camera.matrix_world],
              'plane_normal_camera': list(m), 'plane_constant_m': k,
              'evaluated_guide_max_plane_error_m': error,
              'sample_grid': [columns, rows], 'sample_count': hits,
              'marked_sample_count': marked, 'bright_centre_sample_count': core,
              'plane_visual_half_width_m': half_width,
              'signed_distance_range_m': [signed_min, signed_max],
              'max_reprojection_error_uv': max_reprojection_error}
    (output/f'{name}.focus.json').write_text(json.dumps(result, indent=2)+'\n')
    print('FOCUS_SURFACE', name, hits, 'visible hits', marked, 'plane-band hits', flush=True)
    return result


def generate(output):
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT/'work').resolve()):
        raise ValueError('Generated artifacts must remain below ignored work/')
    records = {}
    for name in CASES:
        if all((output/f'{name}.{ext}').exists() for ext in ('blend', 'png', 'json')):
            records[name] = scene_overlay(output, name)
    pairs = {a+'--'+b: True for a, b in PAIR_NOTES if a in records and b in records}
    summary = {'helper_sha256': digest(__file__), 'cases': list(records), 'pairs': pairs,
               'method': 'Dense chief-ray first mesh hits; signed distance to exact optical sharp plane; feathered RGBA band at scene surfaces only',
               'visual_half_width_m_by_family': PLANE_HALF_WIDTH_M,
               'coordinates': 'Lens-relative camera X right, Y up, Z forward; metres. Full evaluated camera pose.',
               'rotation': 'Rz(axis) Ry(swing) Rx(tilt), reference Y-down then reflected; native evaluated guide b.',
               'plane_equations': 'Native (n-f/b*Z) dot Q=f; ordinary Qz=D. Plane is zero blur, not finite depth of field.',
               'tolerances': 'Guide plane distance <=2e-4*max(1,D) m (float32 RNA); plane normal length and visible depth >1e-10; chief-ray reprojection <=2e-5 normalized UV.',
               'limitations': ['Finite displayed band thickness makes the zero-thickness plane visible; it is independent of aperture and is not a depth-of-field boundary.',
                               'One first-surface sample per mask pixel, nearest-neighbour display with no depth interpolation; tiny geometry below sample spacing can be missed.',
                               'Chief-ray mesh visibility excludes material transparency, reflections, refraction and finite-pupil occlusion changes, especially the enormous city blur-fit pupil.',
                               'A geometric reference, not a measurement of rendered image sharpness.']}
    (output/'focus-guides.json').write_text(json.dumps(summary, indent=2)+'\n')
    return records, pairs


def load_existing(output):
    """Reuse only source- and mask-verified guides, without opening any scene."""
    summary_path = output/'focus-guides.json'
    if not summary_path.exists():
        return {}, {}
    summary = json.loads(summary_path.read_text())
    if summary['helper_sha256'] != digest(__file__):
        return {}, {}
    records = {}
    for name in summary['cases']:
        path = output/f'{name}.focus.json'
        if not path.exists():
            continue
        record = json.loads(path.read_text())
        if not all((output/record[field]).exists() and digest(output/record[field]) == record[hash_field]
                   for field, hash_field in (('mask_file', 'mask_sha256'), ('surface_file', 'surface_sha256'))):
            continue
        if all((output/f'{name}.{ext}').exists() and digest(output/f'{name}.{ext}') == record['source'][key]
               for ext, key in (('blend', 'blend_sha256'), ('png', 'image_sha256'), ('json', 'manifest_sha256'))):
            records[name] = record
    pairs = {key: True for key in summary['pairs'] if all(case in records for case in key.split('--'))}
    return records, pairs


def pair_html(a, b, records, pairs, index):
    if a+'--'+b not in pairs:
        return '', ''
    controls = (f'<div class="guide-controls"><button type="button" class="guide-toggle" aria-pressed="false" '
                f'aria-controls="guide-{index}">Show focus plane</button> '
                '<label>Plane opacity <input class="guide-opacity" type="range" min="10" max="100" value="45" '
                'aria-label="Focus plane opacity"><output>45%</output></label></div>')
    half_width = records[a]['plane_visual_half_width_m']
    if half_width != records[b]['plane_visual_half_width_m']:
        raise ValueError('Paired surface overlays require shared display thickness')
    thickness = f'{half_width*1000:g} mm' if half_width < .1 else f'{half_width:g} m'
    detail = (f'<div id="guide-{index}" class="guide-explanation" hidden>'
              '<p class="legend"><span class="plane-swatch" aria-hidden="true"></span> '
              '<strong>Focus-plane intersection</strong></p>'
              f'<p>{html.escape(PAIR_NOTES[(a,b)])}</p>'
              f'<p>Green marks visible surfaces within ±{thickness} of the exact sharp plane, feathered toward the edge; '
              'the brighter centre is closest to the plane. This finite thickness makes the plane visible and does not show the full depth of field. '
              'Empty air and surfaces hidden behind the first mesh hit remain unmarked. '
              'Chief-ray geometry is a reference; finite-aperture blur and occlusion can extend beyond it. '
              '<a href="focus-guides.json">Method and tolerances</a>.</p></div>')
    return controls, detail


CSS = """.image-stack{position:relative}.image-stack>a{display:block}.image-stack .focus-overlay{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;opacity:var(--guide-opacity,.45);image-rendering:pixelated}
.focus-overlay[hidden],.guide-explanation[hidden]{display:none}.guide-controls{display:flex;flex-wrap:wrap;align-items:center;gap:1rem;margin:1rem 0}
.guide-controls button{padding:.55rem .85rem;font:inherit;color:#e4e7df;background:#344b3c;border:1px solid #9fbea8;border-radius:.35rem;cursor:pointer}
.guide-controls button[aria-pressed=true]{background:#e4e7df;color:#16231c}.guide-controls input{vertical-align:middle;accent-color:#a4ddb4}.guide-controls output{display:inline-block;width:3rem}
.guide-explanation{border-left:3px solid #9fbea8;padding:.3rem 1rem;background:#202a24;margin-top:1rem}.guide-explanation p{font-size:.9rem}.plane-swatch{display:inline-block;width:1.1rem;height:.8rem;margin-right:.35rem;background:#4cf3a3;opacity:.7}
button:focus-visible,input:focus-visible{outline:3px solid #fff;outline-offset:3px}"""
SCRIPT = """<script>document.querySelectorAll('.guide-toggle').forEach(button=>{const section=button.closest('section');const explanation=section.querySelector('.guide-explanation');button.addEventListener('click',()=>{const on=button.getAttribute('aria-pressed')!=='true';button.setAttribute('aria-pressed',String(on));button.textContent=on?'Hide focus plane':'Show focus plane';explanation.hidden=!on;section.querySelectorAll('.focus-overlay').forEach(image=>image.hidden=!on);});const slider=section.querySelector('.guide-opacity');slider.addEventListener('input',()=>{section.style.setProperty('--guide-opacity',slider.value/100);section.querySelector('output').value=slider.value+'%';});});</script>"""


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    generate(args.output)
