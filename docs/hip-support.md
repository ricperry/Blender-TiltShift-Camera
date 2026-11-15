<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# AMD HIP support and evidence

HIP is a target, not currently accepted support. Initialization host inventory:
Fedora 45, Radeon RX 6900 XT (RDNA2 / gfx1030), ROCm/HIP 7.2.53211,
GCC 16.2.1, CMake 4.3 and Ninja 1.13.2, approximately 32 GB system RAM.
Installed toolkits and a successful CPU reference do not establish HIP correctness.

The pinned Blender supports gfx1030 in `CMakeLists.txt`. Configure
`WITH_CYCLES_DEVICE_HIP=ON`, `WITH_CYCLES_HIP_BINARIES=ON`,
`CYCLES_HIP_BINARIES_ARCH=gfx1030`, `HIP_ROOT_DIR=/usr`,
`HIP_HIPCC_EXECUTABLE=/usr/bin/hipcc` on this Fedora host.
Keep HIPRT disabled for the initial baseline. `build_files/cmake/Modules/FindHIP.cmake`
finds `HIP_HIPCC_EXECUTABLE`. The header is `/usr/include/hip/hip_version.h`;
using `/usr/lib64/rocm` as the root incorrectly reports version `0.0.0` and can
silently omit the kernel target despite apparently enabled option summaries.
The script verifies that `cycles_kernel_hip` exists after configuration.

`intern/cycles/kernel/device/hip/CMakeLists.txt` defines `cycles_kernel_hip`,
emitting `kernel_gfx1030.fatbin.zst` using `--offload-arch=gfx1030 --genco`,
`-std=c++17` and `-ffast-math`. The standalone reference is C++20/double;
production helpers must use device-compatible C++17/float and avoid exceptions,
allocation, unsupported standard-library calls and host-only data. Validate and
bound geometry on the host; fast math makes nonfinite guards alone insufficient.

Acceptance requires all of the following, recorded with exact source/library
pins, compiler versions, commands, hardware/device selection and output hashes:

1. Actual gfx1030 kernel compilation and installation in an isolated build.
2. Actual Cycles render selecting HIP without CPU fallback.
3. Disabled baseline regression and enabled tilt/shift/focus/coverage scenes.
4. CPU/HIP linear-float pixel comparisons at matching resolution, seed, samples,
   denoising/adaptive settings, with explicit measured tolerances.
5. No invalid rays, NaNs, clipping errors, lost volume initialization or unstable
   aperture behavior at accepted parameter boundaries.

The provided render runner filters HIP devices by upstream driver requirements,
disables CPU devices and sets the pinned `_cycles.set_device_override('HIP')`
hard override. This prevents upstream's ordinary preference fallback to CPU;
missing/incompatible devices fail. Its smoke comparison defaults are RGB RMSE `0.003` and
maximum absolute error `0.02` in linear EXR values at 320×240 / 32 samples. These
are provisional thresholds, not established acceptance tolerances. Independent
stochastic CPU/HIP noise can exceed them; investigate and choose documented
sample counts/tolerances rather than silently loosening checks. Exact parity is
expected only for repeat comparisons where device and deterministic settings
support it. Performance and portability claims require separate evidence.
