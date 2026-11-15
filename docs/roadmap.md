<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Milestones and acceptance gates

| Milestone | Deliverable | Required evidence | Current state |
|---|---|---|---|
| M1 | Repository and Optical Foundation | Public project, pinned official source/libraries, reproducible tools, numerical invariants, documented conventions, four fixture generators | Foundation complete: 14,120 checks / 1,620 rays; source build/install, four CPU baseline images and actual HIP baseline comparison passed; initialization commit/push tracked separately |
| M2 | CPU Cycles Integration | Physical rays and measured reference renders, raster mapping/breathing, clipping/differentials/volume correctness, exact disabled-path regression | Bounded static CPU foundation complete: 39,214 native checks, 14 measured native renders, four bitwise disabled comparisons, persistence/migration and eight explicit rejections; see [M2 evidence](m2-validation.json) |
| M3 | Native Camera Interface | DNA/RNA/UI defaults and old-file migration, save/reopen, viewport behavior, animation/dependency updates and creative workflow | Native persistence foundation included in M2; panel, overlays and workflow pending |
| M4 | RDNA2 HIP | Actual gfx1030 build/render; CPU/HIP comparisons and measured float tolerances | Pending |
| M5 | Production Readiness | Expanded regression tests, optimization, packaging/docs, reviewable patches and upstream contribution readiness | Pending |

M1 does not establish radiometric throughput, exposure, production lens accuracy,
native camera capability or new-camera HIP support. Each later gate requires new evidence;
do not advance status merely because earlier tests remain green. Keep disabled
baseline, physical geometry, rendering quality and backend performance distinct.
No push, publication, deployment or destructive cleanup follows automatically
from a passing milestone; use the user's explicit authorization.
