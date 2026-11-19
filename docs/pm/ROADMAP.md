# Examiner — Roadmap

**Stack:** React + Vite + TypeScript · Python 3.12 (uv) + FastAPI + Inspect · SQLite · local + GitHub Pages static export (reasons in DECISIONS.md)
**Riskiest assumptions:** (a) a Sonnet judge can reach kappa ≥ 0.6 against Anay's labels; (b) Inspect drives a multi-turn external HTTP target cleanly → both tested in Phase 1.

Rough pacing: 2-3 weeks of evenings, ~1-2 sessions per phase.

## Phase 1 — Walking skeleton + judge spike
**Goal:** one scenario flows end to end: Meridian bot → Inspect run → judge score → SQLite row.
**Demo:** `examiner run --target http://localhost:8001 --pack smoke` prints a pass/fail table for 5 scenarios; a spike notebook shows judge-vs-Anay agreement on 20 transcripts.
- [x] 1.1 Repo baseline: uv, ruff, pyright, pytest, `.env.example`, Makefile (`make dev`, `make test`), CI on push
- [x] 1.2 Meridian Bank data: fictional fee schedule + FAQ (JSON/Markdown)
- [x] 1.3 Meridian bot `POST /chat` (FastAPI, Haiku 5.5), `naive` variant only
- [x] 1.4 Scenario schema (Pydantic) + 5 hand-written smoke scenarios
- [x] 1.5 Inspect task + custom HTTP solver (multi-turn) + deterministic fact scorer
- [x] 1.6 Sonnet judge scorer, one rubric (factual accuracy)
- [x] 1.7 Index results into SQLite
- [ ] 1.8 Spike: label 20 transcripts by hand, compute kappa, write findings in DECISIONS.md (tooling done: `examiner label-export` / `examiner kappa`; needs a live run + Anay's labels)
**Done when:**
- [ ] One command runs the 5 smoke scenarios and stores results
- [ ] Spike result logged: judge agreement number + go/no-go on the judge approach

## Phase 2 — Scenario pack v1
**Goal:** the real content: ~120 scenarios with ground truth and citations.
**Demo:** a generated scenario index (Markdown) and a full naive run's pass rate by area.
- [ ] 2.1 Reg E seeds (~30): unauthorized transfers, error-resolution timelines, provisional credit, notice periods; each with 12 CFR 1005 citations
- [ ] 2.2 Fees/overdraft seeds (~30) grounded in the Meridian fee schedule
- [ ] 2.3 Variant generator (paraphrase + persona), stable ids, dedupe
- [ ] 2.4 Schema tests + citation lint (every scenario has a valid citation and source note)
- [ ] 2.5 Full rubric set: factual accuracy, required disclosure, no invented commitments
- [ ] 2.6 Budget cap, concurrency, retries, prompt caching; cost tracked per run
**Done when:**
- [ ] `--pack v1` runs ~120 scenarios in < 10 min for ≤ $5
- [ ] Every failure stores the citation it breaks

## Phase 3 — Guarded bot + API
**Goal:** the before/after story and the backend the dashboard needs.
**Demo:** naive vs guarded runs side by side via API; diff JSON shows fixed/broke.
- [ ] 3.1 `guarded` Meridian variant: grounded on fee schedule + FAQ, refusal and hand-off rules
- [ ] 3.2 FastAPI read API: runs, results, scorecard aggregates, transcript detail
- [ ] 3.3 Labels API (create/list) + calibration computation (kappa per rubric, confusion counts)
- [ ] 3.4 Run-vs-run diff endpoint
- [ ] 3.5 Tests for aggregates, kappa and diff logic (TDD)
**Done when:**
- [ ] Guarded beats naive on overall pass rate (target ≥ 20 pts) or the reason is documented
- [ ] All endpoints covered by tests

## Phase 4 — Dashboard
**Goal:** the web app: browse, drill in, label, diff.
**Demo:** click through a run's scorecard → a failure with its citation → label 10 transcripts → diff naive vs guarded.
- [ ] 4.0 UI direction: invoke `design:ui-direct` with the PRD handoff brief; Anay picks a direction
- [ ] 4.1 Vite + React + TS scaffold inside the repo, API client
- [ ] 4.2 Runs list + scorecard (by area and rubric)
- [ ] 4.3 Failure drill-down: transcript, judge rationale, failed facts, reg citation
- [ ] 4.4 Labeling screen (blind to judge, keyboard shortcuts)
- [ ] 4.5 Calibration report screen
- [ ] 4.6 Diff screen
- [ ] 4.7 `design:ui-verify` pass
**Done when:**
- [ ] All 5 screens work against real API data
- [ ] Direction logged in DECISIONS.md and PRD §14 filled in
- [ ] ui-verify passes (console clean, a11y, no overflow)

## Phase 5 — Calibrate, export, ship
**Goal:** real numbers and a public demo.
**Demo:** the public scorecard URL + README case study + a 60-second video.
- [ ] 5.1 Label ≥ 100 transcripts; revise at least one rubric; record kappa before/after
- [ ] 5.2 Static scorecard export (JSON snapshot + Vite build) → GitHub Pages (if time; else v1.1)
- [ ] 5.3 README: problem, architecture diagram, how to run, results, limitations, "not legal advice"
- [ ] 5.4 Final acceptance check against the PRD; code review
- [ ] 5.5 Update vault `wiki/projects/examiner.md` + resume bullet with the real numbers
**Done when:**
- [ ] Calibration report with ≥ 100 labels is in the repo
- [ ] README results section has real kappa, pass rates and cost

## Later (post-v1)
See PRD §13 Future add-ons.
