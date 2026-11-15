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
The authoritative complete dependency version list is Blender's
[`build_files/build_environment/cmake/versions.cmake` at the pinned commit](https://projects.blender.org/blender/blender/src/commit/02f0899d78e374b63e7181d9061e1f7ab03419cc/build_files/build_environment/cmake/versions.cmake).
The matching precompiled library origin and exact Git pin are recorded in
[source-revision.json](source-revision.json); individual versions are not duplicated here.

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
Pass `--blender /absolute/path` when needed. Background invocations disable audio
with `-noaudio` and isolate all user resources in `work/blender-user`, with explicit
extensions/scripts/datafiles overrides beneath it, configuration in
`work/blender-user-config` and caches in `work/cache`. These directories are created
before launch because Blender's environment-path overrides can require them to
exist. No personal configuration or extension directory is used.

Four jobs are deliberate: a sixteen-job initialization attempt hit its 22 GiB
systemd memory cap and was terminated; the incremental build was resumed at four
jobs. For an optional bounded build on this 32 GB host, run the existing command
inside a user scope (no system configuration change):

```sh
systemd-run --user --scope --unit=blender-tiltshift-build-lowmem -p MemoryHigh=16G -p MemoryMax=18G -p MemorySwapMax=0 -p CPUQuota=400% python3 scripts/dev.py build cpu --jobs 4
```

Use a different unit name if that scope is already active. A memory limit can
terminate the build; preserve sources and completed outputs, diagnose the log
and resume with suitable concurrency. This does not change the CLI's defaults.

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

Initialization runtime probes succeeded outside the tool sandbox in sequential
user scopes capped at 4 GB, zero swap and two CPU cores' quota, for example:

```sh
systemd-run --user --scope --unit=blender-tiltshift-validate -p MemoryMax=4G -p MemorySwapMax=0 -p CPUQuota=200% python3 scripts/dev.py validate
```

Use a distinct unit name for each active scope. A user scope bounds resources;
it does not itself remove an enclosing tool sandbox. On this host sandbox IPC
denial caused PulseAudio shutdown stalls even with `-noaudio`; authorized
execution outside that sandbox resolved process shutdown. Resource/configuration
isolation remains active in either case. No GUI or personal desktop was opened.
Final validation and all four scene save/reopen checks exited 0; native-feature
required validation exited 1 as expected. Four CPU scene renders and the actual
RX 6900 XT HIP targets render also exited 0. See the
[baseline evidence](baseline-validation.json) for exact settings, pins, hashes
and measured comparison errors. These are unmodified camera baseline checks.

## M2 native CPU patch

Keep the baseline executable/resources in `work/install-blender-baseline`.
Reconfigure the CPU tree for a distinct native prefix before building/installing:

```sh
/usr/bin/cmake -S work/blender -B work/build-blender-cpu \
  -DCMAKE_INSTALL_PREFIX="$PWD/work/install-blender-m2"
```

The current source checkout may contain the reviewed native patch while HEAD
stays pinned. Preserve unrelated dirty source; never reset or checkout over it.
Use the four-job/18 GiB build scope above and install only to the native prefix.
The normal `dev.py configure cpu` command resets the prefix to
`work/install-blender-cpu`; explicitly reapply the M2 prefix when reconfiguring.
Do not copy the baseline HIP fatbin into the native install: device data layout
changed, and enabled native GPU use is deliberately rejected until M4.

`python3 scripts/dev.py patch` exports the tracked source diff plus the explicitly
reviewed new `intern/cycles/kernel/camera/tilt_shift_math.h`, checks that its test
mirror matches, and rejects other untracked source. It does not stage or commit
upstream. See [native camera validation](m2-native-camera.md) for quantitative
fixtures, old-file migration/roundtrip commands and current limitations. Continue
using the immutable M1 generator on both binaries for disabled bitwise parity.

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

For the initialization baseline probe, the complete headless host executable was
built once with HIP runtime enabled. Only the gfx1030 kernel target was built in
the HIP tree, then installed into that same isolated host runtime:

```sh
install -D -m 644 work/build-blender-hip/intern/cycles/kernel/device/hip/kernel_gfx1030.fatbin.zst work/install-blender-cpu/5.3/scripts/addons_core/cycles/lib/kernel_gfx1030.fatbin.zst
sha256sum work/install-blender-cpu/5.3/scripts/addons_core/cycles/lib/kernel_gfx1030.fatbin.zst
python3 scripts/dev.py render --backend hip --scene measurable-targets --label baseline
```

The installed hash must equal the kernel artifact hash in the initialization
ledger. This uses the same executable/source/generator for CPU and HIP comparisons
without compiling a second complete host. It does not mean a full HIP-tree
Blender build was completed. The runtime path above is verified for pinned 5.3's
portable installation; never copy the kernel into a system Blender installation.

The render runner requires a real HIP device and disables CPU fallback. EXR,
RGBA float data and metadata are stored together under `work/renders`. It also
writes an 8-bit PNG through Blender's scene view transform for visual inspection;
that preview is display-only and never used for numerical comparison. Compare
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
`patches/blender-v5.3.0-tilt-shift-m3.patch`, excluding submodules. Empty diffs fail.
The earlier M2 patch is immutable evidence and is never overwritten. The exporter
includes the explicitly reviewed native mathematical header and verifies it against
the standalone mirror; any other untracked source fails. Nothing is staged or
committed upstream. See the [M3 interface guide](m3-native-interface.md) for the
separate GUI-capable install prefix and validation workflow.
