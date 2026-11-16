<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Tilt-shift depth-of-field visual comparison

`scripts/blender_visual_comparison.py` makes a large, reproducible comparison of
one receding tabletop chart. All three images use the same geometry, rigid camera
transform, 50 mm lens, f/1.4 aperture, 0.65 m manual focus, seed and CPU settings.
Depth of Field is **enabled**. M3 preserves M2 optics; changing the milestone alone
is not expected to change a render.
M3's lens/focus/image-circle guide checkboxes control viewport display only;
they intentionally leave final pixels unchanged.

| Case | Tilt-shift camera | Lens tilt |
| --- | --- | --- |
| `ordinary` | Disabled | 0° |
| `physical-zero` | Enabled | 0° |
| `physical-tilted` | Enabled | −8° |

Compare the near and far checkerboards and fine line pairs, rather than only the
middle row. The zero-tilt cases focus around one depth. The tilted case places the
whole chart on the tilt-shift camera's sharp plane. Enabling physical optics also
changes close-focus framing through sensor extension; this is expected breathing,
not a change to the camera transform.

Geometry uses unscaled camera-local metres: X right, Y up, negative Z into the
scene. The chart obeys `Z = -(d + slope*Y)`, where `d = 0.65 m` and
`slope = -d*sin(-8°)/0.05`. This follows the independent manual-focus plane law
`depth = d*(1 - sin(tilt)*Y/f)`. Lens rotation order is
`Rz(axis) Ry(swing) Rx(tilt)`; swing and axis rotation remain zero. Printed layers
are separated by at most 30 μm along camera Z. Image-circle diameter zero is
unbounded. These finite, forward-facing settings are away from the native
`1e-5` singularity margin.

Run sequentially under the runtime resource limits in the build instructions:

```sh
work/install-blender-m3/blender --background -noaudio --factory-startup \
  --python-exit-code 1 --python scripts/blender_visual_comparison.py -- \
  --output work/visual-comparison --case all
```

Defaults are 1280×800, 128 samples and two CPU threads. The fixture writes three
PNGs and three editable `.blend` files under ignored `work/visual-comparison/`.
Per-case JSON manifests record actual RNA, renderer settings, upstream pin and
binary/script/patch/image/scene hashes. Each case can also run separately with
`--case ordinary`, `--case physical-zero` or `--case physical-tilted`.

All patterns and text are real scene geometry with emission materials. There is
no compositor, image-space blur, adaptive sampling or denoising. This comparison
is visual CPU evidence for the tilt-shift focus controls; it does not establish HIP,
GNOME/Wayland interaction or production-lens calibration.

## Observed result

All three native CPU renders completed successfully and were visually inspected
at 1280×800. Ordinary and physical-zero images have a sharp middle row with
pronounced blur in the near and far rows. At −8°, all five rows are visibly
sharp, including their fine line pairs and depth labels, over target depths
0.503–0.920 m. This is direct rendered evidence that the lens tilt control
rotates the focus plane while the rigid camera, aperture and focus distance stay
fixed. It is a visual comparison, not a measured MTF result.

The [completed manifest](../work/visual-comparison/manifest.json) records native
Blender 5.3.0, binary SHA-256
`9c5a635e23bd49e59f60ee67341b081d0f88fb3637d86a46416b133cd222324f`,
and all image/scene hashes. The recorded RNA differs only in physical-camera
enable and lens tilt. Compare
[ordinary](../work/visual-comparison/ordinary.png),
[physical zero tilt](../work/visual-comparison/physical-zero.png), and
[physical −8° tilt](../work/visual-comparison/physical-tilted.png).

## M4 CPU/HIP reproduction

M4 imports this frozen chart without changing its geometry or accepted −8°
settings. The same new executable rendered CPU and hard-selected RX 6900 XT HIP
at 1280×800, 128 samples and seed 203, with denoising/adaptive sampling off.
Both final images were inspected: all five depth rows and their fine line pairs
remain sharp. Linear RGB RMSE was `0.0001215173175`, maximum absolute difference
`0.006985008717`, within the predeclared `0.003` / `0.015625` bounds. This is
qualitative focus evidence plus CPU/HIP pixel parity, not an MTF or physical-lens
calibration result.

The new runner saves EXR/raw measurements, PNG previews and editable scenes:
[CPU chart](../work/m4-validation/cpu/physical-focus-chart.png),
[HIP chart](../work/m4-validation/hip/physical-focus-chart.png),
[CPU scene](../work/m4-validation/cpu/physical-focus-chart.blend),
[HIP scene](../work/m4-validation/hip/physical-focus-chart.blend).
See [M4 reproduction](m4-hip-camera.md) and its
[machine-readable ledger](m4-validation.json) for exact hashes and device scope.
The M3 comparison and original script above remain historical evidence.
