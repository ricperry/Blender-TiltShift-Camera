# Blender Tilt-Shift Camera

Native, physically based architectural tilt-shift camera development for Blender
5.3 and Cycles. The target is an ideal tilted thin lens with Scheimpflug focusing,
physical aperture sampling, camera shift, and image-circle clipping.

The M1 baseline environment is ready: the unmodified pinned Blender and gfx1030
kernel built, four CPU scenes rendered, and the actual CPU/HIP targets comparison
passed on RX 6900 XT. Native tilt-shift integration remains unimplemented; no
modified camera binary or new-camera HIP support is claimed. CPU is the numerical
reference. See [baseline validation](docs/baseline-validation.json) for evidence.

Upstream: https://projects.blender.org/blender/blender.git

Target: `v5.3.0` / `blender-v5.3-release`, commit
`02f0899d78e374b63e7181d9061e1f7ab03419cc`. Upstream source, dependency
libraries, build trees, and renders live in ignored `work/`.

The implemented M1 deliverable is a dependency-free C++20 optical reference with
14,120 numerical checks over 1,620 deterministic rays. It includes physical focus
breathing, tilted-plane aperture sampling, Scheimpflug/hinge geometry, and an
explicit angular coverage stop. It is not yet connected to Blender's native RNA
or Cycles kernel. Enabled zero-tilt finite focus is intentionally allowed to
differ from Cycles' fixed field of view; disabled operation must preserve upstream.

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
