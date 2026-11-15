# Reference scenes

For a real city-scale native-tilt versus ordinary-DOF comparison, see
[Full-scale Meridian](FULL_SCALE_CITY.md). Three matched 50 mm f/2.8 cameras
keep DOF enabled across ordinary, native-zero and native-tilted views.

For a detailed, animated miniature city with six native-camera experiments, see
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
for numerical evidence. Baseline images do not establish native tilt-shift physics.
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
physics. They presently use ordinary upstream Cycles DOF. M2 must add native
parameter cases and independently predicted measurement regions/thresholds for
focus, blur, shift and clipping. The standalone M1 tests provide that mathematical
reference; image appearance alone cannot replace invariant checks.
