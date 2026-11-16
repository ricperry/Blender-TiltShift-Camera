<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# M2 tilt-shift camera on CPU

The reviewable patch is `patches/blender-v5.3.0-tilt-shift.patch`, against the
[recorded Blender pin](source-revision.json). It adds native persisted camera RNA,
Cycles synchronization and a separate physical perspective ray branch. The bounded
static CPU foundation passed numerical, measured-render, disabled-regression and
persistence gates; [the evidence ledger](m2-validation.json) records exact artifacts
and supported limits. M3 owns the camera panel and viewport overlays; M4 requires a
newly compiled and rendered RDNA2 kernel. This is not production acceptance.

## Programmatic controls and persistence

Use the ordinary Blender Camera datablock:

```python
camera.tilt_shift_enabled = True
camera.tilt_shift_tilt = math.radians(8)
camera.tilt_shift_swing = math.radians(-3)
camera.tilt_shift_axis_rotation = math.radians(20)
camera.tilt_shift_image_circle_diameter = 48  # millimetres; 0 means unbounded
```

The enable default is false; the three angular defaults and coverage diameter
are zero. Angles store radians with RNA angle metadata. Existing focal length,
sensor fit/dimensions, dimensionless shift and DOF controls remain authoritative.
There is no second serialized shift state. Physical millimetre shift views and
visualization toggles await M3. The ordinary camera outline has not been made a
physical camera preview.

New-ID DNA member defaults are complemented by schema-based old-file migration:
absence of the `Camera.tilt_shift_enabled` member disables the physical model and
zeros all new settings, independently of the upstream file subversion. Native
round trips retain new fields. Existing shift and optical fields are untouched by
migration. The unmodified baseline camera file migrated with disabled defaults and preserved
shift; native save/reopen retained all five fields. Broader saved-file compatibility
and M3 animation/dependency acceptance remain separate work.

## Frame, units, movements and physical shift

The independent [M1 model](optical-model.md) uses a right-handed lens frame with
X right, Y down and Z toward the scene. Cycles uses X right, Y up and Z toward
the scene, reached by reflecting Y. Build the M1 active rotation
`Rz(axis) Ry(swing) Rx(tilt)`, then reflect the normal and both aperture axes;
rebuilding a reflected aperture axis using a cross product gives the wrong sign.
Native aperture coordinates use the negative reflected M1 Y axis to preserve
Cycles polygon rotation at zero movement. Existing circular/polygonal and
anamorphic aperture sampling is retained in the actual tilted plane.

Native optical lengths use metres: **1 Blender unit = 1 metre**. Focal length
and sensor millimetres are multiplied by `1e-3`. Scene display `scale_length`
does not change the physics. Camera object scale remains removed by upstream
camera synchronization.

M2 fixes the sensor/body anchor and moves the actual lens centre. Let `S` be the
active sensor-fit size in metres (sensor width for AUTO/HORIZONTAL, sensor height
for VERTICAL), and let `T` be the existing camera viewplane roll/flip transform:

```
C.xy = T(S * (Camera.shift_x, Camera.shift_y)); C.z = 0
```

Viewport pan and zoom do not move the physical lens. The existing viewplane shift
inserts `C/f` into nominal virtual-screen slopes `q.xy/q.z`, using the same
roll/flip. Define sensor coordinates relative to the translated lens centre as

```
p = (-f*q.x/q.z, -f*q.y/q.z, -b)
```

Then the body sensor point `C+p` is invariant under shift: the shift in `p`
cancels `C` once. Actual body ray origins are `C+A`; this is a physical decentered
lens, rather than sensor-only framing. Chief rays retain parallel-line
perspective and the derived plane of sharp focus, while both framing and lens
origin change. Pixel aspect, fit, border/crop and existing raster transforms stay
in the upstream projection chain. Numeric and rendered centroid fixtures check
shift signs, breathing, sensor fit and pixel aspect.

## Focus and ray law

Manual focus distance `D` is measured along the fixed scene-going line through
**the translated lens centre**, `C+(0,0,D)`, not along the tilted lens axis or from
the sensor. It remains meaningful when DOF is off; DOF off selects aperture
radius zero without disabling physical breathing. With lens normal `n`,

