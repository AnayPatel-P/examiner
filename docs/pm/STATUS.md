# Status

**Updated:** 2026-11-22
**Current phase:** C (Build), roadmap Phase 5 (calibrate, export, ship) mostly done, merged to `main`
**Current milestone:** Phase 5, waiting on human labels for kappa
**Last completed:** fresh v1 runs on the new machine (naive 21.3%, guarded 92.1%, misinformed 0.8%; D21); 102-item calibration batch; failure taxonomy; cost and latency per run; regression gate + baseline; offline rescore; deployment memo (docs/memo.md); README rewrite; static scorecard snapshot and Pages workflow.
**Next up:** Anay labels calib-v1 (`/label?batch=calib-v1`), then `examiner calibration`, revise any rubric under 0.6, `examiner rescore`, re-export. Portfolio site card (drafted, waiting on Anay).
**Blockers / open questions:** kappa not measured (Anay chose to ship without labels for now). Repo is public (2026-11-22) and the scorecard is live at https://anaypatel-p.github.io/examiner/. The eval-gate workflow needs an `ANTHROPIC_API_KEY` repo secret. Phase 5 is merged and pushed to `main`; CI (lint, tests, baseline check, web tests) is green.

## History
- 2026-11-22: repo made public after a full-history secret scan (clean); Pages live.
- 2026-11-22: Phase 5 built on `phase-5`: batches, taxonomy, gate, rescore, export, memo, README. Fresh runs (D21). Labeling deferred by Anay.
- 2026-11-18: Phase 4 built (plan: phase-4-plan.md), direction set with ui-direct, verified with ui-verify, reviewed, fixed.
- 2026-11-18: Phase 3 built (plan: phase-3-plan.md), reviewed, fixed; live guarded runs (93.7% pre-fix, 90.6% final).
- 2026-11-18: Phase 2 built (plan: phase-2-plan.md), reviewed, fixed; live runs naive + misinformed.
- 2026-11-18: Spike labeled (in chat), kappa computed, D12 logged.
- 2026-11-18: Key added; live smoke + 4-epoch spike run done.
- 2026-11-18: Plan approved. Phase 1 plan in `phase-1-plan.md`; built on branch `phase-1` (local commits, not pushed).
- 2026-11-18: Intake + elaborate (2 question rounds, suggestions picked), brief approved, PRD and roadmap written.
