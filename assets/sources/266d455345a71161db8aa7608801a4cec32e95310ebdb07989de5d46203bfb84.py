# SPDX-License-Identifier: GPL-3.0-or-later
"""Label verified native-camera PNG frames, encode exact-duration MP4s and gallery.

Run with ordinary Python and Pillow, ffmpeg and ffprobe. Raw renders stay intact;
the only image-space operation is the visible setting/value corner annotation.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def write_json(path, record):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(record, indent=2)+'\n')
    temporary.replace(path)


def label_text(record, frame):
    config = record['configuration']
    spec, value = config['spec'], frame['value']
    if config['clip'] in ('shift-x', 'shift-y'):
        return f"{spec['label']}  {frame['shift_mm']:+.2f} mm  ({value:+.3f})"
    if spec['unit'] == 'deg':
        formatted = f'{value:+.1f}°'
    elif spec['unit'] == 'f/':
        formatted = f'f/{value:.2f}'
    elif spec['unit'] == 'm':
        formatted = f'{value:.3f} m'
    else:
        formatted = f"{value:.2f} {spec['unit']}"
    return f"{spec['label']}  {formatted}"


def font_at_size(size):
    for path in ('/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(path).exists():
            return ImageFont.truetype(path, size), path
    # Pillow supplies a scalable default font in current versions.
    return ImageFont.load_default(size=size), 'Pillow default'


def encode(directory):
    manifest = directory/'animation.json'
    record = json.loads(manifest.read_text())
    config = record['configuration']
    clip, fps = config['clip'], config['fps']
    if digest(directory/(clip+'.blend')) != record['blend_sha256']:
        raise ValueError(f'{clip}: animated scene changed')
    width, height = config['resolution']
    if width % 2 or height % 2:
        raise ValueError('yuv420p encoding requires even image dimensions')
    frames = record['frames']
    if len(frames) != config['frames'] or [frame['frame'] for frame in frames] != list(range(1, len(frames)+1)):
        raise ValueError(f'{clip}: frame sequence is incomplete or unordered')
    if len(frames)/fps != record['duration_s']:
        raise ValueError(f'{clip}: frame count does not match exact duration')
    # Verify every input before writing any labels or invoking the encoder.
    for frame in frames:
        path = directory/'raw'/f"frame-{frame['frame']:04d}.png"
        if 'render' not in frame or not path.exists() or digest(path) != frame['render']['sha256']:
            raise ValueError(f'{clip}: missing, changed or unrecorded raw frame {frame["frame"]}')
    labeled = directory/'labeled'
    labeled.mkdir(exist_ok=True)
    font, font_path = font_at_size(max(16, round(height*24/540)))
    labels = []
    for frame in frames:
        filename = f"frame-{frame['frame']:04d}.png"
        with Image.open(directory/'raw'/filename) as source:
            if source.size != (width, height):
                raise ValueError(f'{clip}: unexpected frame dimensions')
            image = source.convert('RGB')
        text = label_text(record, frame)
        draw = ImageDraw.Draw(image)
        x, y, padding = round(width*16/960), round(height*16/540), max(6, round(height*10/540))
        box = draw.textbbox((0, 0), text, font=font)
        text_height, text_width = box[3]-box[1], box[2]-box[0]
        # Top-left placement avoids the workbench's foreground details.
        draw.rounded_rectangle((x, y, x+text_width+2*padding, y+text_height+2*padding), radius=5, fill=(15, 19, 21))
        draw.text((x+padding-box[0], y+padding-box[1]), text, font=font, fill=(250, 250, 246))
        target = labeled/filename
        image.save(target)
        labels.append(dict(frame=frame['frame'], text=text, sha256=digest(target)))
    video = directory/(clip+'.mp4')
    temporary = directory/(clip+'.encoding.mp4')
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-y', '-framerate', str(fps),
               '-start_number', '1', '-i', str(labeled/'frame-%04d.png'), '-frames:v', str(len(frames)),
               '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p',
               '-r', str(fps), '-movflags', '+faststart', str(temporary)]
    subprocess.run(command, check=True)
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames',
                         '-show_entries', 'stream=codec_name,width,height,pix_fmt,r_frame_rate,nb_read_frames,duration',
                         '-of', 'json', str(temporary)], text=True))
    stream = probe['streams'][0]
    if (stream['width'], stream['height']) != (width, height) or int(stream['nb_read_frames']) != len(frames):
        raise ValueError('Encoded dimensions or frame count differ from source')
    if abs(float(stream['duration'])-record['duration_s']) > 1e-6 or stream['pix_fmt'] != 'yuv420p':
        raise ValueError('Encoded duration or pixel format differs from requested settings')
    if stream['r_frame_rate'] != f'{fps}/1' or stream['codec_name'] != 'h264':
        raise ValueError('Encoded rate or codec differs from requested settings')
    temporary.replace(video)
    encoding = dict(schema=1, configuration_sha256=record['configuration_sha256'],
                    animation_manifest_sha256=digest(manifest), encoder_sha256=digest(__file__),
                    video_sha256=digest(video), label_font=font_path, labels=labels,
                    ffmpeg_command=command, ffmpeg_version=subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0],
                    ffprobe=probe, image_operation='RGB display conversion and corner label only; raw renders preserved')
    write_json(directory/'encoding.json', encoding)
    print(f'ENCODED {clip}: {len(frames)} frames, {fps} fps, {record["duration_s"]} s', flush=True)


def gallery(output):
    cards = []
    order = ['tilt', 'swing', 'axis', 'shift-x', 'shift-y', 'focus', 'lens', 'fstop']
    for name in order:
        directory = output/name
        if not (directory/'encoding.json').exists():
            continue
        record = json.loads((directory/'animation.json').read_text())
        encoded = json.loads((directory/'encoding.json').read_text())
        if (encoded['animation_manifest_sha256'] != digest(directory/'animation.json')
                or encoded['video_sha256'] != digest(directory/(name+'.mp4'))):
            raise ValueError(f'{name}: stale encoding/gallery artifacts')
        if encoded['labels'][0]['sha256'] != digest(directory/'labeled/frame-0001.png'):
            raise ValueError(f'{name}: gallery poster changed')
        spec = record['configuration']['spec']
        first, last = record['frames'][0], record['frames'][-1]
        start, end = label_text(record, first), label_text(record, last)
        configuration = record['configuration']
        details = (f"{record['range_kind']}; {record['duration_s']} s, {configuration['fps']} fps, "
                   f"{configuration['resolution'][0]} × {configuration['resolution'][1]}, "
                   f"{configuration['samples']} samples, seed {configuration['seed']}.")
        cards.append(f'''<section><h2>{html.escape(spec['label'])}</h2>
<video controls playsinline preload="metadata" poster="{name}/labeled/frame-0001.png" aria-label="{html.escape(spec['label'])} animation"><source src="{name}/{name}.mp4" type="video/mp4"></video>
<p>{html.escape(start)} → {html.escape(end)}</p><p class="small">{html.escape(details)}</p>
<p><a href="{name}/{name}.mp4" download>MP4</a> · <a href="{name}/{name}.blend">Animated Blender scene</a> · <a href="{name}/animation.json">Frame values / optical checks</a> · <a href="{name}/encoding.json">Encoding audit</a></p></section>''')
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Native camera / photographic controls in motion</title><style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#14191d;color:#e8e8df;font:17px/1.5 system-ui,sans-serif}main{max-width:1240px;margin:auto;padding:32px 24px}h1{font-size:clamp(26px,4vw,42px);line-height:1.15}h2{font-size:23px}a{color:#a8d8e8}section{padding:24px 0;border-top:1px solid #42505a}video{display:block;width:100%;height:auto;background:#080b0e;border-radius:6px}p{max-width:90ch}.small,footer{color:#afbcc4;font-size:15px}a:focus-visible,video:focus-visible{outline:3px solid #f8df8a;outline-offset:4px}@media(min-width:1000px){.clips{display:grid;grid-template-columns:1fr 1fr;gap:24px}section{min-width:0}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style><main><h1>Native camera controls in motion</h1>
<p>Watch one photographic setting change while the camera pose, scene and lighting stay fixed. Each frame is a fresh Cycles render through the native tilted lens and finite aperture. Play each clip individually; the corner label reports its current evaluated setting.</p>
<p>These are representative finite photographic ranges. The movement-axis clip covers its full −180° to +180° cycle with −10° tilt. Other controls can permit wider values depending on lens, focus, sensor, clipping and ray validity; these clips do not claim to cover every valid configuration.</p>
<p>Tilt and swing each keep the other angle at zero. Axis rotation, focus, focal length and aperture retain −10° tilt. The architectural shift clips keep their level pose and zero lens angles; their labels show lens-centre displacement in millimetres and normalized sensor-width shift. The 36 mm sensor makes ±0.5 shift equal ±18 mm.</p>
<p>Focus, focal length, shift and aperture are also available in ordinary Cycles. Aperture changes use evenly spaced exposure stops; these geometric optics renders do not simulate diffraction, shutter exposure or sensor noise. There is no image-space blur, interpolation between rendered frames, motion blur, adaptive sampling or denoising. Only the corner label is added after rendering.</p>
<div class="clips">'''+''.join(cards)+'''</div><footer><p>Raw PNG frames and CPU-portable animated scenes remain beside each clip. The manifests distinguish evaluated-guide and guard-mirror preflight from the native Cycles gate exercised by each actual render. Local demonstration artifacts, GPL-3.0-or-later; not published.</p></footer></main></html>'''
    (output/'index.html').write_text(document)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'work/demo-animations/960x540')
    parser.add_argument('--clip', action='append', choices=['all', 'tilt', 'swing', 'axis', 'shift-x', 'shift-y', 'focus', 'lens', 'fstop'])
    parser.add_argument('--gallery-only', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT/'work'):
        raise ValueError('Generated artifacts must stay below ignored work/')
    if not args.gallery_only:
        selected = ['tilt', 'swing', 'axis', 'shift-x', 'shift-y', 'focus', 'lens', 'fstop'] if not args.clip or 'all' in args.clip else list(dict.fromkeys(args.clip))
        for name in selected:
            encode(output/name)
    gallery(output)


if __name__ == '__main__':
    main()
