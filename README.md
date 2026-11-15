# Blender Tilt-Shift Camera

Native, physically based architectural tilt-shift camera development for Blender
5.3 and Cycles. The target is an ideal tilted thin lens with Scheimpflug focusing,
physical aperture sampling, camera shift, and image-circle clipping.

M2's bounded static CPU camera foundation is complete: native physical rays,
shifted lens origins, off-axis object focus, coverage, clipping and volume tests
passed. All four disabled fixtures match the unmodified baseline bitwise.
See [native conventions](docs/m2-native-camera.md) and the
[measured M2 evidence](docs/m2-validation.json). The [M3 interface](docs/m3-native-interface.md)
is complete within its bounded CPU/private-GUI scope: native panels, physical
guides, persistence, animation and retained regressions pass. See the
[M3 evidence](docs/m3-validation.json). [M4 native HIP](docs/m4-hip-camera.md)
now passes on the actual RX 6900 XT/gfx1030: a fresh kernel build, 19 matching
CPU/HIP render comparisons, retained physics/guard checks and disabled regressions.
Support is bounded to CPU or one non-HIPRT HIP device; see the
[M4 evidence and limits](docs/m4-validation.json).

Upstream: https://projects.blender.org/blender/blender.git

Target: `v5.3.0` / `blender-v5.3-release`, commit
`02f0899d78e374b63e7181d9061e1f7ab03419cc`. Upstream source, dependency
libraries, build trees, and renders live in ignored `work/`.

The implemented M1 deliverable is a dependency-free C++20 optical reference with
14,120 numerical checks over 1,620 deterministic rays. It includes physical focus
breathing, tilted-plane aperture sampling, Scheimpflug/hinge geometry, and an
explicit angular coverage stop. M2 connects a separately tested float implementation
to native RNA and the Cycles perspective kernel. Enabled zero-tilt finite focus is
intentionally allowed to differ from Cycles' fixed field of view; disabled operation must preserve upstream.

```sh
python3 scripts/dev.py check-deps
python3 scripts/dev.py test-optics
```

See [build instructions](docs/build-instructions.md), the
[optical model](docs/optical-model.md), [architecture](docs/architecture.md),
[Blender integration map](docs/blender-integration.md),
[HIP evidence requirements](docs/hip-support.md),
[roadmap](docs/roadmap.md), and [current evidence](docs/initialization-status.md).
Four deterministic fixture generators are described in [examples](examples/README.md).

## License

Project code and documentation are licensed under **GPL-3.0-or-later**. See
[LICENSE](LICENSE). Preserve Blender and dependency license notices in patches.
