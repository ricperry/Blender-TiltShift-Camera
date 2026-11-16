# SPDX-License-Identifier: GPL-3.0-or-later
"""Build one local photo/video gallery from existing, verified artifacts.

Ordinary Python only: no Blender, Pillow, rendering, or encoding. Output and
input directories must remain under ignored work/. Media and manifests are read
only; the canonical gallery and compatibility redirects are the only outputs.
"""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
PHOTO_DEFAULT = ROOT / 'work/demo-comparisons/4k'
VIDEO_DEFAULT = ROOT / 'work/demo-animations/960x540'
GALLERY_DEFAULT = ROOT / 'work/demo-gallery'
REPOSITORY_URL = 'https://github.com/ricperry/Blender-TiltShift-Camera'

# Stable artifact identifiers are deliberately independent of display copy.
PAIRS = [
    ('Follow the tabletop', 'focus', 'table-native', 'table-ordinary-best',
     'A −10° tilt follows the receding paper. Compare the near and far lettering at the same physical pupil.'),
    ('Trade aperture for depth of field', 'focus', 'table-native', 'table-ordinary-f16',
     'Stopping down the standard camera broadens sharpness. Its exact plane of focus still faces the camera.'),
    ('Stop down both cameras', 'focus', 'table-native-f16', 'table-ordinary-f16',
     'At matched smaller pupils, both views gain depth of field. These geometric renders do not simulate diffraction or exposure loss.'),
    ('Start with zero lens angles', 'focus', 'table-native-zero', 'table-ordinary-best',
     'Zero tilt and swing provide a baseline. Finite-distance focusing can still change framing through physical focus breathing.'),
    ('Turn focus from side to side', 'movements', 'swing-native', 'swing-ordinary-best',
     'A 10° swing turns the sharp plane across the subject instead of along the tabletop.'),
    ('Rotate the movement axes', 'movements', 'axis-native', 'axis-ordinary-best',
     'Rotate the movement axes 45° while retaining −10° tilt to place focus diagonally.'),
    ('Create a city focus band', 'focus', 'city-native', 'city-ordinary-best',
     'At real city scale, +10° tilt creates selective focus. The standard camera uses optimized focus and the same physical pupil.'),
    ('Fit standard focus and aperture', 'focus', 'city-native', 'city-ordinary-blur-fit',
     'An optimized standard lens approximates scalar blur across visible surfaces, but cannot rotate its sharp plane or match directional bokeh exactly.'),
    ('Choose manual or object focus', 'focus', 'city-native', 'city-native-object',
     'The same city sharp plane can be set with a manual distance or a focus object.'),
    ('Shift horizontally', 'framing', 'shift-x-native', 'shift-x-ordinary',
     'Move the framing sideways while keeping the camera level. Shift is also available in standard Cycles.'),
    ('Shift vertically', 'framing', 'shift-y-native', 'shift-y-ordinary',
     'Frame higher without tilting the camera body, keeping architectural verticals parallel. Both cameras support this movement.'),
]
CLIPS = [
    ('tilt', 'Lens tilt', 'movements', 'Rotate focus from foreground to background. Swing and movement-axis rotation stay at zero.'),
    ('swing', 'Lens swing', 'movements', 'Rotate focus across the frame. Tilt and movement-axis rotation stay at zero.'),
    ('axis', 'Movement-axis rotation', 'movements', 'Turn the direction of the focus band through a full cycle while retaining −10° tilt.'),
    ('shift-x', 'Horizontal shift', 'framing', 'Slide framing left and right with a level architectural camera and zero lens angles.'),
    ('shift-y', 'Vertical shift', 'framing', 'Move the building within the frame while the level camera keeps verticals parallel.'),
    ('focus', 'Focus distance', 'focus', 'Move focus through the subject while retaining −10° tilt.'),
    ('lens', 'Focal length', 'framing', 'Change the field of view from wide to telephoto while retaining −10° tilt.'),
    ('fstop', 'Aperture', 'focus', 'Watch depth of field broaden through evenly spaced exposure stops, with −10° tilt.'),
]


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def below_work(path):
    path = Path(path).resolve()
    if not path.is_relative_to((ROOT / 'work').resolve()):
        raise ValueError('Gallery inputs and output must remain below ignored work/')
    return path


def verify(path, expected):
    if not path.is_file() or digest(path) != expected:
        raise ValueError(f'Missing or changed gallery artifact: {path}')


