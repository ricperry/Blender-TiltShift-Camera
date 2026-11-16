<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Tilt-shift photographic controls in motion

[The Blender generator](create_demo_animations.py) makes eight editable tilt-shift
camera animations from the verified saved comparison scenes. The default is
**10 seconds, 960 × 540, 5 fps, 50 independently rendered frames per clip**,
with 256 samples per frame by default.
Every frame changes a real camera property used by the tilt-shift Cycles lens model.
There is no image-space blur or interpolation between rendered images.

The [encoder](encode_demo_animations.py) adds the setting name and current
evaluated value in the top-left corner, preserves the raw PNGs, and produces
H.264/yuv420p MP4s with fast-start metadata. The shared photo/video gallery has individual
playback controls and starts with every clip paused. Generated files remain
under ignored `work/demo-animations/`; the input scenes and user images stay intact.

## Clips and finite ranges

| Clip | Animated property | Delivered / recommended range | Other lens movements |
| --- | --- | --- | --- |
| `tilt` | Lens tilt | −20° to +20° | Swing and axis zero |
| `swing` | Lens swing | −20° to +20° | Tilt and axis zero |
| `axis` | Movement-axis rotation | −180° to +180° | Tilt −10°, swing zero |
| `shift-x` | Horizontal shift | −0.5 to +0.5, equivalent to −18 to +18 mm | Level architectural camera; tilt, swing, vertical shift zero |
| `shift-y` | Vertical shift | −0.1 to +0.2, equivalent to −3.6 to +7.2 mm | Level architectural camera; tilt, swing, horizontal shift zero |
| `focus` | Manual focus distance | 1.0 to 2.2 m | Tilt −10°, swing and axis zero |
| `lens` | Focal length | 35 to 135 mm | Tilt −10°, swing and axis zero |
| `fstop` | Aperture f-number | f/1 to f/32, logarithmic | Tilt −10°, swing and axis zero |

These are **representative photographic ranges**, except for the movement axis,
which covers its full RNA cycle. They are not the full valid domains of all
camera controls. Some controls have effectively unbounded or scene-dependent
valid ranges; extreme values can lose the subject, cross a focus singularity or
violate the tilt-shift ray/clip guards. Polygon shape/rotation, anamorphic aperture
ratio and image-circle coverage are outside this animation suite.

The recommended ranges use [demo_animation_ranges.json](demo_animation_ranges.json).
It narrows vertical shift to keep the architecture visible: the broader −0.5
endpoint points into empty foreground, and +0.5 shows mostly sky. The bare
generator retains −0.5 to +0.5 for both shift controls; pass the ranges file in
the commands below to reproduce the recommended suite. The other seven ranges
are unchanged.

Camera pose, scene geometry and lighting remain fixed within each clip. Only its
listed property has animation channels. Tilt/swing reset the sibling lens angles;
focus, focal length and aperture retain the product scene's −10° tilt. The axis
clip needs that nonzero tilt to make the axis change visible. The product clips
reuse the printed-grid `table-native.blend`; shift clips reuse their respective
level architectural tilt-shift scenes. These are photographic demonstrations, not
additional optical acceptance tests.

Shift, focal length, focus and aperture also exist in ordinary Cycles. The tilt-shift
model couples finite sensor distance, physical lens movement and finite-aperture
rays. The ideal geometric optics model does not simulate diffraction, exposure,
shutter speed or sensor noise. Aperture values are evenly spaced in exposure
stops; every other control is sampled linearly, including both range endpoints.

## Reproduce

First generate the comparison inputs as described in
[DEMO_COMPARISONS.md](DEMO_COMPARISONS.md). The animation generator requires each
source `.blend` and PNG to match its JSON hashes and requires a captured
render-generator snapshot matching that source's provenance. It never saves or
renders into the source directory. Follow the photo guide's `mkdir` and snapshot
copy steps before fresh photo generation; a copy of newer source cannot replace
the original source for existing renders. The default source directory is
`work/demo-comparisons/4k/`; use `--source` for another captured input set.

Preflight all 400 recommended frames, save portable animated scenes and record exact
values without initializing a GPU or rendering:

