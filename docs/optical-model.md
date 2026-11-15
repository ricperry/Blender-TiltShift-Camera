<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Tilted thin-lens reference (M1)

This is a standalone, double-precision, ideal Gaussian thin-lens reference for a
future native Blender 5.3 / Cycles camera. It is neither a renderer nor a
postprocessing effect. Tests establish geometrical optics only; native CPU
rendering, disabled-path parity, exposure, sampling PDFs, derivatives, ray
footprints, and HIP remain separate integration requirements.

The enabled camera uses **physical focus breathing**. This is an accepted project
decision: zero tilt with finite focus is allowed to differ from the existing
Cycles camera's fixed field of view. The disabled camera must continue to use the
original Cycles code path. No existing Blender camera behavior is modified by M1.

## Coordinates, units, and movements

Use a right-handed optical coordinate system, with lens centre `C = (0,0,0)`,
`eX × eY = eZ`, and `+Z` toward the scene. Seen from behind the camera looking
toward the scene, `+X` is right and `+Y` is **down**. The sensor has fixed
orientation, normal `k = eZ`, and lies at `z = -b`. Its position changes when
focusing. Its sample point is

```
p = (shift_x + u * sensor_width/2,
     shift_y + v * sensor_height/2, -b),      -1 <= u,v <= 1.
```

These are physical sensor coordinates. Inversion is intentional: at zero tilt,
positive sensor X sees negative scene X. Future raster mapping must account for
this inversion rather than treating these samples as an upright virtual screen.

Every length must use the same unit. Tests and defaults use metres, including
focal length, sensor size, aperture radius, shift, and focus distance. Angles are
radians. There is no implicit mm-to-m conversion or scene-unit conversion in this
library. The lens normal and aperture basis use active, right-handed rotations:

```
R = Rz(axis_rotation) * Ry(swing) * Rx(tilt)
n = R * eZ;    ex = R * eX;    ey = R * eY.
```

Thus Rx is applied first about the fixed X axis, then Ry about fixed Y, then Rz
about fixed Z. This is not a pair of rotations about successively transported
local axes. Positive tilt alone produces `n = (0,-sin(tilt),cos(tilt))`;
positive swing alone produces `n = (sin(swing),0,cos(swing))`. Axis rotation
rotates the combined movement and aperture frame about camera Z. Order matters
when tilt and swing are both nonzero. A circular aperture is invariant under a
rotation in its own plane; the full basis is retained to describe its sampling.

**Shift moves the sensor rectangle relative to a fixed lens centre.** It changes
framing and chief rays, and can move the frame out of coverage. It neither changes
sensor orientation nor rotates the plane of focus. This models relative shift
geometry, not the world-space translation of a lens barrel on a fixed camera
body. To implement physical lens shift while fixing the sensor/body anchor, the
integration must move `C` and transform the sensor into that lens-local frame;
world ray origins then move by `C`. All local rays transform as
`O_world = C_world + R_world O_local`, `d_world = R_world d_local` for a proper
rigid transform. Do not apply sensor-shift framing alone and claim that the lens
origin moved.

## Focus convention and physical sensor distance

`D = focus_distance` is the intersection of the plane of sharp focus with the
fixed camera `+Z` axis, measured from the lens centre. It is not distance along
the tilted lens axis, nor distance from the sensor. Positive infinity is allowed.
With focal length `f > 0`, choose

```
b = f / (n.z - f/D),       f/(+infinity) = 0.
```

A valid real sensor requires `n.z - f/D > 0`. At zero tilt, this becomes the
Gaussian lens relation `1/f = 1/D + 1/b`; at infinity `b = f/n.z`. A tilted lens
focused at infinity means the fixed `+Z` scene direction is in focus at infinity;
it does not mean every sensor position has a conjugate at infinity.

Physical finite focusing moves the sensor: for zero tilt,
`b = f D/(D-f) > f`. Therefore the pinhole chief-ray half-angle satisfies
`tan(alpha) = sensor_width/(2 b)`, rather than the fixed-f expression. This
breathing is required by this model at fixed focal length and sensor width.

## Conjugate and ray derivation

Write coordinates relative to `C`; for another lens centre replace `p` below by
`p-C`. The lens plane is `n·x = 0`. A sensor point must satisfy `n·p < 0`. Define

```
h = 1 + (n·p)/f.
Q_homogeneous = (p, h).
```

For `h != 0`, the scene conjugate is `Q = p/h`. The straight line through the
optical centre has no angular deflection, so object and image are collinear.
Let `w = -n·p > 0`. For a real conjugate (`h < 0`), its positive axial distance is
`U = n·Q = f w/(w-f)`, giving `1/f = 1/U + 1/w`. The same projective expression
also covers virtual conjugates (`h > 0`) and points at infinity (`h = 0`).

Sample aperture point `A = r(ex cos(phi) + ey sin(phi))`, with
`r = aperture_radius sqrt(xi1)` and `phi = 2 pi xi2`. This is uniform in disk
area. The scene-going ray is

