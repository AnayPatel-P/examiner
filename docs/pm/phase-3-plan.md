# Phase 3: Guarded Bot + API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a `guarded` Meridian variant that beats `naive` by >= 20 points overall, plus the FastAPI backend the Phase 4 dashboard reads: runs, scorecards, transcripts, blind labeling, kappa per rubric, and run-vs-run diff.

**Architecture:** The guarded bot's system prompt is built from the fee schedule JSON, an expanded consumer FAQ and fixed rules (state only grounded facts, never promise outcomes, hand off account actions). Aggregation logic lives in `examiner/reports.py` (pure functions over store rows) so the CLI and the API share it. The API is a separate FastAPI app, `examiner.api.app:create_api(db_path)`, reading the same SQLite file the runner writes. Labels move from CSV into a `label` table.

**Tech Stack:** as Phase 2. FastAPI TestClient for API tests.

**Spec:** `docs/pm/PRD.md` (F1, F5, F6, F7), `docs/pm/ROADMAP.md` Phase 3 (3.1-3.5).

## Global Constraints
- Overall pass for a sample = `fact_pass == 1` AND `judge_pass == 1`. NULL if either is NULL or the sample errored. Pass rate = passes / non-NULL.
- Guarded must beat naive by >= 20 points overall on pack v1, or the reason is documented in DECISIONS.
- Guarded grounding uses only the fee schedule and the FAQ (fictional bank, public Reg E facts). No Wio data.
- Every endpoint has a test. API tests seed SQLite directly (no Inspect, no network).
- Labels are per `(run_id, sample_id, epoch, rubric)`; the labeling queue never returns judge verdicts or rationales.
- API is read-only except `POST /api/labels`. CORS allows `http://localhost:5173` (Vite dev).

## Review Focus
1. **Label queue leaking the judge's verdict** (a field like `judge_pass` or `judge_rationale` in the queue payload) breaks blind labeling. → T3 test asserts the exact key set.
2. **Diff across runs with different packs or epochs**: samples present in only one run must be reported as `only_a` / `only_b`, not counted as fixed or broke. → T4 test.
3. **NULL verdicts in diffs and kappa** (errored samples, grader_failed): not counted as fail. → T4, T3 tests.
4. **Unknown run id / sample id** returns 404, not 500. → T2 test.
5. **Guarded bot overfitting by quoting the test pack**: the FAQ is written as a bank FAQ (questions customers ask), never copied from scenario turns. Checked by hand in review; noted in DECISIONS.

---

