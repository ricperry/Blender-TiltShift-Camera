# Development scripts

`dev.py` is a Python standard-library CLI. Run `python3 scripts/dev.py --help`.
It checks tools, acquires/verifies official sources and libraries, configures
isolated headless CPU/HIP trees, builds with bounded parallelism, runs optics,
generates/validates Blender fixtures, renders, compares pixels and generates
nonempty native patches. See [build instructions](../docs/build-instructions.md).

`blender_reference.py` runs inside Blender 5.3 via the CLI. Current validation and
renders are explicitly upstream baseline smoke evidence. `--require-feature`
fails when the proposed native RNA property is absent. HIP render selection
fails without an actual HIP device and never enables CPU fallback.

No system installation, history rewrite, push or desktop interaction is included.
Generated source/build/library/render/scene artifacts stay under ignored `work/`.
