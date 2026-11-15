#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare M4 same-executable CPU/HIP linear buffers using fixed acceptance bounds.

Bounds are declared before hardware execution. Unit-emission/coverage fixtures
use 32--1024 samples: a rare edge decision can move one or two 1/32 samples.
An RGB RMSE .003 and maximum 2/samples therefore bound image-wide and isolated
edge error separately (.0625 only for 32-sample coverage). Constant unit-world
boundaries use 2e-4 for both instead.
These are implementation parity bounds, not photographic accuracy claims.
"""
import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import sys

LIMITS = dict(default=dict(rmse=.003, max_abs_rule='max(0.0002, 2 / samples)'),
              boundary=dict(rmse=.0002, max_abs=.0002))
OPTICS = {
    'disabled-centroid','physical-centroid','physical-shift','vertical-fit',
    'pixel-aspect','offaxis-focus-object','untilted-coc','scheimpflug-sharp',
    'scheimpflug-untilted','shifted-world-window','coverage-untilted',
    'coverage-tilted','tilted-aperture-volume','tilted-aperture-clips',
    'boundary-sensor','boundary-near-aperture','combined-movements',
}
SUITES = dict(optics=OPTICS, **{'optics-texture':OPTICS|{'large-filter-chart'},
                              'full':OPTICS|{'large-filter-chart','physical-focus-chart'}})
PROVENANCE = ('binary_sha256','fixture_script_sha256','immutable_m2_script_sha256',
              'immutable_visual_script_sha256','patch_sha256','source_pin','hip_kernel_sha256')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def buffers(folder):
    found = {}
    for path in sorted(folder.glob('*-results.json')):
        data = json.loads(path.read_text())
        def visit(item):
            if 'pixels_sha256' in item:
                if item['name'] in found:
                    raise ValueError('Duplicate render record: '+item['name'])
                found[item['name']] = (item, data)
            for child in item.get('renders', []):
                visit(child)
        for item in data['results']:
            visit(item)
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cpu', type=Path)
    parser.add_argument('hip', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--suite', choices=tuple(SUITES), default='full',
                        help='Require exactly the named render set; full acceptance requires 19')
    args = parser.parse_args()
    first, second = buffers(args.cpu), buffers(args.hip)
    if set(first) != SUITES[args.suite] or set(second) != SUITES[args.suite]:
        raise ValueError('Both folders must contain exactly the required '+args.suite+' render set')
    provenance = {key:next(iter(first.values()))[1][key] for key in PROVENANCE}
    for _,metadata in (*first.values(),*second.values()):
        if any(metadata.get(key) != value for key,value in provenance.items()):
            raise ValueError('Global provenance differs across cases or backends')
    results = []
    for name in first:
        (a, am), (b, bm) = first[name], second[name]
        if am['backend'] != 'cpu' or bm['backend'] != 'hip':
            raise ValueError('Expected hard CPU and HIP evidence')
        for key in PROVENANCE:
            if am.get(key) != bm.get(key):
                raise ValueError('Provenance differs: '+key)
        for key in ('width','height','samples','seed','adaptive_sampling','denoising','camera_enabled',
                    'camera_settings','raster_settings'):
            if a[key] != b[key]:
                raise ValueError('Render settings differ: '+key)
        if a['adaptive_sampling'] or a['denoising']:
            raise ValueError('Unexpected adaptive sampling or denoising')
        values = []
        for folder, item, metadata in ((args.cpu,a,am),(args.hip,b,bm)):
            path = folder/(name+'.rgba32f')
            if digest(path) != item['pixels_sha256']:
                raise ValueError('Buffer digest mismatch: '+str(path))
            data = array.array('f')
            with path.open('rb') as stream:
                data.fromfile(stream,item['width']*item['height']*4)
                if stream.read(1):
                    raise ValueError('Unexpected trailing buffer data')
            if sys.byteorder != metadata['byteorder']:
                data.byteswap()
            if not all(math.isfinite(x) for x in data):
                raise ValueError('Nonfinite buffer')
            values.append(data)
        errors = [abs(x-y) for i,(x,y) in enumerate(zip(*values)) if i%4 != 3]
        rmse = math.sqrt(sum(x*x for x in errors)/len(errors))
        maximum = max(errors)
        limits = (LIMITS['boundary'] if name.startswith('boundary-') else
                  dict(rmse=LIMITS['default']['rmse'], max_abs=max(.0002,2/a['samples'])))
        results.append(dict(name=name, rmse_rgb=rmse, max_abs_rgb=maximum,
                            limits=limits, passed=rmse<=limits['rmse'] and maximum<=limits['max_abs'],
                            bitwise=values[0].tobytes()==values[1].tobytes(),
                            cpu_pixels_sha256=a['pixels_sha256'],hip_pixels_sha256=b['pixels_sha256']))
    summary = dict(status='passed' if all(x['passed'] for x in results) else 'failed',
                   suite=args.suite, required_render_names=sorted(SUITES[args.suite]),
                   global_provenance=provenance, comparator_sha256=digest(Path(__file__)),
                   predeclared_limits=LIMITS, results=results)
    args.output.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    if summary['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
