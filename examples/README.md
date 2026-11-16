# Reference scenes

Explore photographs and videos together in the
[local tilt-shift camera gallery](../work/demo-gallery/index.html).
[Rebuild the gallery from existing artifacts](DEMO_GALLERY.md) with ordinary Python;
the generated gallery remains under ignored `work/` and is not published.

For the larger photographic suite, see [17 tilt-shift/ordinary comparison images](DEMO_COMPARISONS.md):
botanical extended focus, 10° city tilt, optimized ordinary DOF, architecture
shift parity, and optional focus-plane intersections on scene surfaces. The generator saves
editable scenes and full resolution images in ignored `work/`, linked from the shared gallery.

For eight **10-second camera-control animations**, see
[Tilt-shift photographic controls in motion](DEMO_ANIMATIONS.md) and the generated
[shared gallery](../work/demo-gallery/index.html). Each clip changes
one tilt-shift camera setting and labels its current value in every frame.

For a real city-scale comparison of lens tilt and standard depth of field, see
[Full-scale Meridian](FULL_SCALE_CITY.md). Three matched 50 mm f/2.8 cameras
keep DOF enabled in the standard view and the tilt-shift camera’s zero-angle
and tilted views.

For a detailed, animated miniature city with six tilt-shift camera experiments, see
[Little Meridian](CITY.md). Its generator creates a portable `.blend` under
`work/examples/harbor-city/`; the fixtures below serve separate validation work.

Generate the four named fixtures with `python3 scripts/dev.py scenes` after
building the pinned Blender. Files are written as `work/scenes/<name>.blend`.
The readable generator is [blender_reference.py](../scripts/blender_reference.py).
One Blender unit is one metre; camera focal length is 50 mm, horizontal sensor
width 36 mm and aperture f/4. Renders use 320×240, 32 samples, seed 71, no adaptive
sampling or denoising, fixed four CPU threads, and linear 32-bit RGBA EXR.
Each render also produces a display-only 8-bit PNG using Blender's scene view
transform. Inspect all four previews after actual rendering; use EXR/float data
for numerical evidence. Baseline images do not establish tilt-shift physics.
Initialization generated/saved/reopened all four scenes and rendered all four on
CPU, with an additional HIP targets render. Parent visual inspection covered all
four CPU fixtures and the HIP targets; the facade includes the complete building
with margin. Exact output hashes and comparison results are in
[baseline-validation.json](../docs/baseline-validation.json).

| Fixture | Geometry | Future physical acceptance purpose |
|---|---|---|
| `grid` | Ground lines at 0.5 m intervals | Movement signs, focus plane, framing and image-circle coverage |
| `tabletop` | Receding table and seven depth blocks | Scheimpflug focus across a plane and independent aperture behavior |
| `facade` | 5×6 window grid on a 5×6 m facade | Shift framing, verticals, breathing and viewport mismatch |
| `measurable-targets` | Striped targets at y=0,1,2,3,4 m | Quantified sharpness/CoC and CPU/HIP pixel comparisons |

These are deterministic baseline fixtures, not current proof of tilted-lens
physics. They presently use ordinary upstream Cycles DOF. M2 must add tilt-shift
parameter cases and independently predicted measurement regions/thresholds for
focus, blur, shift and clipping. The standalone M1 tests provide that mathematical
reference; image appearance alone cannot replace invariant checks.
