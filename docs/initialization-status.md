<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Initialization evidence

Update 2026-11-14: the bounded static native CPU M2 foundation, bounded M3
native interface and single-device non-HIPRT M4 HIP gate are complete.
See [M4 evidence](m4-validation.json), [HIP scope](m4-hip-camera.md), [M2 evidence](m2-validation.json),
[native conventions](m2-native-camera.md), [M3 evidence](m3-validation.json) and
[interface workflow/limits](m3-native-interface.md). M3 GUI evidence uses an
isolated Sway/software OpenGL session; M4 adds actual RX 6900 XT/gfx1030 build/render evidence.
The snapshot below remains the historical unmodified M1 initialization record.

Snapshot: 2026-11-14. This ledger distinguishes implemented geometry from future
tilt-shift camera and hardware acceptance. See [source-revision.json](source-revision.json)
for exact provenance and [baseline-validation.json](baseline-validation.json) for
machine-readable metrics and artifact hashes. M1 foundation/build/runtime evidence
is complete; the completed initialization commit/push is tracked separately.
Initial `df` evidence showed approximately 333 GB available before acquisition;
a later snapshot showed approximately 330 GB available. Source/library acquisition
remained within available disk capacity. These are filesystem free-space snapshots,
not sizes attributable exclusively to this checkout.
Final audit showed approximately 329 GB disk available and 23 GiB memory
available, with zero running `blender-tiltshift-*` user units. The upstream checkout
remained clean at the exact pin. Installed host executable SHA-256:
`a7e29865c5203192da0f371939c1a3be37457238ad840958b36f165924f8557b`.

| Item | Evidence / result |
|---|---|
| Public repository | `https://github.com/ricperry/Blender-TiltShift-Camera`; initial commit `eb2303109632d6f11bc4ad6a0110c86883728fa4` |
| Source | Official v5.3.0 tag/commit/version header verified; detached checkout retains upstream history; source clean before native development |
| Required source LFS | 340 selected Linux/runtime/camera files materialized; optional regression media deferred |
| Linux libraries | Pinned gitlink checked out; 716 LFS objects acquired; library `git lfs fsck` passed; clean dependency checkout |
| Standalone optics | Fresh Ninja Debug build, 1/1 CTest passing; executable reports 14,120 checks over 1,620 deterministic rays |
| Native CPU configure | Successful headless Release configure; no system package installations required |
| Native CPU build/render | Headless Release build/install succeeded; installed executable reports 5.3.0 / `02f0899d78e3`; all four CPU baseline renders exited 0 |
| Native feature | No DNA/RNA/UI/Cycles patch; no modified camera binary; native physics and disabled-path regression pending |
| HIP | gfx1030 kernel compilation and actual RX 6900 XT baseline render exited 0; CPU/HIP targets comparison passed; new-camera HIP acceptance remains pending |
| Scene infrastructure | Validation and all four generated `.blend` save/reopen checks exited 0; all CPU previews and HIP targets visually inspected; absent native RNA fails `--require-feature` with expected exit 1 |
| GUI | No active desktop interaction; native UI, viewport/overlay and Wayland acceptance pending |

Recorded successful native CPU configuration:

```sh
CCACHE_DIR="$PWD/work/ccache" /usr/bin/cmake -S work/blender -B work/build-blender-cpu -G Ninja -DCMAKE_BUILD_TYPE=Release -DWITH_HEADLESS=ON -DWITH_CYCLES_NATIVE_ONLY=ON -DWITH_CYCLES_DEVICE_CUDA=OFF -DWITH_CYCLES_DEVICE_OPTIX=OFF -DWITH_CYCLES_DEVICE_ONEAPI=OFF -DWITH_CYCLES_DEVICE_HIP=ON -DWITH_CYCLES_HIP_BINARIES=OFF -DWITH_CYCLES_DEVICE_HIPRT=OFF -DWITH_COMPILER_CCACHE=ON -DCMAKE_INSTALL_PREFIX="$PWD/work/install-blender-cpu" -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
```

