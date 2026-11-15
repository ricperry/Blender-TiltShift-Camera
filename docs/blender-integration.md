<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Pinned Blender integration map

All paths below are relative to `work/blender` at the
[source pin](source-revision.json). This is a source map and implementation plan,
not a statement that native integration is complete.

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
initializers. Default enabled state must be false, movements zero and coverage
unbounded; focal/sensor/focus/aperture values reuse existing camera controls.
Older files require explicit defaults in
`source/blender/blenloader/intern/versioning_500.cc::blo_do_versions_500`, with
schema/member guards appropriate to the fork; version numbers alone must not
accidentally enable old cameras or reinterpret unset fields. Test old-file loads
and round trips rather than assuming new-ID initialization covers deserialization.

Existing perspective rays derive `Pcamera` from `rastertocamera`, including sensor
fit, pixel aspect, viewplane shift, viewport border and crop. `blender_camera_viewplane`
uses `shift = 2*(aspectratio*bcam->shift + offset*aspect*2)`, then roll/flip and
viewplane offsets. Rebuilding physical sensor coordinates from raw resolution
alone would lose these behaviors. Existing FOV is
`2 atan(0.5 sensor_size/lens/aspectratio)` and does not depend on focus distance.
The enabled physical branch must deliberately change finite-focus framing.

`blender_camera_matrix` flips Blender's camera −Z to Cycles +Z and removes object
scale. DOF radius is `lens_mm*1e-3/(2*fstop)`. Focus objects use absolute axial
camera-Z distance, including bone targets; without an object, focus_distance is
used directly. Existing synchronization zeros focus distance when DOF is disabled,
so physical breathing requires a separate enabled-mode focus value even for a
pinhole. Aperture sampling already provides circle/polygon and anamorphic ratio;
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

The scripts reserve `tilt_shift_enabled` as a **proposed** future RNA capability
probe. Current upstream lacks it. `--require-feature` therefore fails clearly;
the probe must be updated with the final native identifier and actual optical tests.
