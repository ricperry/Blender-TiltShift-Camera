# Project instructions

Implement a native Blender 5.3 / Cycles camera, not an image-space effect.
Use GPL-3.0-or-later for original project files and preserve upstream notices.

Inspect code, documentation, and Git status before editing. Preserve unrelated
work. Keep the upstream checkout, dependency libraries, build output, and generated
renders in ignored `work/`. Do not replace system Blender or alter upstream history.

Delegate substantive research, implementation, review, and documentation to
purpose-specific children using `gpt-6.1-sol`; normally use medium reasoning,
increasing it for difficult optical work. Use `fork_turns="none"` and bounded
context. Keep one writing agent at a time. The parent coordinates and verifies.

Document coordinate systems, units, rotation order, singularities, and tolerances.
Preserve the disabled-camera code path. Validate physics with numerical invariants
and deterministic renders. HIP support requires an actual RDNA2 build and render.

Never push, publish, deploy, or perform destructive actions without explicit user
authorization. The initialization request authorizes creating the public repository
and pushing the initial and completed initialization commits.