def load_photos(directory):
    records = {}
    for name in dict.fromkeys(name for pair in PAIRS for name in pair[2:4]):
        path = directory / f'{name}.json'
        if not path.exists():
            continue
        record = read_json(path)
        if 'image_sha256' not in record:
            continue
        verify(directory / f'{name}.png', record['image_sha256'])
        verify(directory / f'{name}.blend', record['blend_sha256'])
        records[name] = record
    return records


def load_guides(directory):
    """Verify cached optics independently of presentation-only helper changes."""
    summary_path = directory / 'focus-guides.json'
    if not summary_path.exists():
        return {}, {}
    summary = read_json(summary_path)
    # A captured source supports future UI-only edits without blessing new optics.
    candidates = [directory / 'focus-overlay-source.py', ROOT / 'examples/demo_focus_overlays.py']
    if not any(path.is_file() and digest(path) == summary['helper_sha256'] for path in candidates):
        raise ValueError('Focus-guide source changed; retain the captured helper or regenerate guides')
    records = {}
    for name in summary['cases']:
        record = read_json(directory / f'{name}.focus.json')
        if record['source']['helper_sha256'] != summary['helper_sha256']:
            raise ValueError(f'{name}: focus-guide source differs from summary')
        for field, hash_field in [('mask_file', 'mask_sha256'), ('surface_file', 'surface_sha256')]:
            artifact = (directory / record[field]).resolve()
            if not artifact.is_relative_to(directory):
                raise ValueError('Focus-guide artifact escapes its source directory')
            verify(artifact, record[hash_field])
        for extension, key in [('blend', 'blend_sha256'), ('png', 'image_sha256'), ('json', 'manifest_sha256')]:
            verify(directory / f'{name}.{extension}', record['source'][key])
        records[name] = record
    return records, summary['pairs']


def load_videos(directory):
    records = {}
    for name, *_ in CLIPS:
        folder = directory / name
        if not (folder / 'encoding.json').exists():
            continue
        record = read_json(folder / 'animation.json')
        encoded = read_json(folder / 'encoding.json')
        verify(folder / 'animation.json', encoded['animation_manifest_sha256'])
        verify(folder / f'{name}.mp4', encoded['video_sha256'])
        verify(folder / f'{name}.blend', record['blend_sha256'])
        verify(folder / 'labeled/frame-0001.png', encoded['labels'][0]['sha256'])
        records[name] = record
    return records


def value_label(record, frame):
    """Display evaluated values without importing the Pillow-based encoder."""
    config = record['configuration']
    value, unit = frame['value'], config['spec']['unit']
    if config['clip'] in ('shift-x', 'shift-y'):
        return f"{frame['shift_mm']:+.2f} mm ({value:+.3f} sensor widths)"
    if unit == 'deg':
        return f'{value:+.1f}°'
    if unit == 'f/':
        return f'f/{value:.2f}'
    return f'{value:.3g} {unit}'