```
b = f / (n.z - f/D)
h = 1 + dot(n,p)/f
O_body = C + A
d_body = normalize(h*A - p)
```

Finite manual `D` must be positive and produce a valid real sensor. The kernel
never divides by `h`, so real/infinite/virtual conjugate regions are continuous.
The standalone reference also tests exact positive-infinite manual focus; native
RNA integration currently accepts finite manual values only.

For a focus object, including an evaluated bone subtarget, preserve its full
camera-space point `P`, set `Q=P-C`, and solve

```
b = f*Q.z / (dot(n,Q)-f)
```

This places an off-axis target on the actual sharp plane rather than merely
using its axial Z coordinate. Object focus requires `Q.z>0` and `dot(n,Q)>f`
with the float margin below. Its plane may have an infinite or negative
camera-axis intercept; M2 does not incorrectly force a positive effective `D`.
In body coordinates the sharp plane is
`(n-(f/b)k) dot P = f + (n-(f/b)k) dot C`.

The shared scalar float header is compiled directly by `native_float_tests` and
mirrored byte-for-byte into the kernel patch. Against the independent C++20
double reference, the current 39,214 checks measure maximum unit-direction error
`1.35967e-7` and maximum aperture-origin error `9.07662e-10 m` over the stated
matrix. They also check body-anchor shift, object-focus convergence, inverse
chief mapping, clip planes and neighboring sampled-ray differences, including
exact infinite/virtual conjugate crossings and object focus with negative axis
intercept. These
measurements do not establish HIP behavior.

## Projection boundaries and validation

The inverse chief projection first subtracts `C`, then scales camera X/Y by
`b/f` before the nominal upstream projection. Exported forward transforms use
`C + diag(f/b,f/b,1)*P_nominal`; corresponding forward/inverse named shader
transforms remain paired. The raw kernel `rastertocamera` stays nominal because
it maps raster coordinates to physical sensor coordinates above. This chief
projection does not invent a unique inverse for the finite-aperture ray bundle.
For background Window coordinates, anchor the direction at the physical lens
centre before applying the inverse; a regression fixture caught and verified
this correction. Generic camera position/distance helpers and unprojected camera-space coordinates
retain the camera-body anchor convention; camera-Z depth is measured from the
body Z plane (the lateral lens translation has zero Z). Baking has no M2
acceptance evidence.

Each sampled physical ray intersects camera-Z near and far clip planes using
its actual tilted-aperture origin and direction. The entire aperture must lie
behind the positive near plane. Exact one-pixel neighboring rays hold the same
sampled aperture fixed, independently intersect the near plane, and provide both
origin and direction finite differences. Existing progressive differential scale
and compact storage are retained.

For volumes, the enabled camera conservatively requests per-ray volume-stack
initialization. It does not use the old pinhole/flat-aperture frustum to decide
that a physical ray cannot start inside a volume. The homogeneous absorption
fixture specifically places the near-clipped ray inside a slab whose camera
body origin is outside.

Before shader/geometry device updates, M2 visibly rejects:

- GPU devices; new-camera HIP validation is M4, irrespective of the M1 baseline.
- Non-perspective cameras, motion blur, motion-vector passes and multiview/stereo.
- Adaptive subdivision, whose dicing/footprint acceptance remains unimplemented.
- Nonfinite/invalid parameters, nonpositive or singular sensor distances, a sensor
  touching/crossing the lens plane, backward rays or an aperture crossing the
  sensor or near clip plane.

The dimensionless float rejection margin is `1e-5`, applied to the lens-facing
normal and `f/b`, and multiplied by the largest relevant optical length for
sensor/aperture plane tests. Focus objects require `dot(n,Q)>f*(1+1e-5)`.
Bounds include the full anamorphic ellipse (conservative for polygonal apertures),
all raster corners expanded by `1.5*filter_width+1` pixels, and the largest sensor
coordinate magnitude. Invalid geometry is rejected instead of silently clamped.

Inside coverage, sampling returns unit camera weight using the existing Cycles
exposure-normalized aperture convention. Outside the prescribed rear-focal-plane
angular image circle it returns zero. No cosine falloff, barrel vignetting,
spectral model or physical exposure/PDF calibration is claimed. Image-circle
clipping is an ideal coverage boundary, not a production lens transmission model.

