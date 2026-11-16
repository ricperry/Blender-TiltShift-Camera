<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Photo and video gallery

The [local tilt-shift camera gallery](../work/demo-gallery/index.html) combines
**17 photographs in 11 pairs and eight videos**. It is generated under ignored
`work/` and has not been published. The README thumbnail is a portable published
city preview; the linked gallery becomes available locally after generation.

## Build from existing artifacts

Run from the repository root with ordinary Python 3, without Blender or encoding
dependencies:

```sh
python3 examples/build_demo_gallery.py
```

The defaults read photographs from `work/demo-comparisons/4k/`, videos from
`work/demo-animations/960x540/`, and write `work/demo-gallery/index.html`.
The builder does not render, label, encode, or modify media, saved scenes or
manifests. It verifies photo/scene hashes and video/manifest/poster hashes before
building. Missing ungenerated cases are omitted; changed recorded artifacts
cause an error. For initial generation, follow the [photo](DEMO_COMPARISONS.md)
and [video](DEMO_ANIMATIONS.md) instructions first.

For another existing input set, pass explicit directories:

```sh
python3 examples/build_demo_gallery.py \
  --photos work/demo-comparisons/preview \
  --videos work/demo-animations/960x540
```

This refreshes the same canonical gallery using the chosen inputs. `--output`
can select a separate inspection directory under `work/` if needed. Links are
relative to the selected gallery output. Both original gallery entrypoints now
delegate to this builder; their input directories' `index.html` files redirect
to the shared gallery rather than maintaining different photo/video layouts.

## Explore the controls

Choose **All**, **Photos**, or **Videos**, then narrow the subject with **Explore**.
Photo badges identify **Tilt-shift camera** and **Standard perspective camera**.
Each photo links to its original PNG and editable Blender scene; camera settings
and source manifests are under a disclosure. The delivered photos are 4K; an
alternate input set retains its own resolution.

Six supported pairs offer **Show focus planes**, off initially, with one opacity
slider for both photos. This marks the exact plane's intersection with visible
surfaces, not the entire depth of field. Overlays remain separate transparent
images; they never alter the photographs. Geometric methods, coordinate systems,
units, rotation order, tolerances and limitations remain in the
[photo guide](DEMO_COMPARISONS.md#optional-focus-plane-intersections).

The builder verifies cached guide metadata against a matching helper source
(`focus-overlay-source.py` beside the artifacts, or the current unchanged
`demo_focus_overlays.py`), each source scene/image/manifest, and every mask and
surface file. Capturing the original helper keeps optics provenance independent
of later presentation changes; a mismatched cache fails rather than silently
displaying an unverified overlay. No guide generation is needed to rebuild this
gallery from valid caches.

Videos start paused with browser playback controls and a first-frame poster.
Playing one pauses the others; hiding a clip through a filter also pauses it.
Each clip shows evaluated endpoints and links to the original MP4, animated scene,
frame values and encoding audit. Optical and rendering caveats are grouped in
**About these demonstrations** at the end.

## Validation

The [artifact audit](../work/demo-gallery/artifact-preservation-audit.json)
confirms all 933 recorded media, scene, mask and manifest files remained unchanged.
Both legacy gallery-only entrypoints rebuilt the canonical gallery successfully;
their indexes contain valid redirects and links.

The [browser audit](../work/demo-gallery/gallery-browser-audit-8.json) passes
all 19 demonstrations: combined media/theme filters, six default-off paired
focus controls with keyboard operation and 10–100% opacity, and playback,
five-second seeking and pausing for all eight videos. Only one video plays at a
time, and filtered-out videos pause. Visible camera labels use “Tilt-shift”.

The final [overlay visual audit](../work/demo-gallery/gallery-overlay-visual-audit.json)
passes all six pairs and responsive/filter checks. Image inspection confirmed
transparent overlay regions leave the photographs unobscured. Tested browser
widths were 1600, 700, 520 and 500 pixels; Firefox clamped a requested 360-pixel
viewport to 500. These are local gallery checks, not a new optical acceptance
claim or a full audit of the original rendering and encoding generators.
