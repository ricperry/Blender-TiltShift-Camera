<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Isolated build and validation

Run commands from the project root. Python scripts use only the standard library;
the scene runner uses Blender's bundled `bpy` and `mathutils`. No command installs
packages, replaces system Blender, opens a desktop window, pushes or rewrites
upstream history. Network acquisition and builds can consume substantial disk and
time; `work/` contains all downloaded/generated artifacts.

## Standalone optical reference

```sh
python3 scripts/dev.py check-deps
python3 scripts/dev.py test-optics
```

This uses `/usr/bin/cmake`, `/usr/bin/ctest`, Ninja and `work/build-optics-ninja`.
An older `work/build-optics` may use Unix Makefiles and is not reconfigured.
`CCACHE_DIR` is always inside `work/ccache`; the explicit CTest avoids a broken
unrelated user-local wrapper on the initialization host. Default parallelism is
four jobs. Passing these tests validates standalone geometry only.

## Official source and dependencies

```sh
python3 scripts/dev.py acquire
python3 scripts/dev.py verify-source
python3 scripts/dev.py dependencies
```

Acquisition creates a full official Git clone at the release tag with LFS smudge
disabled. An existing checkout is verified, never automatically reset or changed
to another revision. Verification checks HEAD, exact release tag, version header,
official origin and library gitlink; dirty source status is informational because
future native edits are expected. It separately reports required LFS assets and
library checkout presence. This is not a full optional regression-media audit.

Dependencies first fetch selected main-source LFS paths (`assets/*`,
`release/datafiles/*`, application templates and camera regression media), then
run Blender's `make_update.py --no-blender`. The updater alone does **not** fetch
main-source LFS assets. It acquires the pinned precompiled dependency checkout
without changing Blender's source HEAD. The script checks the library LFS store
with `git lfs fsck`; verify-source also checks its checkout commit. All optional
Blender regression media remain deferred. Some upstream build/test suites require
additional explicitly acquired media. Keep upstream/dependency license notices.

## Native headless CPU baseline

```sh
python3 scripts/dev.py configure cpu
python3 scripts/dev.py build cpu --jobs 4
python3 scripts/dev.py validate
python3 scripts/dev.py scenes
python3 scripts/dev.py render --scene measurable-targets --backend cpu --label baseline
```

Configuration uses `work/build-blender-cpu`, Release, precompiled libraries,
`WITH_HEADLESS=ON`, `WITH_CYCLES_NATIVE_ONLY=ON`, disabled CUDA/OptiX/oneAPI and
disabled HIP binaries. HIP runtime is enabled in both configurations, matching
the tested parent configuration; CPU rendering is explicitly selected by the
scene runner. The same host executable can later select HIP explicitly, but
runtime availability does not establish a HIP render. Installation stays in
`work/install-blender-cpu`; the Blender build normally places its runnable binary
at `work/install-blender-cpu/blender`, the script's default. The raw build artifact
is `work/build-blender-cpu/bin/blender` and may lack installed Python/libraries.
Pass `--blender /absolute/path` when needed. Background invocations isolate user
configuration in `work/blender-user-config` and caches in `work/cache`.

Headless configure succeeded on this host without installing system packages.
`configure cpu --gui` requests a window-system build and additional development
headers; UI and GNOME/Wayland acceptance remain separate work. Never run GUI
Blender on the user's active desktop without authorization.

Validation creates/reopens a generated `.blend` and checks existing camera RNA.
At M1 native tilt-shift fields are absent; baseline smoke is explicitly reported.
`validate --require-feature` must fail. The proposed future RNA identifier is
`tilt_shift_enabled`; adapt the probe once native integration finalizes its schema. Presence alone
will still not establish physical correctness. Render commands currently render
upstream optics; they are infrastructure for later acceptance scenes.

## HIP and comparisons

```sh
python3 scripts/dev.py configure hip
python3 scripts/dev.py build hip --jobs 4
python3 scripts/dev.py render --blender work/install-blender-hip/blender --backend hip --scene measurable-targets --label baseline
python3 scripts/dev.py compare work/renders/baseline/cpu/measurable-targets.json work/renders/baseline/hip/measurable-targets.json
```

The HIP configuration is isolated, builds gfx1030 only and verifies the generated
`cycles_kernel_hip` target. Fedora's HIP root must be `/usr` (header location),
with `/usr/bin/hipcc`, rather than `/usr/lib64/rocm`; the wrong root can silently
disable ahead-of-time kernel compilation. To exercise just that compiler step:

```sh
CCACHE_DIR="$PWD/work/ccache" /usr/bin/cmake --build work/build-blender-hip --target cycles_kernel_hip --parallel 1
```

The render runner requires a real HIP device and disables CPU fallback. EXR,
RGBA float data and metadata are stored together under `work/renders`. Compare
checks scene/dimensions/seed/samples, generator hash, camera settings, enabled
state and Blender version/build hash, then RGB RMSE and maximum absolute difference;
alpha is excluded. Pixel SHA-256 must match metadata, so interrupted or altered
artifact sets cannot silently compare as valid. Defaults
are provisional, documented in [hip-support.md](hip-support.md). Use explicit
`--rmse`/`--max-abs` for reviewed thresholds; use both zero for exact comparisons.
Optics, physical CPU images and HIP parity remain separate evidence gates.

## Reviewable native patches

```sh
python3 scripts/dev.py patch
```

This writes a binary-capable diff against the pinned commit to
`patches/blender-v5.3.0-tilt-shift.patch`, excluding submodules. Empty diffs fail.
Untracked upstream files fail rather than being silently omitted; review and
stage intended new upstream files before generation (staging does not commit).
No patch exists at M1, and no upstream commit/history change is required.
