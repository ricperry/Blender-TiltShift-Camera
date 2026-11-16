# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable packaging checks with tiny deterministic artifacts; no Blender needed."""
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'examples'))
import build_demo_gallery as gallery
import export_demo_gallery as exporter


class URLs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = []

    def handle_starttag(self, tag, attrs):
        self.values.extend(value for key, value in attrs if key in ('href', 'src', 'poster'))


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.photos = self.root / 'work/photos'
        self.videos = self.root / 'work/videos'
        self.output = self.root / 'work/site'
        self.photos.mkdir(parents=True)
        self.videos.mkdir()
        (self.root / 'examples').mkdir()
        (self.root / 'LICENSE').write_text('GPL-3.0-or-later fixture')
        self.patches = [
            patch.object(gallery, 'ROOT', self.root),
            patch.object(gallery, 'GALLERY_DEFAULT', self.root / 'work/local-gallery'),
            patch.object(gallery, 'PAIRS', gallery.PAIRS[:1]),
            patch.object(gallery, 'CLIPS', gallery.CLIPS[:1]),
            patch.object(exporter, 'GUIDED_PAIRS', {'table-native--table-ordinary-best'}),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        generator = self.photos / 'render-generator-source.py'
        generator.write_text('# captured fixture source\n')
        helper = self.photos / 'focus-overlay-source.py'
        helper.write_text('# captured focus source\n')
        self.write_json(self.photos / 'focus-guides.json', {
            'helper_sha256': gallery.digest(helper),
            'cases': ['table-native', 'table-ordinary-best'],
            'pairs': {'table-native--table-ordinary-best': True},
        })
        for name in ('table-native', 'table-ordinary-best'):
            image, scene = (self.photos / f'{name}.{extension}' for extension in ('png', 'blend'))
            image.write_bytes(b'original image fixture')
            scene.write_bytes(b'original scene fixture')
            manifest = self.photos / f'{name}.json'
            self.write_json(manifest, {
                'image_sha256': gallery.digest(image), 'blend_sha256': gallery.digest(scene),
                'source_sha256': gallery.digest(generator), 'resolution': [3840, 2160],
                'native_enabled': name == 'table-native', 'samples': 256, 'seed': 71,
                'camera': {'focus_object': None, 'focus_distance_m': 1.5, 'lens_mm': 50,
                           'fstop': 2.8, 'tilt_deg': -10, 'swing_deg': 0, 'axis_deg': 0,
                           'shift': [0, 0], 'sensor_width_mm': 36, 'pupil_diameter_m': .018},
            })
            mask, surface = (self.photos / f'{name}.{extension}'
                             for extension in ('focus.png', 'focus-surface.f32.z'))
            mask.write_bytes(b'original overlay fixture')
            surface.write_bytes(b'original surface fixture')
            self.write_json(self.photos / f'{name}.focus.json', {
                'source': {'helper_sha256': gallery.digest(helper),
                           'image_sha256': gallery.digest(image),
                           'blend_sha256': gallery.digest(scene),
                           'manifest_sha256': gallery.digest(manifest)},
                'mask_file': mask.name, 'mask_sha256': gallery.digest(mask),
                'surface_file': surface.name, 'surface_sha256': gallery.digest(surface),
                'plane_visual_half_width_m': .004,
            })
        folder = self.videos / 'tilt'
        (folder / 'labeled').mkdir(parents=True)
        sources = self.videos / 'sources'
        sources.mkdir()
        hashes = {}
        for name in ('create_demo_animations.py', 'create_demo_comparisons.py', 'encode_demo_animations.py'):
            source = sources / name
            source.write_text('# captured ' + name)
            hashes[name] = gallery.digest(source)
        for name in ('tilt.mp4', 'tilt.blend', 'labeled/frame-0001.png'):
            (folder / name).write_bytes(('original ' + name).encode())
        self.write_json(folder / 'animation.json', {
            'blend_sha256': gallery.digest(folder / 'tilt.blend'), 'duration_s': 10,
            'frames': [{'value': -10}, {'value': 10}], 'range_kind': 'fixture range',
            'configuration': {'clip': 'tilt', 'spec': {'unit': 'deg'}, 'resolution': [960, 540],
                              'fps': 5, 'samples': 256, 'seed': 71,
                              'generator_sha256': hashes['create_demo_animations.py'],
                              'helper_sha256': hashes['create_demo_comparisons.py']},
        })
        self.write_json(folder / 'encoding.json', {
            'animation_manifest_sha256': gallery.digest(folder / 'animation.json'),
            'video_sha256': gallery.digest(folder / 'tilt.mp4'),
            'encoder_sha256': hashes['encode_demo_animations.py'],
            'labels': [{'sha256': gallery.digest(folder / 'labeled/frame-0001.png')}],
        })
        # Deliberate unrelated artifacts must not enter the publication.
        (self.photos / 'personal.png').write_bytes(b'private fixture')
        (folder / 'labeled/frame-0002.png').write_bytes(b'unpublished frame')
        (self.photos / 'index.html').write_text('original redirect')

    @staticmethod
    def write_json(path, value):
        path.write_text(json.dumps(value))

    def export(self):
        return exporter.export_gallery(self.photos, self.videos, self.output)

    def test_portable_urls_inventory_and_byte_preservation(self):
        before = {path: gallery.digest(path) for path in (self.root / 'work').rglob('*') if path.is_file()}
        document = self.export().read_text()
        self.assertNotIn('Local demonstration', document)
        self.assertNotIn('This gallery is not published', document)
        urls = URLs()
        urls.feed(document)
        for value in urls.values:
            parts = urlsplit(value)
            if parts.scheme:
                self.assertEqual(parts.netloc, 'github.com')
                continue
            if not parts.path:
                continue
            self.assertFalse(parts.path.startswith('/'))
            target = (self.output / unquote(parts.path)).resolve()
            self.assertTrue(target.is_relative_to(self.output))
            self.assertTrue(target.is_file(), value)
        manifest = gallery.read_json(self.output / 'publication-manifest.json')
        paths = {entry['path'] for entry in manifest['files']}
        self.assertEqual(paths, {p.relative_to(self.output).as_posix()
                                 for p in self.output.rglob('*') if p.is_file()} - {'publication-manifest.json'})
        self.assertEqual(manifest['counts']['blender_scenes'], 3)
        for entry in manifest['files']:
            target = self.output / entry['path']
            self.assertEqual(gallery.digest(target), entry['sha256'])
            self.assertEqual(target.stat().st_size, entry['bytes'])
            if 'source' in entry:
                self.assertEqual(gallery.digest(self.root / entry['source']), entry['sha256'])
        self.assertFalse(any('personal' in path or 'frame-0002' in path for path in paths))
        for path, expected in before.items():
            self.assertEqual(gallery.digest(path), expected)

    def test_missing_video_fails_without_partial_output(self):
        (self.videos / 'tilt/encoding.json').unlink()
        with self.assertRaisesRegex(ValueError, 'every active'):
            self.export()
        self.assertFalse(self.output.exists())

    def test_local_builder_keeps_relative_links_and_compatibility_redirects(self):
        output = self.root / 'work/local-gallery'
        document = gallery.build_gallery(self.photos, self.videos, output).read_text()
        self.assertIn('Local demonstration', document)
        self.assertIn('This gallery is not published', document)
        self.assertIn('../../examples/DEMO_GALLERY.md', document)
        for source in (self.photos, self.videos):
            self.assertIn('../local-gallery/index.html', (source / 'index.html').read_text())

    def test_changed_media_fails_without_partial_output(self):
        (self.photos / 'table-native.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Missing or changed'):
            self.export()
        self.assertFalse(self.output.exists())

    def test_existing_or_overlapping_output_is_preserved(self):
        for output in (self.photos, self.photos / 'site', self.root / 'work',
                       self.root / 'work/local-gallery/nested'):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, 'overlap'):
                exporter.export_gallery(self.photos, self.videos, output)
        self.output.mkdir()
        sentinel = self.output / 'keep.txt'
        sentinel.write_text('preserve')
        with self.assertRaisesRegex(ValueError, 'new directory'):
            self.export()
        self.assertEqual(sentinel.read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()