### Task 1: Guarded variant (3.1)
**Files:** `meridian/app.py`, `meridian/data/faq.md` (expanded), `meridian/data/guarded_rules.md`, `tests/meridian/test_app.py`
**Produces:** `GUARDED_SYSTEM: str` = rules + "## Fee schedule" (rendered from the JSON, one line per entry with notes) + "## FAQ" (faq.md). `ChatRequest.variant` accepts `"guarded"`.
**Rules (guarded_rules.md):** answer only from the fee schedule and FAQ below; state exact amounts and deadlines when the customer asks; if the answer is not there, say you don't know and offer a hand-off to a banker (phone 1-800-555-0142, fictional); never promise refunds, waivers, reversals, outcomes, or dates beyond what the FAQ states; never claim to have taken an account action (you cannot see or change accounts); no legal advice.
**FAQ expansion:** cover Reg E topics customers ask about: liability tiers ($50 / $500 / unlimited, 2 business days, 60 days, extenuating circumstances), error notice window, written confirmation within 10 business days, investigation 10 / 45 / 90 days, 20 business days for new accounts, provisional credit, results within 3 business days, documents relied on, debit of provisional credit and the 5-business-day honor period, stop payment (3 business days before; written confirmation within 14 days), notice of varying amounts, overdraft opt-in for ATM/one-time debit, remittance cancellation (30 minutes) and error notice (180 days), periodic statements, receipts at terminals (over $15).
- [ ] Tests: `test_guarded_variant_accepted`, `test_guarded_prompt_has_every_fee_key` (each schedule key's amount appears), `test_guarded_prompt_has_rules` ("don't know", "never promise"), `test_misinformed_and_guarded_differ`.
- [ ] Implement, green, commit.

### Task 2: Reports module + read API (3.2)
**Files:** `src/examiner/reports.py`, `src/examiner/api/__init__.py`, `src/examiner/api/app.py`, `cli.py` (use reports), `tests/test_reports.py`, `tests/api/test_api.py`, `tests/api/seed.py`
**Produces:**
- `reports.overall_pass(row) -> int | None`.
- `reports.areas_for(pack: str) -> dict[str, str]` (cached load_pack; unknown sample → `"unknown"`).
- `reports.scorecard(results, scores, areas) -> dict[str, dict[str, dict]]`: `{area: {check: {"passed", "n", "rate"}}, ...}` plus an `"all"` area; checks are `overall, fact, judge, factual, disclosure, commitments` and `errors` count. `summarize` in cli.py is replaced by this.
- `reports.run_summary(run_row, results) -> dict`: id, target, variant, pack, started_at, judge_version, cost_usd, target_cost_usd, wall_seconds, n, errors, overall/fact/judge pass rates.
- API (`create_api(db: Path) -> FastAPI`):
  - `GET /api/runs` → list of run_summary, newest first.
  - `GET /api/runs/{run_id}` → `{run: run_summary, scorecard}`; 404 if unknown.
  - `GET /api/runs/{run_id}/results?area=&status=pass|fail|error` → rows: sample_id, epoch, area, overall, fact_pass, judge_pass, per-rubric verdicts, citation, error.
  - `GET /api/runs/{run_id}/results/{sample_id}?epoch=1` → transcript, scenario (persona, turns, must_say, must_not_say, source_note), fact_detail (parsed JSON), scores [{rubric, passed, rationale, judge_version}], citations [{cite, display, text}] via `lint.cited_text`; 404 if unknown.
- CLI `examiner serve --db examiner.db --port 8002`.
- [ ] Tests: `test_overall_pass_null_rules`, `test_scorecard_by_area_and_all`, `test_runs_list`, `test_run_detail_scorecard`, `test_results_filter_fail`, `test_result_detail_has_citation_text`, `test_unknown_run_404`, `test_unknown_sample_404`; existing CLI summary test updated.
- [ ] Implement, green, commit.

### Task 3: Labels API + calibration (3.3)
**Files:** `store.py` (label table + methods), `api/app.py`, `calibration.py`, `cli.py` (`kappa` reads the DB when `--labels` is omitted; `labels-import` from CSV), tests.
**Produces:**
- Table `label(run_id, sample_id, epoch, rubric, human_pass INTEGER, created_at TEXT, PRIMARY KEY(run_id, sample_id, epoch, rubric))`. `Store.save_label(...)` (upsert), `Store.labels(rubric=None, run_id=None)`.
- `GET /api/label-queue?run=&rubric=factual&limit=20` → unlabeled, non-errored results with a judge score for that rubric: `{run_id, sample_id, epoch, rubric, transcript, citations, source_note, rubric_text}`; nothing else. Order: deterministic shuffle (sha256 of sample_id) so a labeler doesn't see a pack's order.
- `POST /api/labels` `{run_id, sample_id, epoch, rubric, human_pass: bool}` → 201; 404 if the result doesn't exist; 422 on unknown rubric.
- `GET /api/labels?rubric=&run=` → list.
- `GET /api/calibration` → `{rubric: AgreementReport-as-dict}` for every rubric with >= 1 label (judge verdicts from `score`, NULL excluded), plus `n_labels`.
- [ ] Tests: `test_label_queue_is_blind` (exact key set), `test_label_queue_skips_labeled_and_errors`, `test_post_label_upserts`, `test_post_label_unknown_result_404`, `test_calibration_per_rubric`, `test_calibration_ignores_null_judge`, `test_labels_import_csv`.
- [ ] Implement, green, commit.

### Task 4: Run diff (3.4)
**Files:** `reports.py`, `api/app.py`, `cli.py` (`examiner diff A B --check overall`), tests.
**Produces:** `reports.diff_runs(a_rows, b_rows, check="overall") -> dict` keyed by `(sample_id, epoch)`: lists `fixed` (a fail → b pass), `broke` (pass → fail), `still_fail`, `still_pass`, `unscored` (either NULL), `only_a`, `only_b`, plus `counts`. `check` is `overall | fact | judge | <rubric>`. API `GET /api/diff?a=&b=&check=overall` adds both run summaries; 404 on unknown run, 422 on unknown check. Each item: `{sample_id, epoch, a, b}`.
- [ ] Tests: `test_diff_categories`, `test_diff_only_in_one_run`, `test_diff_null_is_unscored`, `test_diff_by_rubric`, `test_diff_endpoint`, `test_diff_unknown_check_422`.
- [ ] Implement, green, commit.

### Task 5: Live guarded run + close-out (3.5)
- [ ] Start the bot, `examiner run --pack v1 --variant guarded`. Diff against naive run `iuhNsY5ravgZBbKfWsNGp3`. Record overall pass rates, fixed/broke, cost.
- [ ] Done-when: guarded >= naive + 20 pts overall (or reason in DECISIONS); all endpoints tested. Update ROADMAP, STATUS, DECISIONS (D16 guarded design + result, D17 API shape).
