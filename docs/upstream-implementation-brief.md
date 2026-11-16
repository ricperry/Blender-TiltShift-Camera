<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Native tilt-shift camera: implementation and release work

This brief describes the implemented prototype and proposes work for an upstream
release. It is not an upstream design decision or a claim of maintainer acceptance.
The reviewed source is the cumulative [M4 patch](../patches/blender-v5.3.0-tilt-shift-m4.patch):
16 modified upstream files and one new header, against Blender `v5.3.0` commit
`02f0899d78e374b63e7181d9061e1f7ab03419cc`. The [source manifest](source-revision.json)
records the exact pin and patch hash. Apply M4 once; do not stack earlier patches.

## What changed in the original camera

The original Cycles perspective camera maps raster samples to a virtual screen.
With depth of field enabled, it samples an aperture in camera Z=0 and aims at a
point on an axial focus plane. Its framing does not physically breathe with
focus distance. Existing shift changes the viewplane. Those expressions remain
behind the disabled branch of this patch.

The new, default-off branch instead samples a Gaussian thin lens with a tilted
normal, an aperture in that actual plane, a fixed body/sensor anchor and a
translated lens centre. This changes scene-intersecting rays, including occlusion
and defocus. Focus-plane orientation follows refraction, Scheimpflug and hinge
conditions; it is not a separately rotated blur plane. Enabled zero movement is
still the physical model: finite focus changes sensor distance and framing.

The patch reuses focal length, sensor dimensions/fit, canonical dimensionless
shift, focus distance/object/bone and all existing aperture controls. Circular,
polygonal and anamorphic pupil sampling are existing Cycles capabilities, mapped
into the new plane. They are not new bokeh features. Optional image-circle
clipping is an ideal binary angular coverage stop, not a realistic lens barrel.
Neither pupil redesign nor a more elaborate coverage model is needed to state
the core request: tilt, swing and movement-axis rotation with existing controls.

### Changed source layers

Paths below are relative to the pinned upstream source. Together they account
for all 17 files in the cumulative patch.

| Layer and files | Implemented change |
| --- | --- |
| `source/blender/makesdna/DNA_camera_types.h`; `source/blender/blenloader/intern/versioning_500.cc` | Persist enable, three angles, coverage diameter and three display toggles. New IDs default off/zero; schema-member migration disables old cameras and initializes missing display state without changing existing shift. |
| `source/blender/makesrna/intern/rna_camera.cc` | Expose controls, updates and millimetre shift aliases; canonical shift remains the only stored shift. Focus updates also tag camera geometry/redraw. |
| `source/blender/makesrna/intern/rna_camera_api.cc` | Expose guide vertices through `Camera.tilt_shift_guide_geometry`, requiring a matching camera object/datablock. |
| `scripts/startup/bl_ui/properties_data_camera.py`; `intern/cycles/blender/addon/ui.py` | Add grouped movements, guides and canonical Shift Animation controls; keep focus editable with DOF off because it affects physical framing. Explain approximate preview framing. |
| `source/blender/blenkernel/BKE_camera.h`; `source/blender/blenkernel/intern/camera.cc` | Compute lens/focus planes and forward coverage guide geometry, including evaluated object/bone focus and invalid/infinite geometry omission. |
| `source/blender/draw/engines/overlay/overlay_camera.hh` | Draw those guides using the actual BKE helper; standard viewport projection matrices remain unchanged. |
| `intern/cycles/blender/camera.cpp` | Synchronize evaluated optics, full camera-space focus targets, millimetre-to-metre conversion and sensor-fit/roll/flip-aware physical lens translation. |
| `intern/cycles/scene/camera.h`; `intern/cycles/scene/camera.cpp` | Add sockets, host optical preparation/guards, paired chief projection transforms, packed device state and conservative per-ray volume initialization. |
| `intern/cycles/scene/scene.cpp` | Reject unsupported camera configurations before shader/geometry device updates, including subdivision when either render or dicing camera uses the model. |
| `intern/cycles/kernel/types.h`; `intern/cycles/kernel/camera/camera.h` | Add aligned camera data and isolated enabled ray dispatch; sample physical aperture rays, clip them, compute sampled-ray differences and correct background Window anchoring. |
| New `intern/cycles/kernel/camera/tilt_shift_math.h`; `intern/cycles/kernel/CMakeLists.txt` | Share scalar float optics between host/device and register the header for kernel builds. The repository mirror is checked against this header. |

Existing focus-object/bone dependency relations are reused; the patch does not
modify depsgraph relation construction. Existing Cycles ray tracing, materials
and aperture random sampling remain the integration foundation.

### Ray model and conventions

The [optical derivation](optical-model.md) uses X right, Y down, Z scene-going.
Apply fixed-axis `Rz(axis) Ry(swing) Rx(tilt)` with tilt first, then reflect Y for
Cycles X right, Y up, Z scene-going. Reflect both aperture axes explicitly;
reconstructing one with a cross product would reverse its sign. Blender-local
guide coordinates use X right, Y up, negative Z scene-going.

