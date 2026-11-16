<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Photographic comparisons

The [demo generator](create_demo_comparisons.py) creates **17 active editable scenes**
under ignored `work/demo-comparisons/` and refreshes the shared photo/video gallery.
Explore the [photo and video gallery](https://ricperry.github.io/Blender-TiltShift-Camera/);
click an image for its full resolution PNG, or follow its `.blend` and JSON links.
Generation remains local; the public gallery provides copies of the active artifacts.

The suite combines a botanical product still life, the existing full-scale city,
and level architectural shift views. The still life's three detailed paper
specimens span different depths on a tabletop. A tilt-shift **−10° tilt** aligns its
sharp plane with that surface at a wide pupil. The ordinary comparison optimizes
focus across the same details. The city uses **+10° tilt** for selective focus;
an additional ordinary camera optimizes both focus and pupil to approach its blur.
These comparisons demonstrate rotated focus, rather than treating ordinary DOF
as incapable of producing blur or broad sharpness.

The HERBARIUM sheet has a procedural printed grid: 5 mm minor spacing
with 0.25 mm lines and 25 mm major spacing with 0.40 mm lines. Muted green ink
is applied to its top face only; the bottle label and carton retain plain paper.
Object-local XY coordinates are metres after scale application, so the print
follows the sheet's translation and rotation. It changes base colour only;
paper geometry, focus targets, camera settings and lighting remain unchanged.

## Generate and render

For a fresh input set, capture the generator source in the new output directory,
then run the patched Blender built by this repository without editing that source
between these steps. The animation generator requires this snapshot's SHA-256
to match the photo manifests' `source_sha256`:

```sh
mkdir -p work/demo-comparisons/4k
cp -n examples/create_demo_comparisons.py work/demo-comparisons/4k/render-generator-source.py
work/install-blender-m4/blender --background -noaudio --factory-startup --threads 2 \
  --python-exit-code 1 --python examples/create_demo_comparisons.py -- \
  --case all --resolution 3840 2160 --samples 256 --backend HIP \
  --output work/demo-comparisons/4k
```

`cp -n` preserves any existing snapshot. For older rendered artifacts, retain the
original matching source snapshots; copying today's source does not repair their
provenance. If the source has changed, generate a fresh set in a new output
directory and capture its source there. Pass that directory as `--source` when
generating animations. The photo generator does not capture its own source.

The defaults are 3840 × 2160, 256 samples, seed 71 and a single HIP device.
Use `--samples 512` or higher when fine bokeh noise remains visible. The generator
disables denoising, adaptive sampling, motion blur, compositing and sequencing.
The same AgX view transform and look apply to every pair. It refuses a missing
HIP device or multiple HIP devices, disables HIPRT and other devices, and applies
an explicit Cycles device override. Use `--backend CPU` for CPU rendering.
Every saved `.blend` retains CPU settings and relative render paths for portability.

`--case` can be repeated to render a subset; `--list` lists case names.
`--save-only` creates editable files and manifests without rendering. To preview:

```sh
work/install-blender-m4/blender --background -noaudio --factory-startup --threads 2 \
  --python-exit-code 1 --python examples/create_demo_comparisons.py -- \
  --case table-native --case table-ordinary-best \
  --resolution 1920 1080 --samples 128 --backend HIP \
  --output work/demo-comparisons/preview
```

Each invocation refreshes the unified `work/demo-gallery/index.html` using its
selected photo output directory and the default video directory. The photo
directory's old `index.html` redirects there. Saving or rendering
a case replaces that generated case's files; choose another `--output` to retain
an earlier run. Outputs are restricted to the project's ignored `work/`.
No packaged example or user image is overwritten. Scenes contain no external
images, linked assets, image-space blur, add-ons or execute-on-load handlers.

To refresh the unified gallery from existing manifests with ordinary Python,
without rendering or changing saved scenes and provenance:

```sh
python3 examples/build_demo_gallery.py
```

See [gallery reproduction and alternate input directories](DEMO_GALLERY.md).
The original Blender entrypoint also delegates to the same builder:

```sh
work/install-blender-m4/blender --background -noaudio --factory-startup --threads 2 \
  --python-exit-code 1 --python examples/create_demo_comparisons.py -- \
  --gallery-only --output work/demo-comparisons/4k
```

## Optional focus-plane intersections

The six focus comparisons have a **Show focus planes** button after guide generation.
It toggles both photographs together; originals start unobstructed. The opacity
slider defaults to 45%. Buttons and sliders support normal keyboard navigation.
Generate separate overlays from the ten existing saved scenes, without rendering,
saving scenes, or changing their manifests:

```sh
work/install-blender-m4/blender --background -noaudio --factory-startup --threads 2 \
  --python-exit-code 1 --python examples/create_demo_comparisons.py -- \
  --gallery-only --focus-overlays --output work/demo-comparisons/4k
```

The [helper](demo_focus_overlays.py) casts a dense deterministic **960 × 540**
chief-ray grid against the evaluated scene geometry for each 4K photograph.
It reconstructs each visible surface position from that camera's first mesh hit,
then evaluates its signed perpendicular distance to the exact optical sharp plane.
A translucent green overlay marks the plane's intersection with scene surfaces;
its brighter centre is closest to the plane. Empty air and occluded surfaces stay
unmarked. There are no dot grids, numbered circles, or coordinate graphs.

A zero-thickness plane would be hard to see, so the overlay uses an explicitly
finite, feathered band: **±4 mm** for the product scenes and **±0.65 m** for the
city. Each pair uses the same thickness. This is a geometric display tolerance,
independent of aperture, not the full depth of field or an image-sharpness mask.
Tilt-shift tilt follows the printed paper; an ordinary plane crosses it in a stripe.
Stopping down can broaden acceptable sharpness without changing that ordinary
plane. Swing and movement-axis rotation change the direction of the intersection.
The masks use nearest-neighbour display without interpolating across depth edges.
Subpixel geometry may be missed at the mask's one-quarter 4K linear resolution.

For lens-relative `Q = (camera_x, camera_y, -camera_z) − C`, the tilt-shift plane is
`(n − (f/b)·Z)·Q = f`; the ordinary plane is `Qz = D`. Tilt-shift `b` and optical
centre `C` come from the evaluated guide API; the plane is checked against its
vertices. Rays and projection use the actual sensor distance, saved view frame,
and full evaluated camera pose. The existing `Rz(axis) Ry(swing) Rx(tilt)`
convention applies. Plane normals and visible depths below `1e-10` are rejected;
float32 guide checks allow `2e-4 × max(1,D) m`, and chief rays must reproject
within `2e-5` normalized UV. Signed distances are normalized by the plane normal's
length and use metres, including for the tilt-shift equation's unnormalized normal.

Separate `*.focus.png`, `*.focus.json`, `*.focus-surface.f32.z`, and
`focus-guides.json` record the masks, source hashes, projection checks, display
thickness and coverage. Surface files contain zlib-compressed, row-major,
little-endian float32 pairs `[camera-forward depth, signed plane distance]` in
metres, top-left first, with NaNs for missing hits. Original PNGs, `.blend` files,
JSON render manifests and source snapshots remain unchanged. Plain
`--gallery-only` reuses source- and mask-verified cached overlays without opening
scenes; stale or missing masks require `--focus-overlays`. The helper also runs
directly with `--output` to regenerate these artifacts alone.

This is a chief-ray geometry reference. It does not follow reflections, refraction,
material transparency or finite-aperture visibility changes; the enormous fitted
city pupil makes the latter especially significant. Actual rendered blur can
extend outside the marked geometric intersection. Ordinary DOF can broaden
sharpness or approximate blur, but cannot independently rotate its exact sharp
plane while preserving viewpoint, framing and pupil.

## Cases and controls

| Cases | Purpose |
| --- | --- |
| `table-native`, `table-ordinary-best` | −10° tilt versus focus optimized ordinary DOF at the same physical pupil |
| `table-ordinary-f16`, `table-native-f16` | Stopping down both cameras to a pupil equivalent to tilt-shift f/16 |
| `table-native-zero` | Tilt-shift finite-distance breathing and zero-angle focus baseline |
| `swing-native`, `swing-ordinary-best` | 10° swing and ordinary focus comparison |
| `axis-native`, `axis-ordinary-best` | −10° tilt with movement axes rotated 45° |
| `city-native`, `city-ordinary-best` | +10° city tilt versus focus optimized ordinary DOF at a matched pupil |
| `city-ordinary-blur-fit` | Ordinary focus and aperture fitted to tilt-shift scalar blur on visible surfaces |
| `city-native-object` | Object focus reproducing the tilt-shift city's manual sharp plane |
| `shift-x-native`, `shift-x-ordinary` | Horizontal shift with a level architectural camera |
| `shift-y-native`, `shift-y-ordinary` | Vertical shift with a level architectural camera |

The active gallery contains **17 images in 11 paired comparisons**. Aperture
polygon/rotation, anamorphic aperture ratio, and image-circle demonstrations are
outside this suite's current scope. Their five historical case definitions remain
available only through explicit `--case` names; default generation and `--case all`
skip them, and the gallery never includes their three sections. Existing generated
files are retained without rerendering or deletion.

Shift, focal length, focus distance/object and aperture f-stop also exist in
ordinary Cycles. The suite shows how they work with tilt-shift lens movements; they
are not claimed as unique tilt-shift capabilities.

## How the ordinary cameras are optimized

All cameras keep depth of field enabled. With tilt-shift focal length `f` and actual
sensor distance `b`, an ordinary focal length `b` matches the tilt-shift chief-ray
field of view. Its f-number is multiplied by `b/f` to match the **physical pupil
diameter**. Sensor dimensions, fit, normalized shifts and orientation are shared.
For shift parity the ordinary lens origin also moves by the tilt-shift optical centre
`C = (sensor_width × shift_x, sensor_width × shift_y, 0)` in camera coordinates.
Ordinary architectural focus uses the same tilt-shift zero-angle sharp plane.

At a fixed matched pupil, `*-ordinary-best` chooses the harmonic mean of the
nearest and farthest target depths. This minimizes maximum circle-of-confusion
diameter over those targets. Botanical targets are the three printed detail
positions. City targets are hits from a deterministic **21 × 13 chief-ray grid**
against actual scene mesh surfaces, excluding empty background. This is an
explicit focus objective, rather than an arbitrary poor focus setting.

`city-ordinary-blur-fit` goes further: it fits both ordinary focus and physical
pupil diameter to tilt-shift sensor blur on the same visible surface samples. The
objective is mean squared error in circular-pupil RMS blur diameter. A global
piecewise stationary-point search covers reciprocal focus and the pupil bounds.
Its aperture range uses Cycles' effective `1e-5` f-stop floor through the RNA hard
maximum; **0.1 is only a UI soft minimum**, and does not constrain the fit.
The resulting ordinary camera can use a physically enormous pupil. Its manifest
reports the actual f-number, pupil diameter, sample predictions and residual.
This is a scalar blur fit at finite samples, not full image or bokeh-shape equality.

Stopping down an ordinary camera can make the whole tabletop acceptably sharp.
These geometric optics renders do not simulate diffraction, shutter speed,
exposure or sensor noise penalties. The useful tilt-shift distinction is simultaneous
sharpness along a rotated surface **at a wide matched pupil**, with different
focus away from that surface.

## Coordinates, numerical domain and provenance

One Blender unit is one metre in a right-handed Z-up world. Blender camera −Z
points forward and +Y up; optical calculations reflect Z into the Cycles frame
with +Z scene-going. Tilt-shift rotation is `Rz(axis) Ry(swing) Rx(tilt)` in the
reference Y-down frame, followed by the documented Y reflection. Angles are
radians in data and degrees in the interface. Lens and image-circle UI units are
millimetres. The tilt-shift shift centre uses the active sensor dimension.

Manual focus obeys `b = f / (nz − f/D)`. An object at lens-relative optical
coordinates `Q` obeys `b = f Qz / (n·Q − f)`. Near-zero denominators are
singular; invalid tilt-shift geometry is rejected. The demo uses moderate 10°
movements and a 30 mm near clip plane ahead of the entire tilted aperture.
It does not change tilt-shift tolerances or disable guards. The original city's
off-axis crossing would require a negative manual axial focus at +10°;
the parity pair instead uses a valid axial target at approximately 220 m.
Reconstruction from the single-precision guide distance can slightly change the
displayed manual distance while preserving the rendered sensor conjugate.

Each JSON manifest records generator hash, Blender build identity, settings,
tilt-shift reference geometry, ordinary objective, target depths, predicted sensor
blur, selected device and rendered PNG hash. The circular-pupil diagnostic uses
two orthogonal physical pupil diameters and the inverse tilt-shift ray equation;
polygon and anamorphic shape are outside the active suite and that scalar metric.
Existing numerical and CPU/HIP acceptance tests remain the physics evidence;
an attractive demo alone is not an additional optical or hardware acceptance claim.

The active gallery combines two captured render sources. Its **eight retained
city and architectural-shift scenes** use the original
[render-generator snapshot](../work/demo-comparisons/4k/render-generator-source.py),
SHA-256 `2ff72280435e367585b83ddb0e0a88ba20b4ee8f87deff82d178d9f810900e20`.
Its **nine updated product scenes** use the
[printed-grid render-generator snapshot](../work/demo-comparisons/4k/grid-render-generator-source.py),
SHA-256 `af111b5e09ff5fadccbc9d9a853502c5babc87be7f8552dbc623b890a9caa35a`.
The latter changes the sheet's printed material while preserving the scene
geometry, optical calculations and render settings. Each render manifest identifies
its own captured source. Subsequent gallery, scope and surface-mask changes do
not alter those rendered artifacts or their manifests; gallery regeneration
preserves both sets of provenance.

## Current 4K artifact validation

The active gallery uses **17 images at 3840 × 2160, 256 samples, 16-bit RGB PNG**,
rendered on one Radeon RX 6900 XT HIP device. The
[current artifact audit](../work/demo-comparisons/4k/grid-artifact-audit.json)
passes all 17 active cases: nine product renders contain the new printed grid,
with camera settings and tilt-shift-reference geometry exactly unchanged. The eight
retained city/shift PNG, `.blend` and JSON files are byte-for-byte unchanged, as
are the five excluded historical case triplets. Both captured render-generator
sources are retained in the active `4k/` directory.

The [active scene reopen audit](../work/demo-comparisons/4k/active-scene-reopen-audit.json)
passes all 17 scenes, including the top-face-only printed grid on the nine product
sheets, portable CPU defaults, intended cameras, relative output paths, and no
hidden-render meshes.

The [surface-mask audit](../work/demo-comparisons/4k/focus-surface-audit.json)
passes all ten 960 × 540 masks and six pairs: source/mask hashes, independent
reconstruction from depth to plane distance, alpha-band thickness, shared pair
widths, and reprojection errors below `6e-7` normalized UV. Maximum independent
plane-distance errors are `2.2e-7 m` for product scenes and `5e-5 m` for the city.
Mask generation completed with exit 0 in 622 seconds, without rendering images.

The [gallery interaction audit](../work/demo-focus-ui-audit.json) passes all six
paired controls, independent pair toggles, keyboard operation, 10–100% opacity,
default-off overlays, and Space-key hiding. All 34 photograph/overlay image elements load across
11 sections, with no excluded-case links or horizontal overflow at 520 px width.
Visual inspection covered desktop table and city blur-fit overlays, the narrow
table layout, swing/axis previews, and 4K printed-grid crops. Cached `--gallery-only`
regeneration completed with exit 0 in 0.56 seconds, without rendering. These are
local browser and numerical checks; the geometric overlay limitations above still
apply.

## Historical 4K results and validation

Before the scope reduction and printed-grid update, the local 4K run completed
all **22 renders at 3840 × 2160, 256 samples, 16-bit RGB PNG**, rendered on one
Radeon RX 6900 XT HIP device. These historical audits include five cases now
excluded from the active gallery and do not validate replacement printed-grid
images or the new surface masks. The
[artifact audit](../work/demo-comparisons/4k/artifact-audit.json) records passing all 22
PNG and scene hashes, settings and captured-source provenance. The
[scene reopen audit](../work/demo-comparisons/4k/scene-reopen-audit.json) records
passing all 22 files: CPU defaults, relative output paths, intended active cameras,
valid enabled tilt-shift guides, and no external images, libraries or load-time code.

Historical visual inspection covered the main comparison families and tabletop
crops at 100%. Near and far tabletop lettering remained visible with tilt-shift
wide-pupil tilt; the matched-pupil ordinary camera lost sharpness away from its
selected depth. Stopping down the ordinary camera restored broad sharpness. City
tilt retained a distinct angled focus region, and both shift pairs visually matched
their ordinary counterparts.

The city's [ordinary blur fit](../work/demo-comparisons/4k/city-ordinary-blur-fit.json)
uses 273 visible surface hits and selects approximately **f/0.00395**, focus
**216.17 m**, and a **12.85 m physical pupil**. This deliberately permits an
extreme ideal ordinary lens to approach the tilt-shift blur objective; it still
differs in focus-plane behavior and is not presented as a practical real lens.

The final batch launcher unexpectedly returned 143 during the last image; its
cause is unestablished. The 21 completed cases were retained, and `circle-finite`
was regenerated from the same captured render source with a clean exit 0, recorded
in the [single-case process result](../work/demo-final-circle.process.json).
The successful artifact and reopen audits cover the resulting complete set;
the original batch is not claimed to have exited successfully.
