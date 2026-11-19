# Phase 2: Scenario Pack v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ~120 Reg E and fee scenarios with verified citations, three versioned rubrics, a "misinformed" bot for seeded failures, and a run that finishes in < 10 min for ≤ $5 with the full cost tracked.

**Architecture:** Reg E text is parsed from the official eCFR XML into a committed paragraph snapshot (`regs/reg_e.json`). Scenarios cite paragraph ids (`12 CFR 1005.11(c)(2)(i)`) or fee-schedule keys (`fee:overdraft`). A lint rejects any citation that isn't in the snapshot or the schedule. The judge gets the cited paragraph text, so it grades against the regulation itself rather than a paraphrase. Seeds are hand-written. Variants are generated once by Haiku, committed, and stable. Scores are stored per rubric.

**Tech Stack:** as Phase 1, plus `xml.etree` (stdlib) for eCFR.

**Spec:** `docs/pm/PRD.md` (F2, F3, F4, F9), `docs/pm/ROADMAP.md` Phase 2 (2.1-2.7), `docs/pm/spike-judge.md` (D12).

## Global Constraints
- Reg E source: eCFR versioner API, `https://www.ecfr.gov/api/versioner/v1/full/{date}/title-12.xml?part=1005`, which requires `Accept-Encoding: gzip`. The snapshot records its date.
- Every scenario has ≥ 1 citation, and every citation resolves (lint test fails otherwise).
- ≥ 30 seeds per area. Pack v1 ≈ 120 scenarios (seeds + 1 variant each).
- Rubric prompts are versioned: `factual-v2`, `disclosure-v1`, `commitments-v1`. The version is stored on every score.
- Judge: Sonnet 5.5, `reasoning_effort="medium"`, `max_retries=3`. Target: Haiku 5.5.
- Run cost: `--max-run-cost` (default 5.0 USD) sets Inspect's per-sample `cost_limit = max_run_cost / (n_samples × epochs)`, so judge spend can't exceed it. Target (bot) cost is tracked from the bot's reported usage and shown separately.
- No network in unit tests (fake paraphraser, fake responder, mockllm grader).

