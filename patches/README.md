<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Upstream patches

Use **[blender-v5.3.0-tilt-shift-m4.patch](blender-v5.3.0-tilt-shift-m4.patch)**
for the current camera. It is cumulative: native optics, interface, guides and
the bounded single-device HIP gate, all against official Blender `v5.3.0`, commit
`02f0899d78e374b63e7181d9061e1f7ab03419cc`. Apply it once to that clean pin;
**do not stack M2, M3 and M4 patches**. The [preparation script](../scripts/prepare_blender.py)
acquires/verifies the official source and safely applies this patch. See the
[fresh build workflow](../docs/build-instructions.md#current-m4-fresh-gui-build).

The patch changes 16 existing upstream files and adds one mathematical header;
the exact paths are listed in the [project README](../README.md#upstream-files-changed).
It preserves upstream notices and marks original mathematical code GPL-3.0-or-later.

`blender-v5.3.0-tilt-shift.patch` (M2 CPU) and
`blender-v5.3.0-tilt-shift-m3.patch` (M3 interface) are immutable historical
evidence. Each is independently cumulative against the same pin.
`python3 scripts/dev.py patch --milestone m4` exports the current cumulative
source changes without changing upstream HEAD or staging files; it checks the
shared native/test mathematical header and rejects unknown untracked source.
See [M2 conventions](../docs/m2-native-camera.md),
[M3 interface](../docs/m3-native-interface.md) and
[M4 evidence and limits](../docs/m4-hip-camera.md).
