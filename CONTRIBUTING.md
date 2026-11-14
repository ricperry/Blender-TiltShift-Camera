# Contributing

Keep changes focused and preserve upstream attribution. Do not vendor the Blender
checkout or binary dependencies. Pin upstream revisions and generate reproducible
patches against those pins.

Document optical conventions alongside mathematical changes. Validate geometric
invariants numerically before judging renders. Keep CPU reference and GPU evidence
separate; never describe an untested backend as supported.

Build in `work/`; never replace a system Blender installation. Check Git status
before editing and preserve unrelated changes. Use descriptive commits and record
test commands, results, and limitations.
