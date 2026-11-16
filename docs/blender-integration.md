<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Pinned Blender integration map

All paths below are relative to `work/blender` at the
[source pin](source-revision.json). M2 now implements the native CPU patch;
[its implemented conventions and acceptance limits](m2-native-camera.md) take
precedence over the original proposed UI map below. The bounded static CPU gate
passed; see [measured evidence](m2-validation.json). M3 panels, physical guides and animation fixtures are implemented in the
[interface patch](m3-native-interface.md); [bounded M3 acceptance](m3-validation.json)
includes actual isolated native GUI interactions and passes with documented limits.

| Layer | Path and existing entry point | Required work |
|---|---|---|
| Persistence | `source/blender/makesdna/DNA_camera_types.h`, `Camera`, `CameraDOFSettings` | Add opt-in fields/defaults and old-file versioning; preserve existing fields |
| RNA | `source/blender/makesrna/intern/rna_camera.cc`, `rna_def_camera`, `rna_Camera_update` | Expose units/ranges, animation and render update notifications |
| UI | `scripts/startup/bl_ui/properties_data_camera.py`, `DATA_PT_lens`, `DATA_PT_camera_dof` | Group enabled movements, focus, aperture and coverage with useful disabled states |
| Dependencies | `source/blender/depsgraph/intern/builder/deg_builder_relations.cc`, `DepsgraphRelationBuilder::build_camera` | Existing DOF focus-object/bone relations can be reused; verify animation updates |
| Sync | `intern/cycles/blender/camera.cpp`, `BlenderCamera`, `blender_camera_from_object`, `blender_camera_sync` | Convert units, movement signs, focus and evaluated settings |
| Scene camera | `intern/cycles/scene/camera.{h,cpp}`, `Camera::update` | Add sockets, validate/precompute optical state, preserve border/aspect transforms |
| Device data | `intern/cycles/kernel/types.h`, `KernelCamera` | Upload compact float state; preserve 16-byte structure alignment |
| Sampling | `intern/cycles/kernel/camera/camera.h`, `camera_sample_perspective`, `camera_sample_aperture` | Isolated enabled dispatch, physical rays, clipping, footprints and throughput |
| Regression | `intern/cycles/test/kernel_camera_projection_test.cpp`, `tests/python/cycles_render_tests.py` | Unit tests plus deterministic enabled/disabled rendered fixtures |

These symbols were checked against the pin; they remain internal upstream APIs.
`source/blender/blenkernel/intern/camera.cc::camera_init_data` uses
`INIT_DEFAULT_STRUCT_AFTER`, so new-camera defaults belong in DNA member
initializers. Proposed enabled state is false and new angular movements zero;
existing shift values are preserved. Coverage is unbounded in the optical
reference; the proposed native defaults and unresolved
coverage UI encoding are described below. Focal/sensor/focus/aperture values reuse
existing camera controls.
Older files require explicit defaults in
`source/blender/blenloader/intern/versioning_500.cc::blo_do_versions_500`, with
schema/member guards appropriate to the fork; version numbers alone must not
accidentally enable old cameras or reinterpret unset fields. Test old-file loads
and round trips rather than assuming new-ID initialization covers deserialization.

## Tilt-shift controls (M2/M3)

This table records the M2/M3 interface. M2 implements the enable,
three angle fields and image-circle diameter; M3 adds physical shift views,
panels and visualization toggles, with [implemented workflow details](m3-native-interface.md). Implemented RNA identifiers
are listed in [the M2 guide](m2-native-camera.md). Names below are UI labels. Angular controls display degrees and store radians. Production
angle/shift limits remain subject to float-domain and rendered validation rather
than an arbitrary range chosen here.