Native build log: `work/build-blender-cpu.log` (ignored local evidence).
An attempted sixteen-job build ran in a user systemd scope with
`MemoryHigh=18G`, `MemoryMax=22G`, `MemorySwapMax=0` and `CPUQuota=1600%`.
The soft limit was subsequently raised to 21 GiB; the 22 GiB hard cap remained.
It reached the 22 GiB cap and was terminated by the kernel; the journal records
`Result=oom-kill` at 19:10:17 on November 14 after approximately 5 minutes 20
seconds. This was bounded build-memory exhaustion, not a diagnosed source error.
Source and completed object files remained intact. The parent resumed the
incremental build with four jobs in `blender-tiltshift-build-lowmem`, using
`MemoryHigh=16G`, `MemoryMax=18G`, `MemorySwapMax=0`, `CPUQuota=400%`.
That recovery build completed successfully and installed
`work/install-blender-cpu/blender`; no lasting build blocker remains.
The build finished at approximately 19:26. The user's GNOME notification was
checked against the journal: the earlier event was `CONSTRAINT_MEMCG` in
`blender-tiltshift-build-final.scope`, killing three owned `cc1plus` processes
(PIDs 1130684, 1130705 and 1130688). Checked logs since 19:00 showed no
`systemd-oomd` event or other application kill. This is bounded evidence from
that checked interval, not a claim that high concurrency cannot affect desktop
memory pressure. Later runtime probes used sequential 4 GB / zero-swap scopes
with `CPUQuota=200%`; no additional full builds were started.
The reusable CLI's four-job default remains appropriate and does not change
cgroup policy. The successful, separate HIP kernel compilation remains valid.
The CPU CLI matches the recorded HIP-runtime-enabled configuration without
requesting GPU binaries. CPU render selection remains explicit. No HIP render
follows from configuration alone.

Actual `rocminfo` / `rocm-smi` probes identify RX 6900 XT / gfx1030 with
17,163,091,968 bytes (approximately 16 GiB) VRAM, about 2.25 GB used before tests.
The completed gfx1030 kernel artifact is
`work/build-blender-hip/intern/cycles/kernel/device/hip/kernel_gfx1030.fatbin.zst`,
SHA-256 `a72e060586af190f103b3819cc05a99853a3a6a83ef686408a0f09b837ebdd40`.
The parent installed that exact artifact into the same completed host runtime at
`work/install-blender-cpu/5.3/scripts/addons_core/cycles/lib/kernel_gfx1030.fatbin.zst`
and verified the matching SHA-256. The baseline executable has HIP runtime enabled;
the HIP tree supplied only this compiled kernel, not a second complete host build.
Compilation alone establishes neither GPU rendering nor tilt-shift camera support.
Subsequent actual HIP rendering is recorded below and establishes baseline
operation only.

The unmodified Blender build emitted GCC 16 warnings including array-bounds in
`bmesh_decimate_unsubdivide.cc` / a `std::ranges` sort and nonnull `this` in
`compositor/node_tree_evaluator.cc:115`. They were not build errors and were not
diagnosed or changed here. The standalone optical reference built warning-free.

Initial baseline validation/scene-generation sessions saved and reopened their
expected fixtures but hung during PulseAudio shutdown (`pa_write(): Operation
not permitted`); the parent stopped only those owned sessions, so they do not
count as completed process-exit checks. The runner now uses `-noaudio`. An initial
configuration-only override also attempted the personal extension cache, whose
writes failed in the sandbox; no personal files changed. All Blender user
resource/extension paths are now explicitly isolated beneath `work/` and created
before launch. `-noaudio` alone did not resolve the sandbox IPC shutdown stall;
authorized scoped execution outside the tool sandbox did. Clean validation and
four-scene generation/save/reopen reruns then exited 0, and `--require-feature`
exited 1 as expected because native RNA is absent. No desktop opened. Host Python
was 3.15.2; the installed Blender bundled Python 3.13.13.

Final runtime evidence used the frozen generator SHA-256
`228f5fc7fd573cb926b56b3a8f8522cc2fa6041de43efca10eac0307a8cb1fe5`.
After the facade camera was moved back to include the entire building with
margin, all four scenes were regenerated/saved/reopened, all four CPU renders
completed, and HIP `measurable-targets` completed: every command exited 0 in
sequential 4 GB scopes. Parent visual inspection found the grid, tabletop and
five receding striped targets appropriate; the corrected facade preview includes
the entire building with margin. PNG previews are display-only.

CPU and HIP used the same installed executable, source and generator at 320×240,
32 samples, seed 71, with adaptive sampling and denoising off. Device metadata
records `CPU` and `AMD Radeon RX 6900 XT`; HIP used the hard device override.
Linear RGB RMSE was `3.2579754079794e-05`, maximum absolute difference
`0.008577823638916016`; comparison passed the provisional `0.003` / `0.02` limits.
EXR and raw float hashes are preserved in the machine-readable ledger; images,
float buffers and generated scenes remain ignored in `work/`. These results
establish the baseline environment and automation. Native CPU ray integration,
native interface/animation, disabled-feature parity and new-camera HIP physics
remain unimplemented/unaccepted.

Accepted user decision: enabled mode includes physical focus breathing; zero
tilt may differ from ordinary Cycles at finite focus. Disabled mode must preserve
the exact existing branch. Native optical units follow 1 BU = 1 metre.
