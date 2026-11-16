# SPDX-License-Identifier: GPL-3.0-or-later
"""Export the complete verified gallery as a portable GitHub Pages directory.

Copies explicit dependencies only, without rendering, encoding or changing the
source artifacts. The output must be a fresh directory below ignored work/.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import tempfile

import build_demo_gallery as gallery

OUTPUT_DEFAULT = gallery.ROOT / 'work/demo-gallery-public'
PUBLIC_URL = 'https://ricperry.github.io/Blender-TiltShift-Camera/'
GUIDED_PAIRS = {
    'table-native--table-ordinary-best', 'table-native--table-ordinary-f16',
    'swing-native--swing-ordinary-best', 'axis-native--axis-ordinary-best',
    'city-native--city-ordinary-best', 'city-native--city-ordinary-blur-fit',
}


def export_gallery(photos=gallery.PHOTO_DEFAULT, videos=gallery.VIDEO_DEFAULT,
                   output=OUTPUT_DEFAULT):
    photos, videos, output = map(gallery.below_work, (photos, videos, output))
    for source in (photos, videos, gallery.GALLERY_DEFAULT.resolve()):
        if output.is_relative_to(source) or source.is_relative_to(output):
            raise ValueError('Portable output must not overlap source or local gallery directories')
    if output.exists():
        raise ValueError('Portable output must be a new directory; preserve or move the previous export')
    photo_records = gallery.load_photos(photos)
    guides, guide_pairs = gallery.load_guides(photos)
    video_records = gallery.load_videos(videos)
    expected_photos = {name for pair in gallery.PAIRS for name in pair[2:4]}
    expected_videos = {clip[0] for clip in gallery.CLIPS}
    if set(photo_records) != expected_photos or set(video_records) != expected_videos:
        raise ValueError('Public gallery requires every active photograph and video')
    if {key for key, enabled in guide_pairs.items() if enabled} != GUIDED_PAIRS:
        raise ValueError('Public gallery requires all six verified focus-plane pairs')
    expected_guides = {name for pair in GUIDED_PAIRS for name in pair.split('--')}
    if set(guides) != expected_guides:
        raise ValueError('Public gallery requires every focus-plane source and mask')

    # Destination -> (source, digest). No directory globs or recursive work/ copy.
    dependencies = {}

    def add(source, destination):
        source = source.resolve()
        if not source.is_file():
            raise ValueError(f'Missing publication dependency: {source}')
        dependencies[Path(destination)] = (source, gallery.digest(source))

    def captured_source(candidates, expected, destination):
        for candidate in candidates:
            if candidate.is_file() and gallery.digest(candidate) == expected:
                add(candidate, destination)
                return
        raise ValueError(f'Missing captured publication source with SHA-256 {expected}')

    for name, record in photo_records.items():
        for extension in ('png', 'blend', 'json'):
            add(photos / f'{name}.{extension}', f'assets/photos/{name}.{extension}')
        captured_source(
            [photos / 'render-generator-source.py', photos / 'grid-render-generator-source.py',
             gallery.ROOT / 'examples/create_demo_comparisons.py'],
            record['source_sha256'], f'assets/sources/{record["source_sha256"]}.py')
    add(photos / 'focus-guides.json', 'assets/photos/focus-guides.json')
    summary = gallery.read_json(photos / 'focus-guides.json')
    captured_source([photos / 'focus-overlay-source.py', gallery.ROOT / 'examples/demo_focus_overlays.py'],
                    summary['helper_sha256'], 'assets/photos/focus-overlay-source.py')
    for name, record in guides.items():
        add(photos / f'{name}.focus.json', f'assets/photos/{name}.focus.json')
        for field in ('mask_file', 'surface_file'):
            add(photos / record[field], 'assets/photos/' + record[field])
    for name, record in video_records.items():
        folder = videos / name
        for filename in (f'{name}.mp4', f'{name}.blend', 'labeled/frame-0001.png',
                         'animation.json', 'encoding.json'):
            add(folder / filename, f'assets/videos/{name}/{filename}')
        encoded = gallery.read_json(folder / 'encoding.json')
        for filename, expected in (
                ('create_demo_animations.py', record['configuration']['generator_sha256']),
                ('create_demo_comparisons.py', record['configuration']['helper_sha256']),
                ('encode_demo_animations.py', encoded['encoder_sha256'])):
            captured_source([videos / 'sources' / filename, gallery.ROOT / 'examples' / filename], expected,
                            f'assets/sources/{expected}.py')
    add(gallery.ROOT / 'LICENSE', 'LICENSE')

    output.parent.mkdir(parents=True, exist_ok=True)
    # An incomplete export never appears at the requested publication path.
    with tempfile.TemporaryDirectory(prefix='.gallery-export-', dir=output.parent) as temporary:
        staging = Path(temporary) / 'site'
        staging.mkdir()
        for destination, (source, expected) in sorted(dependencies.items()):
            target = (staging / destination).resolve()
            if not target.is_relative_to(staging):
                raise ValueError('Publication dependency escapes export directory')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            gallery.verify(target, expected)
        gallery.build_gallery(staging / 'assets/photos', staging / 'assets/videos',
                              staging, public=True)
        (staging / '.nojekyll').write_text('')
        entries = []
        for path in sorted(staging.rglob('*')):
            if path.is_file():
                relative = path.relative_to(staging)
                entry = {'path': relative.as_posix(), 'bytes': path.stat().st_size,
                         'sha256': gallery.digest(path)}
                if relative in dependencies:
                    entry['source'] = dependencies[relative][0].relative_to(gallery.ROOT).as_posix()
                entries.append(entry)
        manifest = {
            'schema': 1, 'public_url': PUBLIC_URL, 'license': 'GPL-3.0-or-later',
            'counts': {'photographs': len(photo_records), 'comparisons': len(gallery.PAIRS),
                       'videos': len(video_records), 'focus_plane_pairs': len(GUIDED_PAIRS),
                       'blender_scenes': len(photo_records) + len(video_records)},
            'inventory': {'files_excluding_manifest': len(entries),
                          'bytes_excluding_manifest': sum(entry['bytes'] for entry in entries),
                          'extensions': dict(sorted(Counter(Path(e['path']).suffix for e in entries).items()))},
            'scope': 'Byte-identical active media, scenes and provenance; no raw animation frames except posters. '
                     'Source JSON retains original render-time paths and frame hashes as provenance, not site URLs.',
            'files': entries,
        }
        (staging / 'publication-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        # A fresh output path also prevents stale or personal files being published.
        if output.exists():
            raise ValueError('Portable output appeared during export; leaving it untouched')
        staging.rename(output)
    print(f'Portable gallery: {output} ({len(entries) + 1} files)')
    return output / 'index.html'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--photos', type=Path, default=gallery.PHOTO_DEFAULT)
    parser.add_argument('--videos', type=Path, default=gallery.VIDEO_DEFAULT)
    parser.add_argument('--output', type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    export_gallery(args.photos, args.videos, args.output)


if __name__ == '__main__':
    main()
