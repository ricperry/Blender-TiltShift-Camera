<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# M4 tilt-shift camera on AMD HIP

M4 reuses the M2/M3 tilt-shift camera and shared C++17/float kernel math.
The cumulative patch is `patches/blender-v5.3.0-tilt-shift-m4.patch` against the
recorded official 5.3.0 pin. Earlier patches, fixtures and preserved installs
remain historical evidence. The only M4 native behavior change is a bounded
execution-device gate: ordinary CPU or **one HIP device with HIPRT disabled**.
Same-type multi-GPU aggregates retain `DEVICE_HIP`, so the gate also checks the
actual `multi_devices` list. Mixed CPU/HIP, multi-GPU, HIPRT and all other GPU
backends remain rejected. Disabled cameras return before this gate and retain
the existing upstream perspective-camera path.

The Camera Data message for a non-Cycles engine now says that physical rendering
requires Cycles. The existing M3 controls, canonical properties, units, guides
and animation behavior remain authoritative. M4 introduces no optical formula,
serialized field or altered default.

## Physics and numerical domain

Camera-local units remain unscaled metres: Blender X right, Y up, negative Z
scene-going; Cycles uses positive Z scene-going. Lens and sensor RNA millimetres
convert by `1e-3`. Angles are radians with fixed optical
`Rz(axis) Ry(swing) Rx(tilt)` order. See [M2 conventions](m2-native-camera.md)
for the reflection, translated lens centre, focus breathing and clip mapping.
Image circle zero means unbounded angular coverage. Existing perspective,
static-camera, stereo, adaptive-dicing and geometry guards remain unchanged.

HIP compilation uses `-ffast-math`; host validation therefore still rejects
invalid geometry before any kernel launch. The existing dimensionless `1e-5`
margin, scaled plane tests, filter-padded sensor bounds and full anamorphic
aperture ellipse remain unchanged. M4 near-boundary fixtures accept a sensor
conjugacy with `f/b` approximately `2e-5`, and a tilted f/2 aperture whose roughly
2.5 mm camera-Z extent lies just before the 3 mm near plane. They require finite,
unit-radiance images within `2e-4`; they do not weaken the rejection threshold.

## Build and execution provenance

