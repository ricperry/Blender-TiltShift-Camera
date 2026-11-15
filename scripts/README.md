# Development scripts

`prepare_blender.py` prepares the current cumulative M4 source patch for a full
build: it delegates official pinned source acquisition/verification to `dev.py`,
applies only to a clean exact pin, accepts the exact existing unstaged patch,
and refuses other source changes. Its default downloads source only;
`--with-dependencies` also downloads large pinned libraries and required LFS
assets. It does not build or install packages. Run
`python3 scripts/prepare_blender.py --help` and follow the
[fresh M4 GUI build](../docs/build-instructions.md#current-m4-fresh-gui-build).

`dev.py` is a Python standard-library CLI. Run `python3 scripts/dev.py --help`.
It checks tools, acquires/verifies official sources and libraries, configures
isolated headless CPU/HIP trees, builds with bounded parallelism, runs optics,
generates/validates Blender fixtures, renders, compares pixels and generates
nonempty native patches. See [build instructions](../docs/build-instructions.md).

`blender_reference.py` runs inside Blender 5.3 via the CLI. Current validation and
renders are explicitly upstream baseline smoke evidence. `--require-feature`
fails when the proposed native RNA property is absent. HIP render selection
fails without an actual HIP device and never enables CPU fallback.

`blender_m2_validation.py` is a separate quantitative native CPU runner. It
measures breathing/shift/fit centroids, off-axis focus-object sharpness, physical
CoC, tilted-plane sharpness, image-circle masks, volume initialization and clip
planes, plus explicit rejection and persistence/migration. EXR/raw linear pixels
and hashed JSON evidence go beneath ignored `work/`; use `--case` for bounded
checks. `run_m2_guards.py` validates the expected Blender exit one only against
a fresh complete, hash-matched rejection record and itself exits zero on success.
Positive fixture cases exit zero directly; `--case all` includes expected failing
renders and therefore has Blender's sticky error exit. See
[native reproduction](../docs/m2-native-camera.md).

`dev.py patch` exports the native changes without staging upstream, including
only the specifically reviewed new mathematical header; unknown untracked source
files and mismatched test/kernel header copies are rejected.

No system installation, history rewrite, push or desktop interaction is included.
Generated source/build/library/render/scene artifacts stay under ignored `work/`.
