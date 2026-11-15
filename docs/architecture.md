<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Architecture and accepted boundaries

The target is a native Blender 5.3 / Cycles camera: raster samples generate rays
through a physical tilted thin lens before scene intersection. No image-space
blur, compositor substitute, or rotated ordinary focus plane satisfies this goal.
M1 implements only the standalone optical reference; it changes no Blender code.

`src/optics/thin_lens.{h,cpp}` is the double-precision numerical authority.
`tests/optics_tests.cpp` checks conjugacy, forward/backward refraction, unit
covariance, aperture sampling, coverage, blur, Scheimpflug, hinge and invalid
domains. The full derivation, singularities and tolerances are in
[optical-model.md](optical-model.md). Native CPU and HIP kernels must share a
small device-compatible mathematical implementation, compared against this
reference. The C++20 reference cannot simply be copied into HIP's C++17 kernel.

Accepted behavior: enabled mode uses physical focus breathing, including at zero
tilt. Disabled mode must dispatch through the original Cycles camera path with no
altered expressions, defaults or serialization interpretation. Baseline-disabled
renders must compare exactly within one executable/device/settings combination;
comparison to the unmodified pinned build is a separate regression gate.

The reference frame is right-handed, +X right, +Y down, +Z scene-going; Cycles
perspective uses +X right, +Y up, +Z scene-going. The boundary reflection is
`(X,Y,Z) -> (X,-Y,Z)`; Euler signs and cross products require explicit tests.
Blender object-local conversion is the proper rotation `(X,-Y,-Z)`.
Optical lengths use metres; native integration adopts **1 Blender unit = 1 metre**,
with lens/sensor millimetres converted by `1e-3`. Scene display `scale_length`
does not change optical physics. Angles use radians, with
`Rz(axis_rotation) Ry(swing) Rx(tilt)`: the rightmost Rx acts first about fixed X,
then Ry about fixed Y, then Rz about fixed Z.

Shift in M1 moves the sensor rectangle relative to a fixed lens centre; it is
not a world-space lens translation. UI names/defaults and mapping of Blender's
dimensionless shift to sensor displacement remain M2 decisions, to be verified
with framing/sign fixtures. Coverage is an ideal binary angular stop at the rear
focal plane, not a realistic barrel/vignetting model. Ray weights in M1 establish
coverage only; radiometric throughput/PDF and exposure await native integration.

Native integration must reject singular geometry visibly rather than silently
clamp it. Float GPU tolerances must be measured independently of CPU double
tolerances. Physical camera projection also affects motion vectors, dicing,
volume initialization, clipping and overlays; support boundaries must be explicit
before claiming a usable production camera.