For a new checkout, follow the complete [fresh M4 GUI CPU and HIP build](build-instructions.md#current-m4-fresh-gui-build)
using `work/build-blender-m4` and `work/install-blender-m4`. It includes source
preparation, dependency acquisition, GUI prerequisites and resource caps. Apply
only the cumulative M4 patch; do not stack M2/M3 patches.

The commands below retain the original validation build's provenance: it reused
one existing GUI-capable official build tree and a distinct install prefix. Enable
HIP binaries for `gfx1030`, retain HIPRT off, compile the new kernel with one job,
then build/install the host with four jobs. Blender's official `delayed_install`
places its compressed fatbin and current kernel headers together. Do not copy an
M1 fatbin or overwrite any preserved installation.

```sh
/usr/bin/cmake -S work/blender -B work/build-blender-cpu \
  -DWITH_CYCLES_DEVICE_HIP=ON -DWITH_CYCLES_DEVICE_HIPRT=OFF \
  -DWITH_CYCLES_HIP_BINARIES=ON -DCYCLES_HIP_BINARIES_ARCH=gfx1030 \
  -DHIP_ROOT_DIR=/usr -DHIP_HIPCC_EXECUTABLE=/usr/bin/hipcc \
  -DCMAKE_INSTALL_PREFIX="$PWD/work/install-blender-m4"
/usr/bin/cmake --build work/build-blender-cpu --target cycles_kernel_hip --parallel 1
/usr/bin/cmake --build work/build-blender-cpu --target install --parallel 4
python3 scripts/dev.py patch --milestone m4
```

Use the existing 18 GiB/zero-swap build scopes and sequential two-core/4 GiB
runtime scopes in [build instructions](build-instructions.md). Preserve source
HEAD, dependency libraries and all earlier binaries. Inspect hardware load and
memory before GPU work. All resource/cache/config directories belong in ignored
`work/`; no personal desktop or system Blender is involved.

The new runner uses the **same installed executable** for CPU and HIP. HIP
requires exactly one compatible enumerated device, explicitly disables HIPRT
and CPU device preferences, and uses `_cycles.set_device_override('HIP')` to
prevent ordinary CPU fallback. CPU likewise sets the hard CPU override. Run with
`--debug-cycles` and retain the selected-device and `Using precompiled kernel.`
log lines. Verify the installed and generated `kernel_gfx1030.fatbin.zst` hashes
match. The runtime JSON captures host executable, cumulative patch, installed
fatbin, wrapper and immutable fixture hashes before execution and checks them
again before writing results.

## Reproduction

For each `BACKEND` (`cpu`, then `hip`), run sequentially:

```sh
work/install-blender-m4/blender --background -noaudio --factory-startup \
  --debug-cycles --python-exit-code 1 --python scripts/blender_m4_validation.py -- \
  --output work/m4-validation/BACKEND --backend BACKEND --case all
work/install-blender-m4/blender --background -noaudio --factory-startup \
  --debug-cycles --python-exit-code 1 --python scripts/blender_m4_validation.py -- \
  --output work/m4-validation/BACKEND --backend BACKEND --case visual
work/install-blender-m4/blender --background -noaudio --factory-startup \
  --debug-cycles --python-exit-code 1 --python scripts/blender_m4_validation.py -- \
  --output work/m4-validation/BACKEND --backend BACKEND --case chart
work/install-blender-m4/blender --background -noaudio --factory-startup \
  --debug-cycles --python-exit-code 1 --python scripts/blender_m4_validation.py -- \
  --output work/m4-validation/BACKEND --backend BACKEND --case benchmark
python3 scripts/run_m4_guards.py --blender work/install-blender-m4/blender \
  --output work/m4-validation --backend BACKEND
```

`all` imports the immutable M2 suite with setup/render adapters in memory. It
retains all existing numerical assertions and adds the two boundary renders and
one combined tilt/swing/axis/shift, seven-blade anamorphic-aperture/coverage
fixture. No historical fixture is rewritten. `visual` imports the immutable
user-facing tabletop chart at 1280×800/128 samples, with its matched −8° lens
tilt, 50 mm/f1.4 lens and 0.65 m manual focus. It saves EXR, raw RGBA, PNG and an
editable `.blend`. `chart` renders a 960×600/128-sample depth chart with explicit
UVs and a 512×512 image texture, exercising texture filtering and aperture rays.
The guard runner requires all eight original rejection messages, a unique fresh
result directory, matching provenance and Blender's expected sticky-error exit
one. Other exit codes or incomplete evidence fail.

```sh
python3 scripts/compare_m4.py work/m4-validation/cpu work/m4-validation/hip \
  --output work/m4-validation/cpu-hip-comparison.json
```

The final comparator requires exactly all 19 expected render names and one
global provenance tuple across every case/backend; actual lens, sensor,
fit, shift, movement, aperture, focus, clip, camera/target transforms, raster
filter, pixel aspect, resolution, seed and samples; disabled denoising/adaptive
sampling; matching executable/patch/fixture/fatbin hashes; finite, hash-checked
linear RGBA buffers. PNGs are display evidence only. Limits were declared before
hardware testing: RGB RMSE `0.003`, maximum `max(0.0002, 2/samples)` (two unit
emission sample decisions), and `2e-4` for both on constant boundary worlds.
Only 32-sample coverage receives maximum `0.0625`; 128 samples receive `0.015625`,
256 receive `0.0078125`, and 1024 receive `0.001953125`. A failure requires
investigation rather than a silently enlarged threshold.

Benchmarks use the same backend, scene, 960×600 resolution, seed and 64 samples
for ordinary, enabled-zero and enabled-tilt cameras. Each variant warms once,
then runs three repeats in rotated order. Report all timings, medians and ratios
per backend. Timing surrounds completed `bpy.ops.render.render()` calls and
includes synchronization/session overhead, without image export. These are
completed-render mode comparisons: breathing and tilt also change texture and
intersection workload, so the ratios do not isolate camera-math overhead.
They do not establish general CPU/GPU speedups, production scene throughput or
frame latency. The frozen fixture's initial `interpretation` field calls the
result camera overhead; this narrower interpretation governs acceptance.

## Acceptance status

The bounded M4 gate passes on the actual Radeon RX 6900 XT/gfx1030 with HIP
7.2.53211. A freshly compiled kernel was officially installed with the same new
GUI-capable host executable used by CPU and HIP. Debug logs name the RX 6900 XT
as the path-tracing device and confirm the installed precompiled kernel. The
generated/installed fatbin hash is
`466b9fc17b95fa079eb260b33ca3277685b7172862cb41b9fdc6adef6fa9a994`;
the executable hash is
`901f89e45d72e21b547c9eedac199e4e29a04e40f01f91f65994a88db4bec892`.
The [M4 ledger](m4-validation.json) preserves measured results and artifact hashes.

All 19 final CPU/HIP render pairs passed unchanged predeclared bounds; 15 were
bitwise RGBA identical. Across the suite, maximum RGB RMSE was
`0.0001215173175` and maximum absolute error `0.007818318903`. Retained assertions
passed independently on both backends: maximum centroid error `.036622 px`,
measured CoC `16.48236 px` versus analytic `16.46091 px`, tilted outer-target
variance ratios `.16094` / `.16236`, correct image-circle interior/exterior
coverage, zero leaked near/far target flux and volume transmittance about
`.670273` versus axial `exp(-.4)=.670320`. Both accepted boundary worlds were
finite and exactly unit radiance; these constant worlds establish accepted
execution and weight, rather than accurate near-singularity ray directions or
differentials. Both backends retained all eight explicit rejection messages.

All 14 retained M3 CPU buffers and all four unmodified M1 CPU baseline buffers
remain bitwise identical. GPU disabled regression is measured float parity,
with maximum M1 HIP/M4 HIP error `9.536743164e-7`, rather than bitwise identity.
At 32 samples, ordinary grid/facade CPU/HIP smoke maxima exceeded the original
provisional `.02` bound (`.0212893188` / `.0202977657`). Preserved unmodified M1
CPU/HIP reproduction gave exactly the same maxima. These pre-existing smoke
failures remain recorded; no threshold was enlarged to hide them. The same-
backend HIP regressions passed all four fixtures within the original bounds.

CPU/HIP focus charts were visually inspected: all five depth rows `.503–.920 m`
remain sharp at the matched −8° tilt. The distinct image-texture chart retains
all 15 panels, sharp middle-depth frame/texture and blurred outer-depth pupil
footprints, without visible missing tiles or device artifacts. These images
and float comparisons exercise aperture/filtering behavior; they do not provide
direct derivative-buffer equality, MTF, production radiometry or real-lens
calibration. No new GNOME/Mutter, accessibility, human workflow, other hardware,
multi-device, HIPRT or other GPU-backend acceptance follows from this gate.

## Completed-render timings and interruption

Clean final benchmark processes exited zero on both backends. Each variant had
one warm-up and three rotated paired repeats at 960×600/64 samples:

| Backend | Ordinary median | Enabled zero median | Enabled tilt median | Ratios to ordinary, zero / tilt |
| --- | ---: | ---: | ---: | ---: |
| CPU, two threads | 3.89072 s | 4.88993 s | 4.92900 s | 1.25682 / 1.26686 |
| HIP, RX 6900 XT | 0.0982514 s | 0.104285 s | 0.104767 s | 1.06141 / 1.06632 |

These are completed-render ratios for the specified scene and modes. Breathing,
framing, texture filtering and intersection work change along with ray sampling;
they do not isolate camera-math cost. Short HIP times also make session and
synchronization overhead material. They are not general cross-backend speedup
claims. All nine timings per backend remain in the ledger.

The first CPU benchmark wrote its JSON and printed `Blender quit`, but the outer
test scope returned exit 143 before recording the process result or launching
HIP. That interrupted scope peaked at 718.3 MiB; the checked journal did not
identify an OOM event. Its cause remains unestablished. Its log/JSON are preserved
under `work/m4-benchmark-interrupted/` and excluded from final timing acceptance.
CPU and HIP were then run separately under the same runtime caps and each
completed with observed exit zero; final medians above use those clean reruns.
