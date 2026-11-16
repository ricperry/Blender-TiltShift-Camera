<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Photo and video gallery

The [tilt-shift camera gallery](https://ricperry.github.io/Blender-TiltShift-Camera/) combines
**17 photographs in 11 pairs and eight videos**, with original 4K images,
editable Blender scenes and six optional focus-plane overlays. Its portable
static export is served separately from the source repository through GitHub Pages.
Local generation remains under ignored `work/`.

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

## Export for GitHub Pages

From the complete verified artifact set, export a fresh portable directory:

```sh
python3 examples/export_demo_gallery.py
python3 -m http.server 8765 --directory work/demo-gallery-public
```

Preview `http://localhost:8765/`. The exporter accepts `--photos`, `--videos` and
`--output`; all directories must remain below `work/`. Output must be new and
must not overlap either input or the canonical local gallery. Preserve or move
an earlier export before rebuilding. Missing active photos, videos or any of the
six verified focus-plane pairs fail the export instead of publishing an incomplete
gallery. The exporter does not change the canonical gallery or input redirects.

Only explicit active dependencies are copied: 17 original PNGs, 25 Blender scenes,
eight MP4s and first-frame posters, render/animation/encoding JSON, ten overlay
masks and their surface/provenance records, and matching captured generator
sources. The export also includes `LICENSE`, `.nojekyll` and
`publication-manifest.json`, which records every other file's size and SHA-256,
source paths and gallery counts. All copied bytes are verified. No rendering,
re-encoding or image editing occurs; raw animation sequences, unrelated examples,
caches and browser profiles are excluded. Render-time paths and frame hashes in
the original JSON remain provenance records, rather than downloadable site URLs.

The HTML's media URLs are relative to the export and its method links point to
the source repository on GitHub. Publish only the export directory's contents to
the separate `gh-pages` branch, and configure GitHub Pages to serve that branch's
root. This is a separate publication action: running the exporter does not push
or deploy. Keep generated media out of the source branch. Source-only commits
cannot publish ignored `work/` files. The public entrypoint is
[the GitHub Pages gallery](https://ricperry.github.io/Blender-TiltShift-Camera/).

Run the bounded packaging tests with
`python3 -m unittest discover -s tests -p 'test_gallery_export.py'`.

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