def build_gallery(photos=PHOTO_DEFAULT, videos=VIDEO_DEFAULT, output=GALLERY_DEFAULT,
                  *, public=False):
    photos, videos, output = map(below_work, (photos, videos, output))
    if output in (photos, videos):
        raise ValueError('Canonical gallery must have its own directory')
    photo_records = load_photos(photos)
    guides, guide_pairs = load_guides(photos)
    video_records = load_videos(videos)
    output.mkdir(parents=True, exist_ok=True)

    def url(path):
        if public and Path(path).is_relative_to(ROOT / 'examples'):
            return REPOSITORY_URL + '/blob/main/' + quote(Path(path).relative_to(ROOT).as_posix())
        return quote(Path(os.path.relpath(path, output)).as_posix(), safe='/')

    def link(path, label, download=False):
        return f'<a href="{url(path)}"'+(' download' if download else '')+f'>{html.escape(label)}</a>'

    def photo_card(name, caption, show_guide):
        record = photo_records[name]
        camera = record['camera']
        title = 'Tilt-shift camera' if record['native_enabled'] else 'Standard perspective camera'
        width, height = map(int, record['resolution'])
        alt = f'{title}: {caption}'
        overlay = (f'<img class="focus-overlay" src="{url(photos / guides[name]["mask_file"])}" '
                   f'width="{width}" height="{height}" alt="Green focus-plane intersection on visible surfaces" hidden>' if show_guide else '')
        focus = 'Object focus' if camera['focus_object'] else f"Focus {camera['focus_distance_m']:.4g} m"
        settings = f"{camera['lens_mm']:.1f} mm · f/{camera['fstop']:.3g} · {focus}"
        movements = (f"Tilt {camera['tilt_deg']:.3g}° · Swing {camera['swing_deg']:.3g}° · Axis {camera['axis_deg']:.3g}°"
                     if record['native_enabled'] else 'Parallel lens and sensor planes')
        shift = camera['shift']
        details = f"{movements}. Shift X {shift[0]*camera['sensor_width_mm']:+.3g} mm, Y {shift[1]*camera['sensor_width_mm']:+.3g} mm. Physical pupil {camera['pupil_diameter_m']*1000:.3g} mm."
        resolution_label = '4K PNG' if width == 3840 and height == 2160 else f'{width} × {height} PNG'
        return f'''<article class="photo-card"><h3 class="camera-badge {'tilt-shift' if record['native_enabled'] else 'standard'}">{title}</h3>
<div class="image-stack"><a href="{url(photos / (name+'.png'))}" aria-label="Open full-resolution image: {html.escape(alt)}"><img src="{url(photos / (name+'.png'))}" width="{width}" height="{height}" loading="lazy" decoding="async" alt="{html.escape(alt)}"></a>{overlay}</div>
<p class="settings">{html.escape(settings)}</p><p class="asset-links">{link(photos/(name+'.png'), 'Open '+resolution_label)} · {link(photos/(name+'.blend'), 'Blender scene')}</p>
<details><summary>Camera settings &amp; source</summary><p>{html.escape(details)}</p><p>{width} × {height} · {record['samples']} samples · seed {record['seed']}. {link(photos/(name+'.json'), 'Render manifest')}</p></details></article>'''

    cards = []
    pair_count = 0
    for index, (title, theme, a, b, caption) in enumerate(PAIRS):
        if a not in photo_records or b not in photo_records:
            continue
        pair_count += 1
        pair_key = a + '--' + b
        show_guide = bool(guide_pairs.get(pair_key)) and a in guides and b in guides
        controls = explanation = ''
        if show_guide:
            half_width = guides[a]['plane_visual_half_width_m']
            if half_width != guides[b]['plane_visual_half_width_m']:
                raise ValueError('Paired guides must have the same display thickness')
            thickness = f'{half_width*1000:g} mm' if half_width < .1 else f'{half_width:g} m'
            controls = f'''<div class="guide-controls"><button class="guide-toggle" type="button" aria-pressed="false" aria-controls="planes-{index}">Show focus planes</button><label for="opacity-{index}">Plane opacity</label><input id="opacity-{index}" class="guide-opacity" type="range" min="10" max="100" value="45"><output for="opacity-{index}">45%</output><span>Applies to both photos</span></div>'''
            explanation = f'''<div class="guide-explanation" id="planes-{index}" hidden><p><span class="swatch" aria-hidden="true"></span>Green marks visible surfaces within ±{thickness} of the exact sharp plane, feathered at its edges. This is a geometric reference, not the full depth of field. The band does not expand when the aperture closes.</p><details><summary>How to read the overlay</summary><p>Only the first mesh hit along each chief ray is marked; empty air and hidden surfaces are excluded. Material transparency and reflections are not modeled. Tiny geometry may be missed at the 960 × 540 sampling resolution. Large apertures can change occlusion, especially in the city blur fit. {link(photos/'focus-guides.json', 'Method, coordinates & tolerances')}</p></details></div>'''
        cards.append(f'''<section id="photo-{index+1}" class="gallery-item photo-section" data-kind="photos" data-theme="{theme}" data-pair="{pair_key}"><div class="section-heading"><span class="eyebrow">Photo comparison · {THEMES[theme]}</span><h2>{title}</h2><p>{caption}</p></div>{controls}<div class="pair">{photo_card(a, title, show_guide)}{photo_card(b, title, show_guide)}</div>{explanation}</section>''')

    for name, title, theme, caption in CLIPS:
        if name not in video_records:
            continue
        record = video_records[name]
        config = record['configuration']
        folder = videos / name
        start, end = (value_label(record, record['frames'][index]) for index in (0, -1))
        width, height = config['resolution']
        cards.append(f'''<section id="video-{name}" class="gallery-item video-section" data-kind="videos" data-theme="{theme}"><div class="section-heading"><span class="eyebrow">Video · {THEMES[theme]}</span><h2>{title}</h2><p>{caption}</p></div><div class="video-media"><span class="camera-badge tilt-shift">Tilt-shift camera</span><video controls playsinline preload="none" width="{width}" height="{height}" poster="{url(folder/'labeled/frame-0001.png')}" aria-label="{title} animation"><source src="{url(folder/(name+'.mp4'))}" type="video/mp4"></video></div><p class="range">{html.escape(start)} <span aria-label="to">→</span> {html.escape(end)}</p><p class="asset-links">{link(folder/(name+'.mp4'), 'Download MP4', True)} · {link(folder/(name+'.blend'), 'Animated Blender scene')}</p><details><summary>Clip settings &amp; source</summary><p>{record['duration_s']} seconds · {config['fps']} fps · {len(record['frames'])} independently rendered frames · {width} × {height} · {config['samples']} samples · seed {config['seed']}. {html.escape(record['range_kind'])}.</p><p>{link(folder/'animation.json', 'Frame values & optical checks')} · {link(folder/'encoding.json', 'Encoding audit')}</p></details></section>''')

    # Curate related photographs and motion together; media filters retain order.
    order = ['photo-1', 'video-tilt', 'video-swing', 'photo-5', 'photo-6',
             'video-axis', 'video-focus', 'photo-2', 'photo-3', 'photo-4',
             'video-fstop', 'video-lens', 'photo-7', 'photo-8', 'photo-9',
             'video-shift-x', 'video-shift-y', 'photo-10', 'photo-11']
    cards.sort(key=lambda card: next(index for index, identifier in enumerate(order)
                                    if card.startswith(f'<section id="{identifier}" ')))
    intro = f'{len(photo_records)} photographs in {pair_count} comparisons · {len(video_records)} videos · editable Blender scenes'
    context = 'Photo &amp; video demonstrations' if public else 'Local demonstration'
    footer = (f'<a href="{REPOSITORY_URL}">Source &amp; build instructions</a> · '
              '<a href="LICENSE">GPL-3.0-or-later</a> · '
              '<a href="publication-manifest.json">Publication manifest</a>' if public else
              'Generated local artifacts. This gallery is not published.')
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Tilt-shift camera — photo &amp; video gallery</title><style>{CSS}</style></head><body>
<a class="skip-link" href="#gallery">Skip to gallery</a><main><header class="hero"><p class="eyebrow">Blender 5.3 / Cycles · {context}</p><h1>A new plane of focus.</h1><p class="lede">Explore the tilt-shift camera in photographs and motion. Follow a tabletop, place a band of focus across a city, or reframe architecture while keeping the camera level.</p><p class="inventory">{intro}</p><p class="intro-note">Every image uses physical camera rays. Open a 4K photo to inspect detail; play a clip to watch one setting change.</p></header>
<nav class="gallery-toolbar" aria-label="Gallery filters"><div class="type-filters" role="group" aria-label="Media type"><button type="button" data-filter="all" aria-pressed="true">All</button><button type="button" data-filter="photos" aria-pressed="false">Photos <span>{pair_count}</span></button><button type="button" data-filter="videos" aria-pressed="false">Videos <span>{len(video_records)}</span></button></div><label class="theme-filter">Explore <select id="theme"><option value="all">All camera controls</option><option value="focus">Focus &amp; aperture</option><option value="movements">Lens movements</option><option value="framing">Framing &amp; shift</option></select></label><p id="result-count" role="status" aria-live="polite">{len(cards)} demonstrations</p></nav>
<div id="gallery" class="gallery">{''.join(cards)}</div><p id="empty-state" hidden>No demonstrations match these filters.</p>
<details class="technical-notes"><summary>About these demonstrations</summary><p>Blur comes from finite-aperture camera rays, without image-space blur, denoising, interpolation or motion blur. The videos add only a setting/value corner label. Focus, focal length, shift and aperture also exist in standard Cycles. The special lens movements rotate the sharp plane.</p><p>These ideal geometric optics examples do not simulate diffraction, shutter exposure or sensor noise. Video ranges are representative photographic choices, except for the full movement-axis cycle; they do not cover every valid optical configuration. Finite-distance focusing can change framing. Large movements can encounter singularities or invalid ray domains, guarded by the camera.</p><p>Photo pairs compare matched physical pupils where indicated. Standard focus/aperture fits approximate scalar blur rather than full image equivalence. Green overlays are optional, verified surface intersections of the exact sharp plane; they are not sharpness masks or depth-of-field boundaries.</p><p>{link(ROOT/'examples/DEMO_COMPARISONS.md', 'Photo methods & reproduction')} · {link(ROOT/'examples/DEMO_ANIMATIONS.md', 'Video methods & reproduction')} · {link(ROOT/'examples/DEMO_GALLERY.md', 'Rebuild this gallery')}</p></details>
<footer><p>Tilt-Shift Camera for Blender / GPL-3.0-or-later</p><p>{footer}</p></footer></main><script>{SCRIPT}</script></body></html>'''
    (output / 'index.html').write_text(document)
    for directory in (() if public else (photos, videos)):
        if not directory.exists():
            continue
        destination = quote(Path(os.path.relpath(output/'index.html', directory)).as_posix(), safe='/')
        (directory / 'index.html').write_text(f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="0;url={destination}"><title>Tilt-shift camera gallery</title><p>The photographs and videos now share one gallery. <a href="{destination}">Open the tilt-shift camera gallery</a>.</p></html>')
    print(f'Gallery: {output / "index.html"} ({intro})')
    return output / 'index.html'


THEMES = {'focus': 'Focus &amp; aperture', 'movements': 'Lens movements', 'framing': 'Framing &amp; shift'}

CSS = '''
:root{color-scheme:dark;--bg:#141a1b;--panel:#1e2627;--line:#3a4747;--ink:#edf0e8;--muted:#b2bfbc;--accent:#cbe7ad}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,sans-serif}main{max-width:1600px;margin:auto;padding:0 40px}a{color:var(--accent);text-underline-offset:.2em}a:hover{text-decoration-thickness:2px}button,select,input{font:inherit}button,select{color:var(--ink);background:var(--panel);border:1px solid #657575;border-radius:6px;padding:.6rem .9rem}button{cursor:pointer}button:hover{border-color:var(--accent)}button[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:#19231b}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible,video:focus-visible{outline:3px solid #f3d993;outline-offset:4px}[hidden]{display:none!important}.skip-link{position:absolute;top:-100px;left:20px;padding:1rem;background:var(--panel);z-index:5}.skip-link:focus{top:10px}.hero{padding:32px 0 20px;max-width:1000px}.eyebrow{color:var(--accent);text-transform:uppercase;font-size:.74rem;font-weight:650;letter-spacing:.14em}h1{font-size:clamp(2.8rem,5vw,4.5rem);font-weight:450;letter-spacing:-.05em;line-height:1.05;margin:12px 0 16px}h2{font-size:clamp(1.45rem,2.5vw,2.1rem);font-weight:520;letter-spacing:-.025em;line-height:1.2;margin:.65rem 0}.lede{max-width:760px;font-size:1.1rem;line-height:1.55;margin:12px 0}.inventory{color:var(--accent);font-size:.9rem;margin:14px 0 10px}.intro-note{color:var(--muted);font-size:.9rem;max-width:72ch;margin:10px 0}.gallery-toolbar{display:flex;flex-wrap:wrap;gap:18px;align-items:center;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:18px 0;margin-bottom:18px}.type-filters{display:flex;gap:7px}.type-filters span{font-size:.78rem;opacity:.7;margin-left:.3rem}.theme-filter{display:flex;align-items:center;gap:10px;color:var(--muted);margin-left:auto}#result-count{margin:0;color:var(--muted);font-size:.85rem;min-width:145px}.gallery{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 28px}.gallery-item{min-width:0;padding:36px 0;border-bottom:1px solid var(--line);scroll-margin-top:20px}.photo-section{grid-column:1/-1}.section-heading{max-width:850px;margin-bottom:22px}.section-heading p{color:var(--muted);max-width:80ch;margin:12px 0 0}.pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}.photo-card{background:var(--panel);min-width:0;padding:16px;border-radius:10px}.camera-badge{display:inline-block;font-size:.78rem;letter-spacing:.01em;font-weight:600;line-height:1.35;padding:7px 10px;border-radius:4px;margin:0 0 13px}.tilt-shift{color:#d9edc8;background:#344638}.standard{color:#d3e4ec;background:#34434b}.image-stack{position:relative}.image-stack>a{display:block}.image-stack img,video{display:block;width:100%;height:auto;background:#0b1011;border-radius:4px}.image-stack .focus-overlay{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;opacity:var(--guide-opacity,.45);image-rendering:pixelated;background:transparent}.settings{font-size:.86rem;color:var(--muted);margin:13px 0 8px}.asset-links{font-size:.85rem;line-height:1.8;margin:8px 0 12px}details{color:var(--muted);font-size:.85rem}summary{cursor:pointer;color:var(--ink);padding:5px 0}details p{max-width:85ch}.guide-controls{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:-4px 0 18px;padding:14px 16px;background:#202d26;border:1px solid #405946;border-radius:8px;font-size:.84rem}.guide-controls label{margin-left:8px}.guide-controls input{width:120px;accent-color:var(--accent)}.guide-controls output{width:3rem}.guide-controls span{color:var(--muted);font-size:.76rem}.guide-explanation{background:#202d26;border-left:3px solid #88c597;margin-top:18px;padding:4px 18px 14px;color:var(--muted);font-size:.9rem}.swatch{display:inline-block;background:#4cf3a3;width:1rem;height:.7rem;margin-right:.3rem}.video-media{background:var(--panel);padding:16px;border-radius:10px}.range{font-size:.95rem;color:var(--ink);font-variant-numeric:tabular-nums;margin:18px 0 8px}.range span{color:var(--accent);margin:0 .5rem}.technical-notes{margin:40px 0;border:1px solid var(--line);border-radius:8px;padding:18px 22px}.technical-notes>summary{font-size:1rem}footer{display:flex;justify-content:space-between;gap:20px;color:var(--muted);font-size:.77rem;padding:0 0 36px}#empty-state{padding:2rem 0;color:var(--muted)}@media(max-width:900px){main{padding:0 24px}.gallery-toolbar{gap:14px}.theme-filter{margin-left:0}#result-count{margin-left:auto}.gallery{gap:0 20px}.pair{gap:16px}.photo-card{padding:12px}}@media(max-width:650px){main{padding:0 16px}.hero{padding:28px 0 18px}h1{font-size:clamp(2.8rem,8vw,4rem)}.lede{font-size:1.05rem}.inventory{max-width:34ch}.gallery-toolbar{align-items:flex-start}.type-filters{width:100%}.theme-filter{width:100%;justify-content:space-between}#result-count{margin-left:0}.gallery{display:block}.pair{grid-template-columns:1fr;gap:18px}.gallery-item{padding:30px 0}.guide-controls{gap:10px}.guide-controls label{margin-left:0}.guide-controls button{width:100%;margin-bottom:4px}.guide-controls span{width:100%}.photo-card{padding:12px}.section-heading{margin-bottom:18px}footer{display:block}.technical-notes{padding:14px 16px}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
'''

SCRIPT = '''
const items=[...document.querySelectorAll('.gallery-item')];
let kind='all';
const theme=document.querySelector('#theme');
function filter(){let count=0;items.forEach(item=>{item.hidden=!(kind==='all'||item.dataset.kind===kind)||!(theme.value==='all'||item.dataset.theme===theme.value);if(!item.hidden){count++;}else{item.querySelectorAll('video').forEach(video=>video.pause());}});document.querySelector('#result-count').textContent=count+' demonstration'+(count===1?'':'s');document.querySelector('#empty-state').hidden=count!==0;}
document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{kind=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(other=>other.setAttribute('aria-pressed',String(other===button)));filter();}));theme.addEventListener('change',filter);
document.querySelectorAll('.guide-toggle').forEach(button=>{const section=button.closest('section');button.addEventListener('click',()=>{const on=button.getAttribute('aria-pressed')!=='true';button.setAttribute('aria-pressed',String(on));button.textContent=on?'Hide focus planes':'Show focus planes';section.querySelector('.guide-explanation').hidden=!on;section.querySelectorAll('.focus-overlay').forEach(image=>image.hidden=!on);});const slider=section.querySelector('.guide-opacity');slider.addEventListener('input',()=>{section.style.setProperty('--guide-opacity',slider.value/100);section.querySelector('output').value=slider.value+'%';});});
document.querySelectorAll('video').forEach(video=>video.addEventListener('play',()=>document.querySelectorAll('video').forEach(other=>{if(other!==video)other.pause();})));
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--photos', type=Path, default=PHOTO_DEFAULT)
    parser.add_argument('--videos', type=Path, default=VIDEO_DEFAULT)
    parser.add_argument('--output', type=Path, default=GALLERY_DEFAULT)
    args = parser.parse_args()
    build_gallery(args.photos, args.videos, args.output)


if __name__ == '__main__':
    main()
