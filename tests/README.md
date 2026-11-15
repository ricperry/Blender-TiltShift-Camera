# Validation

`optics_tests.cpp` independently checks the M1 double optical reference.
`native_float_tests.cpp` compiles the actual shared scalar float kernel helper
against that reference and checks reflected rotations, finite/virtual/infinite
conjugacy, coverage, physical body-anchor shift, off-axis object focus, exact
clip planes, inverse chief projection and neighboring sampled-ray footprints.
The kernel mirror must match `src/native/tilt_shift_math.h` byte-for-byte;
`dev.py patch` checks this before exporting.

Run `python3 scripts/dev.py test-optics`. Current native float matrix: 39,214
checks; measured maximum direction error `1.35967e-7` and aperture-origin error
`9.07662e-10 m`. M1's 14,120 checks remain separate. Native CPU rendered fixtures
and disabled parity are separate gates; see [M2 validation](../docs/m2-native-camera.md).
