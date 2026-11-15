<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Initialization evidence

Snapshot: 2026-11-14. This ledger distinguishes implemented geometry from future
native camera and hardware acceptance. See [source-revision.json](source-revision.json)
for exact provenance. Long-running native build outcomes must be appended only
after execution finishes; successful configuration is not a working executable.

| Item | Evidence / result |
|---|---|
| Public repository | `https://github.com/ricperry/Blender-TiltShift-Camera`; initial commit `eb2303109632d6f11bc4ad6a0110c86883728fa4` |
| Source | Official v5.3.0 tag/commit/version header verified; detached checkout retains upstream history; source clean before native development |
| Required source LFS | 340 selected Linux/runtime/camera files materialized; optional regression media deferred |
| Linux libraries | Pinned gitlink checked out; 716 LFS objects acquired; library `git lfs fsck` passed; clean dependency checkout |
| Standalone optics | Fresh Ninja Debug build, 1/1 CTest passing; executable reports 14,120 checks over 1,620 deterministic rays |
| Native CPU configure | Successful headless Release configure; no system package installations required |
| Native CPU build/render | Build started at initialization; completed result and rendered evidence pending |
| Native feature | No DNA/RNA/UI/Cycles patch; no modified camera binary; native physics and disabled-path regression pending |
| HIP | gfx1030 configuration found HIP 7.2.53211 and kernel target; kernel compile started, render acceptance pending; no support claim |
| Scene infrastructure | Four deterministic scene generators and render/pixel comparison commands provided; actual generated scenes/renders require a runnable Blender |
| GUI | No active desktop interaction; native UI, viewport/overlay and Wayland acceptance pending |

Recorded successful native CPU configuration:

```sh
CCACHE_DIR="$PWD/work/ccache" /usr/bin/cmake -S work/blender -B work/build-blender-cpu -G Ninja -DCMAKE_BUILD_TYPE=Release -DWITH_HEADLESS=ON -DWITH_CYCLES_NATIVE_ONLY=ON -DWITH_CYCLES_DEVICE_CUDA=OFF -DWITH_CYCLES_DEVICE_OPTIX=OFF -DWITH_CYCLES_DEVICE_ONEAPI=OFF -DWITH_CYCLES_DEVICE_HIP=ON -DWITH_CYCLES_HIP_BINARIES=OFF -DWITH_CYCLES_DEVICE_HIPRT=OFF -DWITH_COMPILER_CCACHE=ON -DCMAKE_INSTALL_PREFIX="$PWD/work/install-blender-cpu" -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
```

Native build log: `work/build-blender-cpu.log` (ignored local evidence).
The parent later bounded its running build with a user systemd scope using
`MemoryHigh=18G`, `MemoryMax=22G`, `MemorySwapMax=0`, `CPUQuota=1000%` and ten jobs.
The reusable CLI remains conservative at four jobs and does not change cgroup policy.
The CPU CLI matches the recorded HIP-runtime-enabled configuration without
requesting GPU binaries. CPU render selection remains explicit. No HIP render
follows from configuration alone.

Accepted user decision: enabled mode includes physical focus breathing; zero
tilt may differ from ordinary Cycles at finite focus. Disabled mode must preserve
the exact existing branch. Native optical units follow 1 BU = 1 metre.