## Reproduction and evidence limits

Preserve the unmodified installation as `work/install-blender-baseline` and use
`work/install-blender-m2` for the new binary. Reusing a prefix containing the M1
HIP fatbin would leave a stale incompatible kernel alongside changed device data;
M2's enabled GPU guard is intentional. Keep the pinned source HEAD unchanged.
The patch exporter includes only the explicitly reviewed untracked native header
and rejects any other untracked source; it never stages or commits upstream.

```sh
python3 scripts/dev.py test-optics
python3 scripts/dev.py patch
work/install-blender-baseline/blender --background -noaudio --factory-startup \
  --python-exit-code 1 --python scripts/blender_m2_validation.py -- \
  --output work/m2-old --case write-upstream
work/install-blender-m2/blender --background -noaudio --factory-startup \
  --python-exit-code 1 --python scripts/blender_m2_validation.py -- \
  --output work/m2-validation --case persistence \
  --upstream-file work/m2-old/upstream-camera.blend
for case in projection centroid coc tilted coverage volume-clips; do
  work/install-blender-m2/blender --background -noaudio --factory-startup \
    --python-exit-code 1 --python scripts/blender_m2_validation.py -- \
    --output work/m2-validation --case "$case"
done
python3 scripts/run_m2_guards.py --blender work/install-blender-m2/blender \
  --output work/m2-validation
```

Use the [isolated environment/resource scopes](build-instructions.md) for all
Blender commands. The parent validation runner controls four-job/18 GiB builds
and sequential two-core/4 GiB runtime scopes; no desktop is opened. `--case` can
select `centroid`, `coc`, `tilted`, `projection`, `coverage`, `volume-clips`, `guards` or
`persistence` individually. Measurement JSON records binary, fixture script and
patch SHA-256 hashes because source HEAD alone cannot identify the modified build.
EXR and raw linear RGBA are the measurements; PNG is only visual evidence.

All seven positive case groups exited zero on the final binary. The guard host
runner also exited zero after validating a fresh complete eight-rejection JSON
and Blender's expected exit one. Upstream `render/intern/engine.cc` sets
`G.is_break` when render reports include `RPT_ERROR`; `creator/creator.cc` maps
that flag to background failure even when Python caught each expected error.
Consequently direct `--case guards` and `--case all` exit one by design. The
host runner accepts that exit only with complete expected messages, unique fresh
artifacts and matching binary/script/patch hashes; unrelated errors fail.

Measured final results include maximum centroid error `.03663 px`, CoC
`16.48236 px` versus `16.46091 px`, tilted outer-target variance ratios `.16094`
and `.16236`, zero interior/exterior coverage error away from the declared edge
margin, absorption `.67027297` versus axial `exp(-.4)=.67032005`, and zero leaked
near/far target flux. World Window means are `.500000118` / `.500000065`, after
the earlier erroneous X mean `.493100521` exposed the background-origin bug.
Four disabled fixtures are bitwise RGBA identical to the preserved baseline.
Generated PNGs were inspected; their linear EXR/raw data supply the measurements.

The CoC fixture uses `f=.05 m`, `D=.5 m`, object depth `.3 m`, aperture radius
`.0125 m`, and 36 mm / 320-pixel horizontal framing. Expected sensor CoC is
`1.85185185 mm`, or `16.46090535 px`. It subtracts the finite emitter square's
second moment from measured variance and permits `.8 px` for pixel filtering
and Monte Carlo residual. Tilted-plane fixtures compare local second moments
at independently derived sharp-plane targets with the same untilted camera;
they supplement, rather than replace, the numerical Scheimpflug/hinge proof.
Coverage fixtures check independent masks away from a stated edge margin.
The clipping fixture places colored targets just outside near/far planes.

The immutable M1 scene generator separately establishes disabled-path bitwise
regression against the preserved baseline. A successful M2 run still does not
establish UI, viewport overlays, GNOME/Wayland, screen-reader, real lens accuracy,
production radiometry, arbitrary dicing, motion or HIP acceptance.
