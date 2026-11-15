<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Milestones and acceptance gates

| Milestone | Deliverable | Required evidence | Current state |
|---|---|---|---|
| M1 | Repository and Optical Foundation | Public project, pinned official source/libraries, reproducible tools, numerical invariants, documented conventions, four fixture generators | Reference implemented: 14,120 checks / 1,620 deterministic rays; native baseline build/runtime evidence tracked separately |
| M2 | CPU Cycles Integration | Physical rays and measured reference renders, raster mapping/breathing, clipping/differentials/volume correctness, exact disabled-path regression | Not implemented |
| M3 | Native Camera Interface | DNA/RNA/UI defaults and old-file migration, save/reopen, viewport behavior, animation/dependency updates and creative workflow | Not implemented |
| M4 | RDNA2 HIP | Actual gfx1030 build/render; CPU/HIP comparisons and measured float tolerances | Pending |
| M5 | Production Readiness | Expanded regression tests, optimization, packaging/docs, reviewable patches and upstream contribution readiness | Pending |

M1 does not establish radiometric throughput, exposure, production lens accuracy,
native camera capability or HIP support. Each later gate requires new evidence;
do not advance status merely because earlier tests remain green. Keep disabled
baseline, physical geometry, rendering quality and backend performance distinct.
No push, publication, deployment or destructive cleanup follows automatically
from a passing milestone; use the user's explicit authorization.