Lengths are metres: one raw Blender unit is treated as one metre; lens/sensor
millimetres convert by `1e-3`. Scene display `scale_length` does not change the
physics, and camera object scale is removed. Angles store radians/display degrees.
Let `f` be focal length, `n` the lens normal, `C` the physical lens centre, `D`
manual focus distance, `A` the sampled tilted-plane aperture point and `q` the
upstream nominal raster-to-camera point:

```text
C.xy = viewplane_roll_flip(active_sensor_size * canonical_shift); C.z = 0
b = f / (n.z - f/D)
p = (-f*q.x/q.z, -f*q.y/q.z, -b)
h = 1 + dot(n,p)/f
origin = C + A
direction = normalize(h*A - p)
sharp plane: (n - (f/b)*(0,0,1)) dot (P-C) = f
```

`p` is sensor position relative to the lens; its shifted raster coordinates
cancel `C` exactly once so the body sensor stays fixed. Viewport pan/zoom do not
translate the physical lens. Manual focus anchors `C+(0,0,D)`; an evaluated
object/bone point uses `Q=P-C` and `b=f*Q.z/(dot(n,Q)-f)`, preserving off-axis focus.
DOF off sets aperture radius zero but retains breathing. Native manual focus is
finite and positive; exact infinite focus has standalone numerical evidence only.

The ray formula does not divide by `h`, so crossing infinite conjugacy is
continuous. Host validation rejects invalid/nonfinite inputs, grazing normals,
nonpositive/singular sensor distances, sensor/lens crossings and backward rays.
Its dimensionless margin is `1e-5`; plane tests scale that margin by relevant
optical lengths. Bounds include the full anamorphic ellipse and raster corners
padded by `1.5*filter_width+1` pixels. This is rejection, not silent clamping.

Every sampled aperture ray is intersected with camera-Z near/far planes. One-pixel
neighbors hold that same aperture sample and independently intersect the near
plane to form origin/direction finite differences. The enabled chief projection
subtracts `C` and applies `b/f` scaling; forward transforms apply the inverse.
Raw `rastertocamera` remains nominal for sensor reconstruction. This chief mapping
cannot uniquely invert a finite-aperture bundle. Generic camera position/distance
helpers keep body-anchor semantics; background Window directions receive explicit
lens-centre anchoring. Volumes conservatively initialize their stack per ray.

## Evidence and present limits

These are recorded prototype results, not fresh results generated by this brief.
The [M2](m2-validation.json), [M3](m3-validation.json) and [M4](m4-validation.json)
ledgers identify binaries, patches, fixtures, images and measurements by hash.
The [build guide](build-instructions.md) and milestone guides provide reproduction.

| Evidence | What it establishes, within its fixture domain |
| --- | --- |
| 14,120 double-reference checks; 39,214 shared-float checks | Conjugacy/refraction, Scheimpflug/hinge, unit covariance, shifts, focus, coverage, clipping and neighboring rays. Maximum float direction error `1.35967e-7`; aperture-origin error `9.07662e-10 m`. |
| Native CPU and retained HIP fixtures | Maximum centroid error about `.03663 px`; CoC `16.48236 px` vs analytic `16.46091 px`; tilted outer-target variance ratios about `.161/.162`; coverage, near/far rejection and volume absorption checks. |
| M3 interface/dependency fixtures | 2,107 actual BKE guide checks, 27 persistence checks and 755 animation/dependency checks; frame return and guide-toggle pixel invariance. Native interactions were inspected in private Sway/software OpenGL, not GNOME/Mutter. |
| Actual RX 6900 XT/gfx1030 build/render, HIP 7.2.53211 | Newly compiled/installed kernel; CPU/HIP use the same M4 executable with hard device overrides. All 19 render pairs passed predeclared bounds, 15 bitwise identical; maximum RGB RMSE `.0001215173`. |
| Disabled regression | Four original CPU buffers and 14 retained M3 CPU buffers remain bitwise identical in M4. M1 HIP versus M4 HIP maximum error is `9.536743164e-7`, not bitwise identity. |

The current enabled execution gate admits CPU or one non-HIPRT HIP device.
It rejects other GPU backends, multi-device configurations, non-perspective
cameras, motion blur, motion-vector passes, stereo/multiview and adaptive
subdivision. Frame-by-frame keyframed optics and focus updates were tested;
shutter-time optical or rigid-camera motion sampling was not implemented.
Solid/Eevee and the ordinary camera frame remain approximate; rendered roll/flip
framing, baking and arbitrary production scenes have no acceptance evidence.

M4 uniform-world boundary renders prove finite execution and unit weight, not
near-singularity direction/differential accuracy. Texture charts exercise filtering
without direct derivative-buffer equality. Existing provisional CPU/HIP smoke
failures are retained and reproduced on the unmodified baseline. No calibrated
exposure/PDF, real-lens aberration, diffraction, gradual vignetting, accessibility
or broad hardware/OS acceptance follows from the recorded tests.

The completed-render benchmark compares ordinary, enabled-zero and enabled-tilt
modes with warming and three rotated repeats per backend. Framing, texture and
intersection workload change, and session/synchronization costs are included.
Those timings do not isolate camera-math overhead or establish general speedups.

