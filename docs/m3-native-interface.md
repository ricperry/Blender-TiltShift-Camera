<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# M3 native camera interface

The cumulative M3 source patch is
`patches/blender-v5.3.0-tilt-shift-m3.patch`, against the recorded official 5.3.0
pin. The committed M2 patch remains immutable historical evidence. M3 adds the
native Camera Data interface, persisted display settings, physical viewport
geometry and interface/animation fixtures. The [M3 evidence ledger](m3-validation.json) records passed geometry, persistence,
animation, retained regression and isolated native GUI checks. This completes the
bounded M3 native interface gate; the scope and remaining limits are recorded below.

## Creative workflow

Select a perspective camera, use Cycles with CPU rendering, and enable **Tilt-Shift**
in Camera Data. Adjust Lens Tilt, Lens Swing and Movement Axis Rotation; angles
are shown in degrees and stored in radians. Rotation order remains fixed optical
`Rz(axis) Ry(swing) Rx(tilt)`, with tilt first. The optical units and focus
conventions in [M2](m2-native-camera.md) remain authoritative.

Horizontal and Vertical Shift show millimetres. They are invertible views of the
existing `shift_x`/`shift_y` fields: `shift_mm = S_mm * shift`, with the same active
sensor size for both axes. `S` is sensor height for VERTICAL, sensor width for
HORIZONTAL and AUTO, including portrait AUTO. Pixel aspect and resolution do not
change this conversion. There is no additional serialized shift. Sensor-fit or
sensor-size changes therefore update the displayed millimetres immediately.

Keyframe dimensionless shifts in the collapsed **Shift Animation** child panel,
while the physical camera is enabled. The ordinary Lens panel retains its original
shifts in other modes. The millimetre aliases deliberately cannot
be animated: independent curves on an alias and its canonical property would
compete to overwrite one field. Lens movements and existing focus fields retain
ordinary Blender keyframe/driver support. Motion blur and vector passes remain
explicitly unsupported by the M2 guard.

The existing Depth of Field panel supplies focus object/bone or manual Focus
Distance. Focus stays editable with the aperture disabled because physical
pinhole framing still breathes. Its checkbox controls the aperture; existing
F-Stop, blade count, rotation and ratio remain in its Aperture child panel.
Image Circle zero is explicitly labelled **unbounded**; a positive diameter is
rear-focal-plane angular coverage, in millimetres.

The native enable header remains reachable after changing camera type or render
engine. Unsupported controls show the perspective/Cycles requirement. Solid,
Eevee and the ordinary camera frame use nominal projection and are labelled as
approximate. Use a Cycles Rendered viewport or final render for physical framing.
M3 does not modify the standard viewport projection matrices.

## Physical guides and their limits

Three persisted display toggles default false: lens plane, focus plane and image
circle. They are independent of rendering and obey viewport Extras visibility.
The real native camera overlay obtains its vertices from
`BKE_camera_tilt_shift_guides`; the RNA method
`Camera.tilt_shift_guide_geometry(camera_object, view_roll=0, view_flip_x=False)`
returns those same vertices for numerical verification and integrations.
Use an evaluated camera object and its evaluated Camera datablock for evaluated
animation/targets. The object must use that datablock; shared-camera datablocks
work without assuming one global owning object.

Outputs are `(valid, focus_valid, circle_valid, sensor_distance, lens, focus,
circle_x, circle_y, circle_z)`. Lens/focus arrays contain four flattened XYZ
vertices each; each coverage coordinate array contains 64 components in matching
order. Coordinates are **unscaled Blender camera-local metres**, X right, Y up,
negative Z scene-going. Apply a scale-normalized camera object transform for
world coordinates, matching Cycles. Display scene-unit scale does not change
optical physics. The helper's validity describes guide geometry; the full Cycles
render guards still additionally validate aperture, clipping and padded raster
bounds.

The blue lens rectangle lies through the translated physical lens centre with
M2's actual lens normal and reflected aperture axes. The green rectangle lies in
the actual sharp plane `(n-(f/b)k)·(P-C)=f` and is centred on the manual focus
anchor or full evaluated object/bone target. These rectangles have side length
Display Size; their finite extent is a visualization choice, not glass diameter
or an assertion that only that region is sharp. A valid vertical sharp plane is
retained, including zero or negative camera-axis intercepts.

The amber closed curve is the **angular coverage boundary projected forward**
onto camera depth Display Size. Its rear-focal circle is
`r=-f*n+R*(ex*cos(theta)+ey*sin(theta))`; displayed body points are
`C+(DisplaySize/r.z)*r`. Thus it is a true chief-ray coverage cone section, not a
fixed sensor circle, vignette or the physical lens rim. It is drawn forward for
visibility beside a metre-sized camera icon. The actual sensor intersection
would use `C+(-b/r.z)*r`, on the opposite side of the lens. Changing Display Size
changes guide presentation only.

The dimensionless singularity margin is `1e-5`, matching the M2 float-domain
convention. Nonpositive/singular sensor distances, backward normals and invalid
focus targets suppress guides. A near-zero full focus-plane normal suppresses
the plane at infinity; zero axial component alone does not. Infinite or
unbounded image circles have no finite curve. The continuous boundary is checked
analytically for a backward/asymptotic crossing before sampling; no segment is
joined across infinity. Nonfinite or excessive vertices are omitted, never
replaced with clamped fake planes.

The optional roll/flip arguments use the same BKE viewplane offset transform as
M2 and the active camera-view overlay passes those values. The default describes
the final render camera. Parameterized geometry verification does not establish
rolled/flipped rendered-viewport framing acceptance; M3's visual workflow evidence
is restricted to the standard unrolled, unflipped view.