```sh
work/install-blender-m4/blender --background -noaudio --factory-startup --threads 2 \
  --python-exit-code 1 --python examples/create_demo_animations.py -- \
  --clip all --preflight-only --samples 256 --backend HIP \
  --ranges examples/demo_animation_ranges.json \
  --output work/demo-animations/960x540
```

Render the same configuration directly with the patched Blender:

```sh
work/install-blender-m4/blender --background -noaudio --factory-startup --threads 2 \
  --python-exit-code 1 --python examples/create_demo_animations.py -- \
  --clip all --samples 256 --backend HIP \
  --ranges examples/demo_animation_ranges.json \
  --output work/demo-animations/960x540
```

The development-only `work/run-demo-comparisons.py` launcher is not published.
Its 8 GiB memory limit, no-swap limit and two-CPU quota do not apply to these
direct commands. `--backend CPU` uses the CPU path. HIP requires exactly one
HIP device; the existing comparison backend helper disables other devices and
HIPRT and refuses an unavailable or mixed-device configuration. Saved scenes
retain CPU settings and relative output paths regardless of the render backend.

For a three-frame benchmark, use a separate directory:

```sh
work/install-blender-m4/blender --background -noaudio --factory-startup --threads 2 \
  --python-exit-code 1 --python examples/create_demo_animations.py -- \
  --clip tilt --frames 1 25 50 --samples 64 --backend HIP \
  --ranges examples/demo_animation_ranges.json \
  --output work/demo-animations/benchmark
```

`--clip` can repeat. `--frames` selects render frames while retaining the complete
animation and preflighting every sampled frame. `--fps` accepts 5 through 10;
`--seconds` defaults to 10. For a different quality or range configuration, choose
a new output directory. The recommended ranges file is the default for these
documented commands, rather than an implicit generator default. A custom
`--ranges work/my-ranges.json` accepts entries
such as `{"tilt": [-15, 15], "fstop": {"bounds": [1.4, 22],
"interpolation": "log", "range_note": "Custom photographic range"}}`.
Requested values that RNA clamps are rejected. Every sampled configuration must
pass preflight; the script never silently reduces a requested range.

Once all frames are present, run ordinary Python with Pillow, ffmpeg/libx264 and
ffprobe available:

```sh
python examples/encode_demo_animations.py --output work/demo-animations/960x540
```