## Proposed release work, in priority order

The following are recommendations and decisions to resolve, not implemented
features or commitments by Blender maintainers. Correctness for the agreed
release scope is required; additional modes may remain explicitly unsupported.
Neither all-backend support nor a calibrated radiometric lens is a prerequisite
for a first release unless the agreed design promises it.

1. **Agree the smallest useful product contract.** Begin with opt-in tilt, swing
   and axis rotation, reusing existing shift/focus/aperture. Decide whether ideal
   image-circle clipping and its guide belong in the initial release. Confirm
   movement signs/order, focus convention, breathing and metre/unit behavior.
   Physical lens translation and breathing are this prototype's model choices;
   upstream could choose compatibility-preserving framing with an explicit
   optical contract, revised equations and tests. Do not silently mix models
   or treat enabled-zero as legacy-equivalent.
   Put representative creative tasks and accepted limitations in a design task
   before expanding the patch. Keep existing-camera compatibility a release gate.
2. **Complete projection consumers and a predictable viewport workflow.** Audit
   camera framing/culling, camera helpers, picking, overlays, render borders,
   shader camera/Window transforms, baking, compositing and tracking consumers.
   Decide which must use physical chief projection and which have documented
   body-anchor semantics. Make camera framing agree where feasible; explicitly
   design Eevee/Solid behavior. Verify rendered pan/zoom, roll/flip, crop/aspect
   and off-axis focus rather than inferring correctness from guide geometry.
3. **Define motion and geometry interactions.** To support motion, implement shutter-time sampling
   of camera transforms and optical state, consistent projection/motion vectors
   and deformation/rolling-shutter behavior where supported. Frame animation
   passing is insufficient. Derive/test adaptive subdivision footprints and
   dicing-camera behavior; define stereo lens/eye transforms and convergence.
   Retain explicit restrictions until each combination passes appropriate tests.
4. **Establish the supported device matrix.** Build and render on every backend
   intended for release, including relevant CPU architectures, HIP/HIPRT, CUDA,
   OptiX, Metal and oneAPI as applicable. Test compiler math modes, device data
   layout, multi-GPU and mixed-device paths. One RDNA2 result supports that route
   only. Keep default-off regression and finite/invalid-domain checks per route.
5. **Harden numerical and optical integration.** Independently test directions,
   clipping and differential accuracy near accepted domain boundaries and across
   scale/extreme focus/shift/aspect/filter combinations. Review normalization and
   overflow, fast-math effects, large world coordinates, invalid animation values
   and diagnostic quality. Confirm aperture sampling/weight/PDF expectations
   with Cycles integrators; separate normalized artistic exposure from any future
   calibrated lens model. Avoid broadening thresholds merely to pass renders.
6. **Review permanent schema, API and UX.** Replace fork-specific migration with
   the upstream-approved versioning strategy; cover old files, linked data,
   overrides, undo/redo, copying, drivers and save/reopen. Review property names,
   angle ranges, nonanimatable millimetre aliases, unit behavior and guide API.
   Resolve duplicated optical preparation between BKE guides and Cycles while
   respecting module boundaries. Correct the current RNA tooltip's stale
   “CPU only” claim and milestone-specific error wording. Test real creative
   workflows, accessibility and target desktop/platform configurations.
7. **Move verification and profiling into maintainable upstream form.** Port
   useful independent invariants and deterministic scenes into Blender/Cycles
   test infrastructure with reviewed tolerances and reproducible assets. Add
   integration tests for every released consumer/mode and rejected combination.
   Profile ray generation separately, plus paired production scenes and disabled
   hot-path/device-memory costs; the existing completed-render ratios cannot
   answer those questions. Name maintenance ownership and document public
   conventions, limitations and release changes.

## Upstream case and alternatives

The useful outcome is independent control of the plane of sharp focus and
composition: for example, hold a receding surface sharp at an open aperture, or
place a narrow focus region through a scene while retaining the desired viewpoint.
Ordinary shift, camera placement and stopping down already solve many tasks;
examples should demonstrate where tilt/swing provides a distinct useful result.
Creative control is a valid motivation, but an upstream proposal also needs a
clear workflow, reasonable scope and a credible maintenance/integration case.

An [OSL custom camera](https://docs.blender.org/manual/en/5.1/render/cycles/osl/camera.html)
is another implementation route. Its GPU path is limited to OptiX in that manual;
the native HIP result gives a concrete reason to evaluate a compiled camera route,
without claiming acceptance of every backend. Compare that alternative's user
workflow and maintenance costs before deciding that permanent Camera DNA/RNA
and cross-module integration are warranted.

Blender's [contribution guidance](https://developer.blender.org/docs/handbook/contributing/)
asks for motivation, alternatives, limitations, workflow and maintenance planning;
its [design guidance](https://developer.blender.org/docs/handbook/design/ideas_concept/)
starts with the user problem and outcome. A bounded design proposal with this
implementation/evidence attached would make the discussion concrete. This brief
does not authorize submitting it, contacting maintainers or publishing a patch.
