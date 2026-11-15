#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate Blender's expected sticky-error exit using a fresh guard result set.

Pinned Blender exits 1 after reported render-engine errors even when Python
catches the expected RuntimeErrors. Success therefore requires both this exact
exit and complete, freshly generated, hash-matched rejection evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from dev import ENV, PIN, ROOT

EXPECTED = {
    'invalid-focus': 'singular sensor',
    'near-aperture': 'clip planes',
    'motion-blur': 'motion blur',
    'motion-pass': 'motion',
    'orthographic': 'perspective',
    'multiview': 'stereo',
    'adaptive-subdivision': 'adaptive subdivision',
    'adaptive-dicing-camera': 'adaptive subdivision',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'work'):
        raise ValueError('Guard artifacts must be below ignored work/')
    output.mkdir(parents=True, exist_ok=True)
    # A unique directory prevents any older result from satisfying this run.
    folder = Path(tempfile.mkdtemp(prefix='guards-', dir=output))
    paths = dict(binary_sha256=args.blender.resolve(),
                 fixture_script_sha256=ROOT / 'scripts/blender_m2_validation.py',
                 patch_sha256=ROOT / 'patches/blender-v5.3.0-tilt-shift.patch')
    provenance = {key: digest(path) for key, path in paths.items()}
    for name in ('BLENDER_USER_RESOURCES', 'BLENDER_USER_CONFIG', 'BLENDER_USER_EXTENSIONS',
                 'BLENDER_USER_SCRIPTS', 'BLENDER_USER_DATAFILES', 'XDG_CACHE_HOME'):
        Path(ENV[name]).mkdir(parents=True, exist_ok=True)
    command = [str(paths['binary_sha256']), '--background', '-noaudio', '--factory-startup',
               '--python-exit-code', '1', '--python', str(paths['fixture_script_sha256']), '--',
               '--output', str(folder), '--case', 'guards']
    log = folder / 'blender.log'
    with log.open('w') as stream:
        result = subprocess.run(command, env=ENV, stdout=stream, stderr=subprocess.STDOUT,
                                timeout=180, check=False)
    if result.returncode != 1:
        raise RuntimeError(f'Expected pinned Blender guard exit 1; got {result.returncode}; {log}')
    data_path = folder / 'guards-results.json'
    if not data_path.is_file():
        raise RuntimeError(f'No fresh complete guard JSON; inspect {log}')
    data = json.loads(data_path.read_text())
    if data['source_pin'] != PIN:
        raise RuntimeError('Unexpected guard source pin')
    for key, path in paths.items():
        if data[key] != provenance[key] or digest(path) != provenance[key]:
            raise RuntimeError(f'Guard provenance mismatch: {path}')
    records = data['results']
    if len(records) != len(EXPECTED) or {item['name'] for item in records} != set(EXPECTED):
        raise RuntimeError('Incomplete or unexpected guard result set')
    for item in records:
        if (item.get('rejected') is not True or
                'Physical Tilt-Shift:' not in item.get('error', '') or
                EXPECTED[item['name']] not in item['error']):
            raise RuntimeError(f'Wrong or missing explicit rejection: {item}')
    summary = dict(status='passed', blender_exit_code=result.returncode,
                   explanation='Pinned Blender retains expected render-engine errors at process exit',
                   fresh_guard_results=str(data_path.relative_to(ROOT)),
                   guard_results_sha256=digest(data_path),
                   host_runner_sha256=digest(Path(__file__)),
                   expected_rejections=list(EXPECTED), **provenance)
    (output / 'guards-host-results.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
