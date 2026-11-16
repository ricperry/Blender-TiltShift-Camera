<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Isolated build and validation

Run commands from the project root. Python scripts use only the standard library;
the scene runner uses Blender's bundled `bpy` and `mathutils`. Project scripts do
not automatically install packages, replace system Blender, open windows, push or
rewrite upstream history. Explicit package and GUI commands are shown separately.
Network acquisition and builds can consume substantial disk and
time; `work/` contains all downloaded/generated artifacts.

## Current M4 fresh GUI build

Use this workflow for the current camera. The sections below retain earlier
milestone and baseline reproduction commands; they are historical workflows.
Start in a clone of this project on Linux x86-64. Use fresh
`work/build-blender-m4` and `work/install-blender-m4` directories so existing
baseline/M2/M3 installations remain intact. This is a full Blender source build;
allow substantial network traffic, disk space and build time.

Install build tools and GUI development headers if missing. On Fedora, the
[official Blender Linux build guide](https://developer.blender.org/docs/handbook/building_blender/linux/)
lists the distribution prerequisites. A starting package set for this workflow is:

```sh
sudo dnf install python3 git git-lfs gcc gcc-c++ cmake ninja-build ccache pkgconf-pkg-config \
  make mesa-libGL-devel mesa-libEGL-devel libstdc++-static \
  libX11-devel libXxf86vm-devel libXi-devel libXcursor-devel libXrandr-devel \
  libXinerama-devel libXfixes-devel libXrender-devel \
  wayland-devel wayland-protocols-devel libxkbcommon-devel dbus-devel kernel-headers
```

These are commands for the builder to run; project scripts do not install system
packages. Fedora package availability varies by release. The precompiled library
checkout supplies many other dependencies, including Wayland components when
supported by the upstream configuration. Check CMake's summary for
`WITH_HEADLESS=OFF`, `WITH_GHOST_WAYLAND=ON` and `WITH_GHOST_X11=ON`; investigate
missing-header warnings rather than assuming a successful configure enables
Wayland. Compiling a GUI does not establish GNOME/Mutter workflow acceptance.

Acquire the exact official `v5.3.0` source pin and apply **only** the cumulative
[M4 patch](../patches/blender-v5.3.0-tilt-shift-m4.patch):

```sh
python3 scripts/dev.py check-deps
python3 scripts/prepare_blender.py --with-dependencies
python3 scripts/dev.py test-optics
```

`prepare_blender.py` delegates acquisition, pin/origin/version verification and
optional dependency acquisition to `dev.py`. Its default omits dependencies but
still downloads the full source clone. `--with-dependencies` adds the large
pinned Linux library checkout and required source LFS assets. Existing source is
accepted only when clean at the pin or exactly equal to the unstaged M4 patch;
staged edits, partial patches and unrelated source changes fail without resetting
or overwriting them. It never stacks historical patches or changes upstream HEAD.
The library pin and source provenance are in [source-revision.json](source-revision.json).

Configure a fresh GUI host with HIP runtime available but no ahead-of-time HIP
kernel yet. CPU rendering does not require an AMD GPU:

```sh
export CCACHE_DIR="$PWD/work/ccache"
/usr/bin/cmake -S work/blender -B work/build-blender-m4 -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DWITH_LIBS_PRECOMPILED=ON \
  -DWITH_CYCLES_NATIVE_ONLY=ON -DWITH_COMPILER_CCACHE=ON \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
  -DWITH_HEADLESS=OFF -DWITH_GHOST_WAYLAND=ON -DWITH_GHOST_X11=ON \
  -DWITH_CYCLES_DEVICE_CUDA=OFF -DWITH_CYCLES_DEVICE_OPTIX=OFF \
  -DWITH_CYCLES_DEVICE_ONEAPI=OFF -DWITH_CYCLES_DEVICE_HIPRT=OFF \
  -DWITH_CYCLES_DEVICE_HIP=ON -DWITH_CYCLES_HIP_BINARIES=OFF \
  -DCMAKE_INSTALL_PREFIX="$PWD/work/install-blender-m4"
systemd-run --user --scope --unit=blender-tiltshift-m4-host \
  -p MemoryHigh=16G -p MemoryMax=18G -p MemorySwapMax=0 -p CPUQuota=400% \
  /usr/bin/cmake --build work/build-blender-m4 --target install --parallel 4
```

The user scope requires a functioning systemd user session. Use a distinct unit
name if one is already active. The 18 GiB cap and four jobs protect headroom on
the tested 32 GB host; a cap can still stop a build. Preserve completed outputs,
diagnose failures and resume at suitable concurrency. No system install target
is used: CMake's install prefix stays inside this project's ignored `work/`.
Avoid `dev.py configure cpu` here; that older helper selects different build and
install directories and headless defaults.

Before running this build, isolate its configuration, scripts and caches:

```sh
export BLENDER_USER_RESOURCES="$PWD/work/blender-user"
export BLENDER_USER_CONFIG="$PWD/work/blender-user-config"
export BLENDER_USER_EXTENSIONS="$PWD/work/blender-user/extensions"
export BLENDER_USER_SCRIPTS="$PWD/work/blender-user/scripts"
export BLENDER_USER_DATAFILES="$PWD/work/blender-user/datafiles"
export XDG_CACHE_HOME="$PWD/work/cache"
mkdir -p "$BLENDER_USER_RESOURCES" "$BLENDER_USER_CONFIG" "$BLENDER_USER_EXTENSIONS" \
  "$BLENDER_USER_SCRIPTS" "$BLENDER_USER_DATAFILES" "$XDG_CACHE_HOME"
python3 scripts/dev.py validate --blender work/install-blender-m4/blender --require-feature
work/install-blender-m4/blender --background -noaudio --factory-startup \
  --threads 2 --python-exit-code 1 --python scripts/blender_m4_validation.py -- \
  --output work/m4-validation/cpu --backend cpu --case all
python3 scripts/run_m4_guards.py --blender work/install-blender-m4/blender \
  --output work/m4-validation --backend cpu
```

The positive `all` fixture should exit zero. The guard runner creates its own
fresh result directory and checks complete rejection records together with
Blender's expected sticky render-error exit one; the host guard runner itself
exits zero on success.
See [M4 reproduction](m4-hip-camera.md#reproduction) for all cases and comparison
requirements. For the editable example, launch the isolated GUI deliberately:

```sh
work/install-blender-m4/blender --factory-startup examples/full-scale-city/full-scale-city.blend
```

The file defaults to Cycles CPU. Select a perspective camera, open Camera Data
and enable **Tilt-Shift**. In the example, the tilt-shift camera is already
active. Changing to HIP is optional and requires the next build step.

### Optional RDNA2 HIP kernel and host installation

The validated configuration is RX 6900 XT / `gfx1030`, HIP 7.2.53211, one device
and HIPRT disabled. On Fedora, check `/usr/bin/hipcc` and `/usr/include/hip`;
the build host used the `hipcc` and `rocm-hip-devel` packages. Install a compatible
ROCm toolchain if absent, and inspect GPU load and available RAM/VRAM before GPU
work. The instructions below do not establish support on another architecture.

Reconfigure the same fresh M4 tree, compile the HIP kernel with **one job**, then
install the host and matching kernel together with four jobs under the cap:

```sh
/usr/bin/cmake -S work/blender -B work/build-blender-m4 \
  -DWITH_CYCLES_DEVICE_HIP=ON -DWITH_CYCLES_DEVICE_HIPRT=OFF \
  -DWITH_CYCLES_HIP_BINARIES=ON -DCYCLES_HIP_BINARIES_ARCH=gfx1030 \
  -DHIP_ROOT_DIR=/usr -DHIP_HIPCC_EXECUTABLE=/usr/bin/hipcc \
  -DCMAKE_INSTALL_PREFIX="$PWD/work/install-blender-m4"
ninja -C work/build-blender-m4 -t targets all | rg '^cycles_kernel_hip:'
systemd-run --user --scope --unit=blender-tiltshift-m4-kernel \
  -p MemoryHigh=16G -p MemoryMax=18G -p MemorySwapMax=0 -p CPUQuota=400% \
  /usr/bin/cmake --build work/build-blender-m4 --target cycles_kernel_hip --parallel 1
systemd-run --user --scope --unit=blender-tiltshift-m4-hip-install \
  -p MemoryHigh=16G -p MemoryMax=18G -p MemorySwapMax=0 -p CPUQuota=400% \
  /usr/bin/cmake --build work/build-blender-m4 --target install --parallel 4
```

The target check must print `cycles_kernel_hip`; a silent missing target is not a
HIP build. The `/usr` HIP root is deliberate on this Fedora toolchain. Use the
official install target rather than copying an older fatbin: installed kernel,
headers and host must match. Execute the [M4 CPU and HIP reproduction suite](m4-hip-camera.md#reproduction)
with the same installed executable, one device, hard backend selection and
retained kernel/device logs before claiming HIP support. Its full 19-pair
comparison is stronger than simply opening the example or detecting a GPU.

## Historical workflows

The following sections preserve baseline/M2/M3 commands and the original M4
build-tree provenance. For a new current build, use the fresh workflow above.

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
upstream. See [tilt-shift camera validation](m2-native-camera.md) for quantitative
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

This now writes a binary-capable cumulative diff against the pinned commit to
`patches/blender-v5.3.0-tilt-shift-m4.patch`, excluding submodules. Empty diffs fail.
The earlier M2/M3 patches are immutable evidence and are never overwritten. The exporter
includes the explicitly reviewed native mathematical header and verifies it against
the standalone mirror; any other untracked source fails. Nothing is staged or
committed upstream. See the [M3 interface guide](m3-native-interface.md) for the
separate GUI-capable install prefix and validation workflow.

## M4 single-device native HIP

The current cumulative exporter defaults to `--milestone m4`; existing M2/M3
patches are immutable. Preserve all earlier installations and use a distinct
`work/install-blender-m4` prefix. Reconfigure the existing GUI-capable CPU build
tree with HIP binaries ON for gfx1030 and HIPRT OFF, compile `cycles_kernel_hip`
with one job, then build/install the host with four jobs under the 18 GiB build
cap. Use the official install target so the new fatbin and current source
headers are installed together. The ordinary `dev.py configure cpu` command
resets the prefix and disables HIP binaries; follow the explicit
[M4 build/reproduction commands](m4-hip-camera.md) instead.

The same M4 executable selects hard CPU or single HIP execution, with CPU fallback
and HIPRT disabled. The final comparison requires all 19 declared float buffers,
matching actual camera/raster settings and one global executable/script/patch/
fatbin provenance tuple. The [M4 ledger](m4-validation.json) includes retained
physics/rejections, ordinary-camera attribution, actual device/kernel log proof,
resource caps, completed-render mode timings and the interruption/rerun record.
