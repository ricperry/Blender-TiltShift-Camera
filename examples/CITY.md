<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Little Meridian

A self-contained miniature city for experimenting with the native Blender 5.3 /
Cycles camera: pastel apartments and shops, roof gardens, water towers, a clock
square, striped market stalls, a park, a canal, bridges, traffic, cyclists and
walking citizens. All geometry, materials and animation are generated locally;
there are no downloaded assets, add-ons, linked libraries or load-time scripts.

Generate with the project's patched binary:

```sh
work/install-blender-m4/blender --background -noaudio --factory-startup --threads 2 \
  --python-exit-code 1 --python examples/create_city.py -- \
  --output work/examples/harbor-city/harbor-city.blend
```

Generation only saves the `.blend` and its `.json` inventory; it does not render.
Open the saved file with that binary and press **F12**. The selected camera's
native controls appear in Camera Data properties. The Text datablock
**START HERE · Little Meridian** contains instructions inside the file.

From the project directory, open it with:

```sh
work/install-blender-m4/blender work/examples/harbor-city/harbor-city.blend
```

Press **Space** over the viewport to play the timeline. For an immediately visible
traffic view, choose camera **06 STREETLIFE**. Camera **01 HERO** and **02 COMPARE**
provide the same-view tilt comparison. Set Depth of Field's Focus Object to a
named vehicle root to experiment with tracking focus.

The saved file uses CPU rendering for portability, 1600 × 1000, 128 samples and
seed 71. To render on the tested single AMD HIP device, select the device in
Preferences > System and GPU Compute in Render Properties. Keep motion blur,
Vector passes, HIP RT and multiple enabled HIP devices off: those are outside
the native M4 camera's supported scope. Opening this scene is not HIP acceptance.

| Camera | Experiment |
| --- | --- |
| 01 HERO | Native +1.7° tilt, 50 mm, f/1.4, central crossing focus |
| 02 COMPARE | Same pose, lens, aperture and focus; native angles zero |
| 03 SWING | Same pose and optics; native −1.6° swing |
| 04 OVERVIEW | Ordinary upstream camera, native feature disabled, f/8 |
| 05 ARCHITECTURE | Level body, 60 mm, f/5.6, +4 mm vertical shift |
| 06 STREETLIFE | Low view along the avenue, 35 mm, f/2.8, separate crossing focus |

Choose a camera in Scene Properties > Camera, or select one in the Outliner and
press **Ctrl Numpad 0**. HERO and COMPARE isolate the lens movement; physical
breathing can change framing slightly. OVERVIEW intentionally has a different
aperture so the whole city is easy to inspect. All depth blur is computed by
Cycles camera rays; no compositor or image-space blur is present.
Native Display guides require Viewport Overlays > Extras, enabled in the saved file.

The file opens on frame 40. The 1–240 range runs at 24 fps. Vehicles and pedestrians
use deterministic keyframes, rather than a traffic or rigid-body simulation.
East–west traffic holds from frame 85 through 200. Signals are green at frames
1–84 and 201–240, amber at 85–92, and red at 93–200; crossing pedestrians move
only during that red hold. STREETLIFE at frame 145 shows the crossing in progress.
Playback wraps between frames 240 and 1, with visible positional resets at the
boundary. Motion blur remains disabled.

The city is a physical miniature: **1 Blender unit = 1 metre**, with a 1.64 × 1.34 m
display plinth and 0.10–0.39 m buildings. Z points up; streets follow world X/Y.
Camera −Z points forward and +Y up. Native lens angles store radians, displayed
as degrees; their active lens-frame order is `Rz(axis) Ry(swing) Rx(tilt)` as
defined in [the optical model](../docs/optical-model.md). The focus empty is an
actual native off-axis focus object. Move it or adjust lens angles in small
increments, about 0.25° to start. Image-circle diameter zero is unbounded.
Extreme movements can produce singular or invalid optical geometry and are
rejected by the native camera. Surface offsets of 0.3–1 mm separate paint and
overlaid surfaces; no numerical physics tolerances are changed.

Numbered collections organize the scene. Repeated geometry shares small primitive
meshes, and objects carry readable names. This is an artistic camera playground;
the separate numerical and render fixtures remain the physics acceptance tests.

The [ten-second traffic preview](../work/examples/harbor-city/traffic-preview.mp4)
contains 120 actual HIP-rendered frames at 800 × 500, 32 samples and 12 fps,
sampling every other frame of the 24 fps scene. It uses no denoising or compositor
blur. The saved scene remains at frame 40 with its original CPU rendering default.

The generated scene was reopened and inspected with 1,560 objects, six cameras,
18 animated objects and eight three-color traffic signals. All six cameras
rendered on a single AMD Radeon RX 6900 XT through HIP. The 1600 × 1000,
128-sample previews in `work/examples/harbor-city/` are `hero.png`, `zero-tilt.png`,
`overview.png`, `architecture.png` and `streetlife.png`; the street view uses frame
145 and the other previews use frame 40. Each has a matching JSON render record.
Animation checks confirmed stationary vehicles during the red hold, crossing
pedestrian movement, and the green, amber and red signal phases. These checks
exercise this example; they do not extend the native camera's physics acceptance.