```
O = A;
d = normalize(h A - p).
```

For real conjugates, this is directed from `A` to `Q`; for virtual conjugates,
the backward extension passes through `Q`. Its lens-normal component before
normalization is `n·(h A-p) = -n·p > 0`. At infinity it reduces smoothly to
`normalize(-p)`, independent of aperture sample. The implementation never divides
by `h`, so it needs no large surrogate focus distance, epsilon sign selection,
or discontinuous real/virtual branch.

An independent refraction check uses axial slopes. The incident sensor-to-lens
ray with unit normal component is `vin = (A-p)/w`, and the outgoing ray is
`vout = d/(n·d)`. Their transverse difference must be exactly the thin-lens kick

```
vout - vin = -A/f.
```

The tests evaluate this independently for 1,620 deterministic rays across
combined positive/negative tilt, swing, axis rotation, sensor shifts, and aperture
samples. They also propagate scene rays forward using the opposite slope kick
and intersect the physical sensor.

## Scheimpflug and hinge, derived rather than imposed

Inverting the conjugacy gives `p = Q/(1-n·Q/f)`. Enforcing `p.z = -b` yields the
sharp-focus plane

```
(n - (f/b) k) · Q = f.                         (1)
```

This plane is a consequence of refraction and the physical sensor, not a rotated
ordinary graphics focus plane. Substituting `(0,0,D)` verifies the stated focus
convention. Let `q = (n.x,n.y,0)` and `s = |q|`.

For `s > 0`, intersect the lens plane `n·Q=0` and sensor plane `Q.z=-b`.
Equation (1) is then satisfied automatically, giving the **Scheimpflug line**.
One point on it is `(b n.z/s²) q - b k`; its direction is `k × n`.

Intersect instead the through-lens plane parallel to the sensor (`Q.z=0`) and
the front focal plane (`n·Q=f`). These also satisfy (1), giving the **hinge
line**. A point on it nearest the origin is `H = (f/s²) q`, so

```
distance(C, hinge) = f/s = f/sin(angle between lens and sensor normals).
```

Its direction is again `k × n`. Changing `D` with the same lens orientation
changes `b` and the focus-plane angle, but preserves this hinge. Numerical tests
check both three-plane intersection laws and the hinge distance independently.
At zero tilt/swing the intersection lines are at infinity; no finite line is
constructed. At exactly zero tilt and infinite focus, (1) has zero normal and
nonzero offset. As homogeneous plane coefficients this is the **plane at
infinity**; it has no finite affine points. Callers must not normalize its normal
or attempt an ordinary ray-plane intersection.

For finite `D`, (1) also gives
`Q.z = D * (1 - (n.x Q.x + n.y Q.y)/f)`. Positive tilt alone therefore increases
focus depth with positive optical Y, and positive swing alone decreases depth
with positive optical X. This documents signs before any Blender UI convention.

## Aperture, blur, and coverage

The aperture is a circular opening in the actual tilted lens plane. It is not a
blur kernel, a disk on the sensor plane, or a rotation of an untilted outgoing
ray. At zero tilt the sensor-plane blur diameter of an axial object at distance
`U` is

```
CoC_diameter = 2 aperture_radius * abs(1 - b*(1/f - 1/U)).
```

Forward-propagation tests check this at multiple object distances, radii, and the
exact focus distance. For a tilted lens, the defocused sensor footprint is
generally not a circle; the library emits physical rays rather than applying
this untilted scalar formula. Zero aperture is the normalized geometric pinhole
limit. A physical opening of zero area transmits zero energy; returning a ray in
that limit is not an exposure claim.

`image_circle_radius` deliberately has an explicit M1 convention: it defines a
**prescribed circular angular coverage stop at the rear focal plane**, not a
measured lens barrel or a circular boundary drawn on the moving sensor. Follow
the sensor chief ray through the centre to the plane `n·x=-f`:

```
B = -f p/(n·p);
covered iff |B + f n| <= image_circle_radius.
```

Equivalently, the angle `theta` to the lens axis must satisfy
`tan(theta) <= image_circle_radius/f`. At zero tilt and infinite focus the
specified radius is the physical sensor-plane circle radius. At finite focus
its sensor-plane radius is `b/f` times larger. With tilt, intersection of this
coverage cone with the sensor is a conic (an ellipse for ordinary tilt/coverage
angles; a parabola or hyperbola is possible at extreme angles). Shift moves the
frame within that footprint. Positive infinity disables
clipping; zero admits only the optical-axis chief ray in exact arithmetic.

The gate is binary, independent of aperture sample, with no arbitrary radial
vignetting. An ideal Gaussian thin lens alone does not predict image-circle
cutoff: the stop is an explicit idealized coverage parameter. Real barrel
occlusion, cat-eye pupils, gradual mechanical vignetting, aberrations, diffraction,
and radiometric cosine falloff are outside M1. The ray `weight` is only this
coverage indicator, with no claim about energy, importance sampling, or exposure.