Explore the [photo and video gallery](https://ricperry.github.io/Blender-TiltShift-Camera/).
Local generation writes `work/demo-gallery/index.html`.
To refresh its presentation without encoding, run
`python3 examples/build_demo_gallery.py`; see the
[gallery guide](DEMO_GALLERY.md) for alternate input directories. The old video
index redirects to this gallery.
The encoder also supports repeated `--clip` and `--gallery-only`. Encoding refuses
missing, changed or unrecorded raw frames, changed scene files, incomplete frame
sequences and non-exact duration. It validates encoded frame count, resolution,
rate, codec, pixel format and duration with ffprobe before promoting an MP4.

## Optical coordinates and guard limits

One Blender unit is one metre in the right-handed Z-up world. Blender camera −Z
points forward and +Y up. Optical coordinates reflect camera Z into Cycles
`(+X right, +Y up, +Z scene-going)`. The rotation convention is
`Rz(axis) Ry(swing) Rx(tilt)` in the reference Y-down frame followed by the Y
reflection. Angles are stored as radians and labeled as degrees. Focal length,
sensor width and shift displacement are reported in millimetres; manual focus
distance is metres. A 36 mm horizontal-fit sensor maps one normalized shift unit
to 36 mm lens-centre displacement. Corner labels show both units for shift.

For lens normal `n`, focal length `f`, manual axial focus `D` and sensor distance
`b`, the tilt-shift conjugate obeys `b = f / (nz − f/D)`. Near-zero denominators and
backward ray domains are rejected. Each sampled frame uses the evaluated tilt-shift
guide API and checks the sharp plane against its guide vertices, with float32
distance tolerance `2e-4 × max(1,D) m`. It also mirrors the internal Cycles camera
availability checks, including the dimensionless `1e-5` domain margin, tilted
aperture extent, near/far clips and filter-padded raster corners.

Manual focus checks reconstruct `b` independently with tolerance
`2e-6 × max(f,|b|) m`. Guide-plane validation uses the algebraically equivalent
stable normal `(nx, ny, f/D)`, avoiding cancellation in `nz − f/b` after the RNA
guide distance has been rounded to float32. This matters for the architectural
scenes' long focus distance and does not widen their guide-distance tolerance.

The internal C++ `Camera::tilt_shift_error` gate has no Python API. The manifest
therefore identifies preflight as **evaluated guides plus a Python guard mirror**;
every actual Cycles render subsequently executes the tilt-shift gate. The fixture
restricts camera fit to horizontal, pixels to square and rendering to a full
raster without border crop, stereo, motion passes or adaptive subdivision. Backend
availability is separately enforced by the existing backend helper. No extra
tilt-shift guard probe render is claimed.

## Artifacts, determinism and safe resume

Each clip directory contains an animated `.blend`, `animation.json`, untouched
`raw/frame-0001.png` through `raw/frame-0050.png`, a `labeled/` sequence, an MP4
and `encoding.json`. The saved camera action has one numeric property channel
with a key at every sampled frame and linear interpolation between those keys.
For aperture, the key values follow the logarithmic sampling above; the sampled
frames are exact, while in-between subframes interpolate linearly.

The generator uses seed 71 with animated seed off, fixed sample count, no adaptive
sampling, denoising, compositing, sequencing or motion blur. Persistent render data
may reuse static scene setup within a process; it does not replace tilt-shift frame
renders. Bitwise equality across devices or Blender builds is not promised.

The manifest records generator/helper, Blender binary, cumulative patch and source
hashes, exact requested/evaluated values, full camera state, per-frame guide/guard
checks, backend/device identity and rendered PNG hashes/timing. Only the active
property can vary across its frames. A resume requires an identical configuration,
verified animated blend and unchanged evaluated preflight. It skips a frame only
when both its successful render record and matching PNG hash exist. Unrecorded
or changed raw frames cause an error instead of arbitrary reuse.

The encoder records each label string and labeled-frame hash, font, ffmpeg
identity/command, MP4 hash and ffprobe verification. Corner labeling converts the
display-referred PNG to RGB for the 8-bit delivery sequence; raw 16-bit Cycles
renders remain available. The gallery verifies source manifest/video/poster hashes
before including an encoded clip. Rendering and visual audits should be reported
separately; this document describes the reproducible workflow, not unrun results.

## Current results

The [photo and video gallery](https://ricperry.github.io/Blender-TiltShift-Camera/) contains all eight
clips: **400 frames, 50 frames per clip, exactly 10 seconds at 5 fps, 960 × 540,
H.264/yuv420p**. Each frame used 256 samples on one Radeon RX 6900 XT HIP device.
The [artifact audit](../work/demo-animations/960x540/artifact-audit.json) passes
raw/labeled/video/source hashes, exact camera values, fixed pose and the confirmed
photographic range preset. Delivery-frame pixels differ from the raw-frame RGB
conversion only inside the corner annotation. The
[scene reopen audit](../work/demo-animations/960x540/scene-reopen-audit.json)
passes all 400 keyed states in the eight CPU-portable animated scenes.

The [browser audit](../work/demo-animations/960x540/gallery-browser-audit-8.json)
passes metadata, playback, seeking to 5 seconds, pausing and default-paused state
for every clip, plus the 520 px layout without horizontal overflow. Visual
inspection covered desktop axis/aperture playback, the narrow layout, and focal
length, vertical-shift and aperture endpoints. These are local artifact and
isolated-browser checks, not broader platform or accessibility acceptance.

The delivered vertical-shift clip uses −0.1 to +0.2 from the range preset; its
replacement source remains under `work/demo-animations/vertical-framed/`. The
original wider clip is preserved under `work/demo-animations/vertical-wide-original/`.
[Captured runtime sources and the range preset](../work/demo-animations/960x540/sources/)
remain beside the final artifacts.

Two launchers returned 143 for an unestablished cause, recorded in
[batch-interruption.json](../work/demo-animations/960x540/batch-interruption.json).
Verified completed frames were retained; the remaining 13 aperture frames and
20 revised vertical-shift frames resumed with clean exit 0, recorded in the
[aperture resume](../work/demo-animation-fstop-resume.process.json) and
[vertical-shift resume](../work/demo-animation-vertical-resume.process.json)
results. The final artifact audits pass; the original batches are not claimed to
have exited cleanly.