## Persistence, dependencies and reproduction

A schema member check initializes all three display settings false for upstream
and M2 files without touching existing M2 optical or canonical shift fields.
New IDs initialize false; save/reopen persists display state and ordinary animation.
Existing camera depsgraph relations already track the focus object transform and
bone completion independently of `use_dof`; M3 reuses those relations. Focus RNA
updates now also tag the camera ID for geometry updates and redraw, including
manual physical focus while DOF is off.

Preserve `work/install-blender-m2` and install the GUI-capable M3 build separately
at `work/install-blender-m3`. Use isolated configuration/resources, sequential
4 GiB runtime scopes, and the build limits in [build instructions](build-instructions.md).

```sh
python3 scripts/dev.py patch --milestone m3
work/install-blender-m3/blender --background -noaudio --factory-startup \
  --python-exit-code 1 --python scripts/blender_m3_validation.py -- \
  --output work/m3-validation --case geometry
work/install-blender-m3/blender --background -noaudio --factory-startup \
  --python-exit-code 1 --python scripts/blender_m3_validation.py -- \
  --output work/m3-validation --case persistence \
  --upstream-file work/m2-old/upstream-camera.blend \
  --m2-file work/m2-validation/native-camera.blend
work/install-blender-m3/blender --background -noaudio --factory-startup \
  --python-exit-code 1 --python scripts/blender_m3_validation.py -- \
  --output work/m3-validation --case animation
work/install-blender-m3/blender --background -noaudio --factory-startup \
  --python-exit-code 1 --python scripts/blender_m3_validation.py -- \
  --output work/m3-regression --case m2-regression
python3 scripts/run_m3_guards.py --blender work/install-blender-m3/blender \
  --output work/m3-validation
```

Use the actual preserved file paths on the host. The fixture records input hashes,
new binary/script/patch hashes and numeric results. Geometry checks test the
actual native overlay vertices, focus convergence, image-circle coverage,
mm mapping, ownership, object/bone focus and singular omission. Animation checks
change optical fields, canonical shift and focus, render centroid predictions,
return to a deterministic earlier frame, and animate focus targets/bones while
DOF is off. A repeated enabled render with all three guide toggles changed must
remain bitwise identical. The M3 guard host runner reuses the immutable expected
rejection map, requires fresh complete results and Blender's expected sticky-error
exit one, and records the actual M3 patch/fixture hashes. Original M1/M2 fixtures
and shared float header remain unchanged.

For visual inspection, launch `scripts/blender_m3_gui_fixture.py -- --output
work/m3-gui` only on the agent-owned private display. It prepares the real native
Camera Data panels and guides, writes `gui-ready.json` after redraw, and keeps the
window open for the parent harness to capture and close. Private Sway/software
OpenGL evidence does not establish GNOME/Mutter, human workflow, accessibility,
physical printing, production optics or HIP support. M4 still requires an actual
new RDNA2 build and render.

## Background acceptance evidence

The final GUI-capable native binary passed 2,107 actual BKE guide checks, with
maximum absolute numeric error `2.45756246e-7`, plus 27 persistence checks and
755 animation/dependency checks. Six animation renders measured a maximum
centroid error `.028071 px` against `.22 px` tolerance. Returning to frame one
restored bitwise identical pixels. Enabling all three guide toggles likewise left
the enabled render bitwise unchanged. Focus-object animation changed actual
rendered breathing while DOF was off; bone animation changed evaluated guide
sensor distance `.0560497306 → .0524002165 → .0560497306 m` on a frame return.

All 14 retained M2 measured linear RGBA buffers match the immutable M2 evidence
bitwise. The four disabled M1 baseline scenes also match bitwise (`RMSE=0`, maximum
RGB error `0`). All eight retained explicit rejections passed the M3 guard host
runner with current M3 source provenance and its expected Blender exit one.
The cumulative patch also applies to the exact recorded upstream pin using a
separate temporary index; upstream HEAD and its actual index remain unchanged.
The ledger records artifact and input hashes. Both standalone optical CTest
targets also passed using `/usr/bin/ctest`; the original kernel helper mirror
remains byte-identical.


## Native GUI acceptance

The final binary ran in an agent-owned 1600×1000 headless Sway/pixman session
using software OpenGL/llvmpipe. The real registered Camera Data panel remained
readable at its original 282-pixel width, including explicit millimetre units.
Private pointer/keyboard interactions toggled off the focus guide alone, restored
it, entered **4 mm** horizontal shift, expanded canonical Shift Animation controls,
and inspected active **2 m** focus with DOF unchecked and aperture controls disabled.

An actual Ctrl-S saved the edited fixture. A separate background readback
confirmed canonical `shift_x=.1111111119389534`, its mapped view `4.0 mm`, `shift_y=0`,
sensor width `36 mm`, disabled DOF and all three saved guide toggles true. The
installed camera/Cycles UI scripts match their source bytes. The ledger hashes
screenshots, readiness/readback JSON and the saved `.blend`. All task-owned GUI,
input and compositor processes were stopped afterward.

This is bounded native interface acceptance under isolated Sway/software OpenGL.
It establishes neither GNOME/Mutter nor human, screen-reader or cross-platform
acceptance. Standard Solid/Eevee/camera-frame projection remains approximate;
rolled/flipped rendered-viewport framing, production optics and new-camera HIP
remain outside this gate. M4 requires separately authorized RDNA2 build/render work.