## Review Focus
1. **Roman `(i)` vs letter `(i)`** in the eCFR parser: `1005.2(i)` is a letter; `1005.11(c)(2)(i)` is roman. → T1 tests both.
2. **Citation typos** like `1005.11(c)(3)(iii)` (doesn't exist) must fail the lint. → T2 test.
3. **A variant drifting from its seed's meaning** (the paraphrase changes the question): the generator keeps the seed's facts, and a test asserts variants copy must_say/must_not_say/citations unchanged. Meaning drift is checked by hand-reviewing the index. → T4.
4. **One judge call failing for one rubric** must not discard the other rubrics' scores for that sample. → T5 test.
5. **Bot without usage info** (older target / third-party URL): target cost becomes NULL, not a crash. → T7 test.

---

### Task 1: Reg E snapshot (eCFR parser + fetch command)
**Files:** `src/examiner/regs/ecfr.py`, `src/examiner/regs/reg_e.json` (generated, committed), `tests/regs/test_ecfr.py`, `tests/regs/fixture_part.xml`
**Produces:** `parse_part(xml: bytes) -> dict[str, str]` mapping paragraph ids (`"1005.11(c)(2)(i)(A)"`) to text. The text of a parent includes only its own P, not its children. `load_reg_e() -> dict` (cached) with keys `{"source", "date", "paragraphs"}`. `reg_text(cite: str) -> str | None` accepts `"12 CFR 1005.6(b)(3)"`. CLI `examiner regs-fetch --date YYYY-MM-DD` rewrites the snapshot.
**Level rule:** markers at the start of a P (one or two, e.g. `(c) Heading—(1) text`). Levels: lowercase letter → 1, digit → 2, roman → 3, uppercase → 4. A token that could be a letter or a roman numeral (`i`, `v`, `x`) is roman if the current deepest level is ≥ 2 (we are under a digit or deeper), else a letter.
- [ ] Tests: fixture with `(h)`, `(i) Financial institution` (a letter, depth 1) and `(c)…(2)…(i)…(A)` → `"X.2(i)"` and `"X.11(c)(2)(i)(A)"` both exist. On the real snapshot: `1005.11(c)(3)(ii)` contains "90 days"; `1005.6(b)(3)` contains "60 days"; `1005.2(i)` starts with "Financial institution".
- [ ] Implement, fetch the snapshot (date 2026-11-17), green, commit.

### Task 2: Schema v2, citation lint, judge sees the regulation text
**Files:** `scenarios/schema.py`, `scenarios/lint.py`, `runner/judge.py`, `store.py`, `cli.py`, `packs/smoke/*.yaml`, tests.
**Changes:** `Scenario.citation: str` becomes `citations: list[str]` (min 1), each either `12 CFR <id>` or `fee:<schedule key>`. Add `seed_id: str | None = None`. Property `citation_display = "; ".join(citations)`, used wherever Phase 1 used `citation` (store, CLI table, labels, scorer metadata).
- `lint_scenario(s) -> list[str]` returns errors; `lint_pack(name)` runs it on all.
- Judge user prompt gets a "Rules cited" block: each citation followed by its paragraph text (reg) or schedule entry (fee).
- [ ] Tests: `test_lint_rejects_unknown_paragraph` (`12 CFR 1005.11(c)(3)(iii)`), `test_lint_rejects_unknown_fee_key`, `test_lint_smoke_pack_clean`, `test_judge_prompt_includes_reg_text` (contains a phrase from 1005.11(c)(2)(i)). Update the Phase 1 tests for the rename.
- [ ] Migrate the smoke pack, green, commit.

### Task 3: Seeds (2.1, 2.2)
**Files:** `packs/v1/seeds/rege-NNN.yaml` (≥ 30), `packs/v1/seeds/fees-NNN.yaml` (≥ 30), `tests/scenarios/test_pack_v1.py`
**Content rules:** Reg E seeds span 1005.6 (liability tiers, 60-day window, extenuating circumstances), 1005.11 (notice window, written confirmation, 10 business days / 45 / 90 / 20 for new accounts, provisional credit, notice of credit, results within 3 business days, debiting provisional credit and the 5-business-day overdraft honor period, documents relied on), 1005.10 (stop payment 3 business days before, notice of varying amounts), 1005.17 (overdraft opt-in for ATM and one-time debit), 1005.33/34 (remittance: 30-minute cancellation, 180-day error notice), 1005.7/9 (statements, receipts). Fee seeds span every schedule entry, including waiver conditions, daily caps, NSF = $0, the overdraft-vs-protection-transfer distinction, and trap questions ("is it $35?"). About 8 multi-turn seeds. Facts use `any_of` alternatives and spelled-out numbers, and avoid ambiguous bare tokens (lessons from the Phase 1 review).
- [ ] Tests: `test_v1_seed_counts` (≥ 30 per area), `test_v1_lint_clean`, `test_v1_unique_ids`, `test_every_seed_has_must_say`, `test_multi_turn_seeds_present` (≥ 6).
- [ ] Write the seeds, green, commit.

### Task 4: Variant generator (2.3)
**Files:** `scenarios/variants.py`, CLI `examiner variants`, `packs/v1/variants/*.yaml` (generated, committed), tests.
**Produces:** `Paraphraser = Callable[[list[str], str], Awaitable[list[str]]]` taking (turns, persona) and returning the rewritten turns. `make_variant(seed, n, persona, turns) -> Scenario` with id `f"{seed.id}--v{n}"` and `seed_id=seed.id`; facts, citations and rubrics are copied unchanged. `is_duplicate(a: list[str], b: list[str]) -> bool` returns true when token Jaccard is > 0.85 on the lowercased joined turns. The CLI picks a persona per seed deterministically (`PERSONAS[hash(seed.id) % len]`), skips files that already exist (stable), and retries once on a duplicate. `load_pack` globs recursively.
- [ ] Tests (fake paraphraser): `test_variant_copies_ground_truth`, `test_variant_id_scheme`, `test_duplicate_detected`, `test_variants_cli_skips_existing`, `test_load_pack_recursive`.
- [ ] Implement, generate with Haiku (cost ≈ cents), hand-skim 10, green, commit. Then `examiner index --pack v1 --out docs/pack-v1.md` (seed table with area, question, citations, and variant count).

### Task 5: Full rubric set, per-rubric scores (2.5)
**Files:** `rubrics/factual.md` (v2: system/user split, full rubric shown verbatim), `rubrics/disclosure.md`, `rubrics/commitments.md`, `runner/judge.py`, `store.py`, `cli.py`, tests.
**Rubrics:** *factual-v2*: same intent as v1. *disclosure-v1*: fail if the reply does not give the key fact(s) the customer asked for (this judge sees `must_say` facts as "key facts"); a hedge or referral without the fact fails. *commitments-v1*: fail if the bot promises an outcome, amount, refund or date that the cited rules don't guarantee, or claims an account-specific action it can't take.
**Produces:** `judge(rubric: str)` scorer factory, one call per rubric. The system message holds the rubric + fee schedule (cached); the user message holds the cited rules + transcript. Scorer name `judge_<rubric>`. A sample runs only the rubrics in `scenario.rubrics` (v1 default: all three). New table `score(run_id, sample_id, epoch, rubric, passed, rationale, judge_version, PRIMARY KEY(run_id, sample_id, epoch, rubric))`. `result.judge_pass` = all rubrics passed (NULL if any grader_failed). `examiner kappa --rubric factual` (default factual) and `label-export --rubric`.
- [ ] Tests: `test_each_rubric_scored_separately`, `test_one_rubric_grader_failed_keeps_others`, `test_disclosure_prompt_includes_key_facts`, `test_factual_prompt_excludes_must_say`, `test_kappa_by_rubric`.
- [ ] Implement, green, commit.

### Task 6: Misinformed bot for seeded failures (2.7)
**Files:** `meridian/app.py`, `meridian/data/misinformed.md`, tests.
**Produces:** variant `misinformed`, whose system prompt confidently states wrong facts: overdraft $35, NSF $29, report within 30 days, provisional credit within 20 business days, investigations up to 60 days, no maintenance fee waiver, and so on. It is used only to make calibration transcripts with real failures; the README labels it as a test fixture.
- [ ] Tests: `test_misinformed_variant_accepted`, `test_misinformed_prompt_contains_wrong_overdraft` (check that the wrong numbers really differ from the schedule).
- [ ] Implement, green, commit.

### Task 7: Run budget, retries, cost tracking, area summary (2.6)
**Files:** `meridian/app.py` (return `usage`), `runner/solver.py`, `store.py`, `cli.py`, tests.
**Produces:** `/chat` returns `{"reply", "variant", "usage": {"input_tokens", "output_tokens"}}`. The solver sums usage into `state.metadata["target_usage"]`. Store column `result.target_cost_usd` (Haiku prices; NULL if no usage). `run.target_cost_usd`, `run.cost_usd` (judge). CLI: `--max-run-cost 5.0` gives the per-sample `cost_limit` above, plus `retry_on_error=2`, `max_samples=8`, and `GenerateConfig(reasoning_effort="medium", max_retries=3)` for the judge. The summary prints pass rates by area × check (fact, each rubric), judge cost, target cost and wall time.
- [ ] Tests: `test_solver_sums_target_usage`, `test_missing_usage_is_null_cost`, `test_per_sample_cap_from_run_cap` (5.0 over 120 samples → 0.041666…), `test_summary_by_area`.
- [ ] Implement, green, commit.

### Task 8: Live v1 runs + close-out
- [ ] `examiner run --pack v1` against `naive`, then `misinformed`. Record wall time, judge + target cost, and pass rate by area and rubric. Check cache reads > 0 in the log's model usage.
- [ ] Done-when checks: < 10 min, ≤ $5, every failure has its citations. Update ROADMAP, STATUS and DECISIONS (D13: rubric set + run numbers).
