# Reference scenes

Generate the four named fixtures with `python3 scripts/dev.py scenes` after
building the pinned Blender. Files are written as `work/scenes/<name>.blend`.
The readable generator is [blender_reference.py](../scripts/blender_reference.py).
One Blender unit is one metre; camera focal length is 50 mm, horizontal sensor
width 36 mm and aperture f/4. Renders use 320×240, 32 samples, seed 71, no adaptive
sampling or denoising, fixed four CPU threads, and linear 32-bit RGBA EXR.

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
