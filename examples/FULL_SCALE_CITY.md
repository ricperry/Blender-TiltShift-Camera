<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Full-scale Meridian

A low-detail city district for comparing native lens tilt with ordinary
perspective depth of field at real city distances. The geometry and animated
travel from [Little Meridian](CITY.md) are enlarged **50× in world space**:
the core district is 82 × 67 m, cars about 3.3 m long, standing people about 2 m
tall, and buildings about 5–22 m. Units remain 1 Blender unit = 1 metre.
Continuous terrain, extended roads and canal, and surrounding simple blocks
replace the miniature's display plinth, nameplate and studio tabletop.

Generate with the project's patched Blender; generation saves without rendering:

```sh
work/install-blender-m4/blender --background -noaudio --factory-startup --threads 2 \
  --python-exit-code 1 --python examples/create_full_scale_city.py -- \
  --output work/examples/full-scale-city/full-scale-city.blend
```

Open `work/examples/full-scale-city/full-scale-city.blend` with the same binary
and press **F12**. The active camera is **03 NATIVE TILT**. Instructions are also
in the file's **START HERE · Full-scale Meridian** Text datablock. The `.json`
inventory records world-space representative dimensions and matched camera
positions/settings. The reused generator saves an intermediate
`source-miniature.blend` and inventory in this same ignored output directory;
it does not alter the original miniature scene or generator.

| Camera | Native movement | Depth of Field enabled |
| --- | --- | --- |
| 01 ORDINARY | Disabled | On |
| 02 NATIVE ZERO | Enabled, zero angles | On |
| 03 NATIVE TILT | Enabled, +5° tilt | On |

All three have identical position and orientation, scale 1, a 50 mm lens,
36 mm horizontal sensor, f/2.8, seven aperture blades and the same native
off-axis focus object at `(0.75, -6, 1.75)` m. The camera position is
`(102.5, -132, 150)` m. Choose the camera in Scene Properties > Camera, or select
it in the Outliner and press **Ctrl Numpad 0**. The ordinary camera's DOF remains
enabled, so the comparison isolates native movement rather than switching blur
on and off. At this scale ordinary 50 mm DOF is broad; tilt changes the plane of
focus at the same aperture. Physical breathing is accepted, so the frames need
not align pixel for pixel. Use `--tilt-degrees` to generate another angle, or
adjust it in Camera Data properties in small steps, initially about 0.25°.

The world is right-handed, Z-up, with streets along X/Y. Camera −Z points
forward and +Y up. Native angles store radians and display degrees; active
lens-frame order is `Rz(axis) Ry(swing) Rx(tilt)`, as specified in the
[optical model](../docs/optical-model.md). Image-circle diameter zero means
unbounded. Extreme movements can reach singular focus geometry and be rejected;
no optical tolerances are changed. Paint and overlaid-surface offsets inherited
from the miniature become 15–50 mm after enlargement.

The saved scene uses Cycles CPU, two threads, 1600 × 1000, 128 samples and seed
71; motion blur and the compositor are disabled. All depth blur comes from
finite-aperture camera rays. Frame 40 is selected; **Space** plays the inherited
deterministic 1–240 animation at 24 fps. Traffic holds at frames 85–200 and
pedestrians cross at 105–184, with a positional wrap between 240 and 1. There
are no linked assets or load-time scripts. Opening this example does not establish
HIP support or replace the separate numerical and deterministic-render physics
acceptance tests.

The generated file was reopened and checked: 2,314 objects, three matched
cameras, a measured 3.30 m car body, a 1.91 m standing person, and a 19.5 m hotel
body. Camera transforms, lens, aperture and shared focus target match; traffic
holds, pedestrian movement and signal phases pass the inherited animation checks.

All three cameras were rendered on the Radeon RX 6900 XT using single-device
HIP, frame 40, **2400 × 1500**, 256 samples and seed 71, with denoising,
adaptive sampling and compositing disabled. The previews are
[ordinary DOF](../work/examples/full-scale-city/ordinary-dof.png),
[native zero tilt](../work/examples/full-scale-city/native-zero.png), and
[native 5° tilt](../work/examples/full-scale-city/native-tilt.png).
Each has a matching JSON record in the output directory; `inspection.json`
records the saved-scene and animation checks. Visual inspection shows broad
sharpness in the ordinary and zero-tilt views, and a narrower central band of
focus in the tilted view. The saved scene retains its portable CPU default.
