# Upstream patches

`blender-v5.3.0-tilt-shift.patch` is the M2 native CPU implementation against
`02f0899d78e374b63e7181d9061e1f7ab03419cc`. Export with
`python3 scripts/dev.py patch`; this preserves upstream HEAD and index and checks
the shared native test/kernel header. Review and apply only to the exact pin.
It includes upstream notices and marks original mathematical code GPL-3.0-or-later.
See [M2 conventions and evidence limits](../docs/m2-native-camera.md).