| Requested control | Proposed meaning / storage | Proposed disabled-safe default |
|---|---|---|
| Enable Tilt-Shift | Opt into physical Cycles ray generation; proposed probe `tilt_shift_enabled` | False; use original upstream branch |
| Lens Tilt (degrees) | Fixed-X optical rotation Rx | 0° |
| Lens Swing (degrees) | Fixed-Y optical rotation Ry | 0° |
| Tilt/Swing Axis Rotation (degrees) | Fixed-Z rotation Rz of the movement/aperture frame; Rx first, then Ry, then Rz | 0° |
| Horizontal Shift (physical millimeters) | Sensor-relative framing movement; invertible RNA view of existing `Camera.shiftx`, with sensor-fit-aware scale and tested sign | Derived from existing shift; no additional stored shift |
| Vertical Shift (physical millimeters) | Sensor-relative framing movement; invertible RNA view of existing `Camera.shifty`, with sensor-fit-aware scale and tested sign | Derived from existing shift; no additional stored shift |
| Image Circle Diameter (millimeters) | Twice the prescribed rear-focal-plane angular coverage radius from the [optical model](optical-model.md#aperture-blur-and-coverage) | A diameter of 0 means unbounded; positive finite values specify diameter |
| Display Focus Plane | Viewport overlay derived from the actual sharp-focus plane, including the plane-at-infinity case | False |
| Display Lens Plane | Viewport overlay derived from tilted lens centre, normal and aperture frame | False |
| Display Image Circle | Viewport coverage overlay derived from the angular stop and sensor intersection | False |

Reuse existing `Camera.lens`, `sensor_x`, `sensor_y`, `sensor_fit`, `dof.focus_object`,
`dof.focus_subtarget`, `dof.focus_distance`, `dof.use_dof`, `dof.aperture_fstop`,
`dof.aperture_blades`, `dof.aperture_rotation` and `dof.aperture_ratio` rather than
introducing independent focal length, sensor, focus or aperture values. Focus
remains meaningful for enabled physical breathing even when aperture/DOF is off.
Physical shift controls must update the existing dimensionless shift fields;
serialization must never hold two competing shift states. Their exact signed
conversion must be tested across sensor fit, pixel aspect and raster orientation.

A finite user-specified image-circle diameter is converted from mm to metres and
halved before optical sampling. It is defined at the rear focal plane, not as a
fixed circle on the moving sensor; at finite focus or tilt its sensor footprint
changes. Native RNA encodes the unbounded reference default as zero, not IEEE infinity.
M3 must present that special value clearly; persistence/migration is part of M2
validation. The three display
toggles affect visualization only; they must not alter rendered rays or exposure.

Existing perspective rays derive `Pcamera` from `rastertocamera`, including sensor
fit, pixel aspect, viewplane shift, viewport border and crop. `blender_camera_viewplane`
uses `shift = 2*(aspectratio*bcam->shift + offset*aspect*2)`, then roll/flip and
viewplane offsets. Rebuilding physical sensor coordinates from raw resolution
alone would lose these behaviors. Existing FOV is
`2 atan(0.5 sensor_size/lens/aspectratio)` and does not depend on focus distance.
The enabled physical branch must deliberately change finite-focus framing.

`blender_camera_matrix` flips Blender's camera −Z to Cycles +Z and removes object
scale. DOF radius is `lens_mm*1e-3/(2*fstop)`. Legacy focus objects use absolute axial
camera-Z distance, including bone targets; without an object, focus_distance is
used directly. M2 preserves the full object/bone target and solves its physical
sensor distance. It also synchronizes manual focus while DOF is off, so physical
breathing remains meaningful for a pinhole. Aperture sampling already provides circle/polygon and anamorphic ratio;
the reference currently models a circular aperture only.

The legacy differentials deliberately ignore DOF. New chief-ray derivatives must
be compared to independent neighboring raster samples. Legacy clipping assumes
aperture origins lie at camera `z=0`; a tilted aperture requires intersections
with the intended camera-Z clip planes. `Camera::viewplane_bounds_get`,
`transform_full_raster_to_world`, `device_update_volume` and
`world_to_raster_size` assume the existing projection; volume initialization and
adaptive subdivision/dicing require correction or a clearly bounded restriction.
Kernel point-to-raster/motion-vector mappings need a matching inverse.
In particular, `kernel/camera/camera.h::camera_world_to_ndc`,
`camera_motion_vector` and `camera_motion_vector_direction` must agree with enabled
ray generation. `BlenderSync::sync_camera_motion` in `blender/camera.cpp` and its
call sites in `blender/object.cpp` synchronize time samples; new optical parameters
need a deliberate motion-blur policy alongside existing animated FOV and rigid
camera motion. Until implemented, reject or document unsupported animated optical
movements instead of implicitly treating center-time settings as fully supported.

EEVEE, camera outlines, overlay selection, motion tracking and compositing are
not automatically made physically correct by a Cycles kernel patch. A headless
build provides no UI/Wayland or human-workflow evidence. M3 must communicate any
viewport mismatch and test serialization, animation and dependency invalidation.

The scripts use `tilt_shift_enabled` as the native RNA capability probe. The
unmodified upstream baseline lacks it; the M2 patch implements it. Presence alone
does not pass the quantitative [native fixtures](m2-native-camera.md).

The pinned upstream `tests/files/render/camera/camera_depth_of_field.blend` and
`camera_polygonal_bokeh.blend` were opened read-only with the built Blender.
They contain enabled perspective DOF fixtures with a 35 mm circular aperture and
a 50 mm three-blade aperture respectively. Successful loading is inventory
evidence, not an upstream render-regression pass. The local inspection log is
`work/upstream-scene-inventory.log`.
