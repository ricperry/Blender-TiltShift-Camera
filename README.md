# Blender Tilt-Shift Camera

Native, physically based architectural tilt-shift camera development for Blender
5.3 and Cycles. The target is an ideal tilted thin lens with Scheimpflug focusing,
physical aperture sampling, camera shift, and image-circle clipping.

This project is under development. It does not yet provide a modified Blender
binary. CPU is the numerical reference; AMD HIP support requires a real build and
render comparison before it can be claimed.

Upstream: https://projects.blender.org/blender/blender.git

Target: `v5.3.0` / `blender-v5.3-release`. Source pins and acquisition evidence are
recorded in `docs/` as initialization proceeds. Upstream source, dependency
libraries, build trees, and renders live in ignored `work/`.

## License

Project code and documentation are licensed under **GPL-3.0-or-later**. See
[LICENSE](LICENSE). Preserve Blender and dependency license notices in patches.