## Domain, singularities, and numerical policy

The reference uses C++20, standard-library double precision, and no dependencies.
Invalid configurations/samples throw `std::invalid_argument`; nothing silently
clamps focus, rotations, shift, aperture coordinates, or coverage.

* Focal length and sensor dimensions must be finite and positive. Shift and
  rotations must be finite. Aperture radius must be finite and nonnegative.
  Coverage radius must be nonnegative or positive infinity. Focus distance must
  be positive or positive infinity.
* `n.z` and `n.z-f/D` must exceed `64 * DBL_EPSILON` (approximately `1.42e-14`).
  This rejects reversed/grazing lens orientation and the infinite sensor travel
  singularity. It is a numerical domain guard, not an optical angle preset.
* Every sensor corner must be behind the lens plane by more than
  `64 * DBL_EPSILON * L`, where `L` is the largest focal length, sensor distance,
  sensor dimension, absolute shift, or aperture radius. Linear plane distance
  reaches its extrema at rectangle corners, so this covers the full sensor.
* The entire aperture must lie in front of the sensor plane by the same margin:
  `b - aperture_radius*hypot(ex.z,ey.z) > 64 * DBL_EPSILON * L`.
  A sensor or aperture physically crossing the other plane is rejected.
* Sensor coordinates must lie in `[-1,1]`, explicit aperture coordinates in the
  unit disk, and random variates in `[0,1]`. Endpoints are permitted. Nonfinite
  values are rejected. Vector normalization rejects zero/nonfinite vectors.
* Infinity is represented projectively without an `h` threshold. Coverage uses
  its stated floating-point comparison; samples within rounding error of the
  exact coverage boundary need not have stable inclusion. Tests deliberately
  probe either side with a resolved margin.

Test tolerances are explicit absolute values in metres or dimensionless values,
appropriate to the documented sub-metre lens / metre scene fixtures. Typical
unit vectors and plane constraints use `1e-15`, forward sensor reconstruction
`1e-12 m`, and conjugate ray collinearity `1e-10 m`; the looser conjugate tolerance
accounts for division near infinity in the *test*, not in ray generation. Unit
covariance is checked at scale factors `1e-6` and `1e6`. This is a CPU double
reference: GPU float tolerances and accepted production parameter ranges must be
established during native integration rather than copied uncritically.

## Blender / Cycles boundary and remaining gates

Inspection of the pinned Blender 5.3 source establishes that Cycles camera
coordinates use `+X` right, `+Y` up, `+Z` forward after its camera-axis conversion.
These are reflected relative to this reference. Convert optics vectors to Cycles
by `(X,Y,Z) -> (X,-Y,Z)`; because that mapping is a reflection, do not transform
cross products or Euler signs by assumption. Derive/test the UI movement signs
at the boundary. Blender object-local coordinates can instead be reached by the
proper rotation `(X,Y,Z) -> (X,-Y,-Z)`.

Blender's existing focal length/sensor dimensions are millimetres; its aperture
radius conversion uses `lens_mm * 1e-3/(2*f_number)`. Its existing focus distance,
object placement, and clips are raw Blender units; scene display `scale_length`
is not automatically applied. Integration must explicitly reconcile those
conventions before feeding this all-one-unit reference. M1 does not define a
new UI or silently reinterpret existing files.

Required next evidence includes correct raster orientation and shift sign,
physical finite-focus breathing when enabled, unchanged original Cycles when
disabled, scene scale and clipping behavior, derivatives, PDFs and throughput,
CPU deterministic renders, and an actual RDNA2 HIP build/render comparison.
A standalone passing test is not acceptance of a native camera or HIP support.

## Build and verify

```
cmake -S . -B work/build-optics -DCMAKE_BUILD_TYPE=Debug
CCACHE_DIR="$PWD/work/ccache" cmake --build work/build-optics -j2
/usr/bin/ctest --test-dir work/build-optics --output-on-failure
work/build-optics/optics_tests
```

The explicit cache directory keeps compiler output inside ignored `work/` in
restricted environments. On the initialization host `/usr/bin/ctest` avoids a
broken unrelated user-local Python wrapper. No system Blender is installed or
replaced by this build.

## Optical references

The derivation above specializes ideal Gaussian thin-lens conjugacy; it does not
claim the accuracy of a real multi-element lens. The Gaussian lens equation and
physical sensor movement are described in [Physically Based Rendering, fourth
edition, Projective Camera Models](https://www.pbr-book.org/4ed/Cameras_and_Film/Projective_Camera_Models).
Harold M. Merklinger's authored [Principles of View Camera Focus](https://www.cs.cmu.edu/~ILIM/courses/vision-sensors/readings/VuCamTxt.pdf)
describes the Scheimpflug and hinge three-plane conditions and the need to
satisfy both. M1 derives and tests both conditions from the same conjugate map.
