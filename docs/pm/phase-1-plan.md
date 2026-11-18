# Phase 1: Walking Skeleton + Judge Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One command runs 5 smoke scenarios against the Meridian Bank bot through Inspect, scores them with deterministic fact checks and a Sonnet judge, and stores results in SQLite. A spike measures judge-vs-human agreement on 20 transcripts.

**Architecture:** The Meridian bot is a separate FastAPI app (`POST /chat`). The Inspect task treats it as an external HTTP target: a custom solver replays each scenario's user turns against the URL and puts the bot's replies into `TaskState.messages`. Two scorers run on the transcript: `fact_check` (no LLM) and `judge` (grader-role model). After eval, the `EvalLog` is indexed into SQLite. The CLI (`examiner`) wraps all three.

**Tech Stack:** Python 3.12, uv, inspect-ai 0.3.291, anthropic 2.10, FastAPI 0.165, Pydantic 2, Typer, SQLite (stdlib), pytest, ruff, pyright.

**Spec:** `docs/pm/PRD.md` (F1, F2, F3, F4, F9) and `docs/pm/ROADMAP.md` Phase 1.

## Global Constraints
- Target model `anthropic/claude-haiku-5-5`; judge model `anthropic/claude-sonnet-5-5` (D9).
- API keys only in `.env` (gitignored); `.env.example` has `ANTHROPIC_API_KEY=` with no value.
- Fictional bank "Meridian Bank" only; public regulation text only; no Wio material (D11).
- Every scenario carries a reg or fee-schedule citation (e.g. `12 CFR 1005.11(c)`, `Meridian fee schedule §overdraft`).
- Judge prompt has a version string (`JUDGE_VERSION = "factual-v1"`) stored on every score.
- Default run cost cap: `--max-cost 1.00` USD for smoke (Inspect `cost_limit`).
- Unit tests make no network calls: the bot takes an injectable responder, Inspect tests use `mockllm/model`.

## Review Focus
1. **Bot is down or returns 500**: the run should mark the sample as errored with a clear message, not crash the whole eval. → test in Task 4 (`test_solver_http_error_marks_sample`).
2. **Fact phrasing variance** ("$34" vs "$34.00" vs "34 dollars"): checks use `any_of` alternatives, case-insensitive, and `$34` must not match inside `$340`. → test in Task 3 (`test_fact_match_boundaries`).
3. **Judge returns unparseable output**: the score should be `INCORRECT` with `reason="grader_failed"` and the raw text kept, not an exception. → test in Task 5.
4. **Multi-turn scenarios**: every user turn is sent with the full history, and the transcript keeps the turn order. → test in Task 4.
5. **Re-indexing the same log twice**: no duplicate rows (upsert on `run.id` and `(run_id, sample_id, epoch)`). → test in Task 6.

---

### Task 1: Repo baseline

**Files:** `pyproject.toml` (already has deps), `Makefile`, `.gitignore`, `.env.example`, `.github/workflows/ci.yml`, `tests/test_smoke_import.py`, `README.md` (stub)

- [ ] Configure ruff (line-length 100, `select = ["E","F","I","UP","B"]`), pyright (`typeCheckingMode = "standard"`, `include=["src","tests"]`), and pytest (`testpaths=["tests"]`) in `pyproject.toml`. Register the CLI: `[project.scripts] examiner = "examiner.cli:app"`.
- [ ] Makefile targets: `dev` (runs the bot on :8001 with uvicorn reload), `test` (`uv run pytest -q`), `lint` (`ruff check` + `ruff format --check` + `pyright`), `smoke` (`examiner run --target http://localhost:8001 --pack smoke`).
- [ ] `.gitignore`: `.env`, `.venv/`, `logs/`, `*.db`, `__pycache__/`, `.pytest_cache/`.
- [ ] CI on push: checkout, `astral-sh/setup-uv`, `uv sync`, `make lint`, `make test`.
- [ ] `tests/test_smoke_import.py`: `import examiner` works. Run `make lint test` until green.
- [ ] Commit `chore: repo baseline`.

### Task 2: Meridian Bank data + `POST /chat` (naive)

**Files:** `src/examiner/meridian/data/fee_schedule.json`, `src/examiner/meridian/data/faq.md`, `src/examiner/meridian/bank.py`, `src/examiner/meridian/app.py`, `tests/meridian/test_app.py`

**Interfaces (produces):**
- `load_fee_schedule() -> dict` and `load_faq() -> str` in `bank.py`.
- `Responder = Callable[[str, list[dict]], Awaitable[str]]`, called with (system_prompt, messages).
- `create_app(responder: Responder | None = None) -> FastAPI`. Default responder: AsyncAnthropic, model `claude-haiku-5-5`, max_tokens 600.
- `POST /chat` body `{"variant": "naive", "messages": [{"role": "user"|"assistant", "content": str}]}` returns `{"reply": str, "variant": str}`. `variant` other than `naive` returns 422 for now (guarded comes in Phase 3). Empty `messages`, or a last message that isn't a user message, returns 422.
- `GET /health` returns `{"ok": true}`.
- Module-level `app = create_app()` for uvicorn.

Fee schedule values (fictional; scenarios depend on them): overdraft fee $34 per item, max 3 per day; NSF fee $0 (Meridian eliminated it); overdraft protection transfer $12; monthly maintenance $12, waived with $1,500 daily balance or $500 direct deposit; out-of-network ATM $3.00; stop payment $30; wire domestic outgoing $25; card replacement $0 standard / $25 expedited. The FAQ covers the dispute process in plain words: report within 60 days of the statement, provisional credit within 10 business days, investigation up to 45 days.

Naive system prompt: "You are Meridian Bank's helpful assistant. Answer customer questions." (deliberately ungrounded).

- [ ] Tests (with a fake responder, using FastAPI TestClient): `test_chat_returns_reply`, `test_chat_passes_history_in_order`, `test_chat_rejects_unknown_variant` (422), `test_chat_rejects_empty_messages` (422), `test_health`, and `test_fee_schedule_has_overdraft_34`.
- [ ] Implement, run tests green, then commit `feat: Meridian naive bot`.

### Task 3: Scenario schema, fact matcher, 5 smoke scenarios

**Files:** `src/examiner/scenarios/schema.py`, `src/examiner/scenarios/facts.py`, `packs/smoke/*.yaml`, `tests/scenarios/test_schema.py`, `tests/scenarios/test_facts.py`

**Interfaces (produces):**
- `Fact(BaseModel)`: `id: str`, `any_of: list[str]` (min 1), `note: str = ""`.
- `Scenario(BaseModel)`: `id: str` (pattern `^[a-z0-9-]+$`), `area: Literal["reg_e","fees"]`, `persona: str`, `turns: list[str]` (min 1, user messages), `must_say: list[Fact]`, `must_not_say: list[Fact]`, `rubrics: list[str]` (default `["factual"]`), `citation: str` (non-empty), `source_note: str`.
- `load_pack(name: str, root: Path = PACKS_DIR) -> list[Scenario]`: reads `packs/<name>/*.yaml` sorted by filename, raises `ValueError` on duplicate ids.
- `fact_present(fact: Fact, text: str) -> bool`: case-insensitive. Each alternative is escaped literally and wrapped in boundaries `(?<![\w$.])` … `(?![\w.]?\d)`, so `$34` doesn't match `$340` but does match `$34.` at the end of a sentence.
- `check_facts(scenario: Scenario, transcript: str) -> FactResult` with `missing: list[str]` (must_say ids not present), `forbidden: list[str]` (must_not_say ids present), and `passed: bool`.

Smoke scenarios, one YAML file each:
1. `fees-overdraft-amount`: "What's your overdraft fee?" must_say `$34`; must_not_say `$35`, `$25`, `$36`; citation `Meridian fee schedule: overdraft`.
2. `fees-nsf`: "If a check bounces do you charge an NSF fee?" must_say any_of `["no NSF fee","don't charge an NSF","do not charge an NSF","$0"]`; must_not_say `["$34 NSF", "$35"]`; citation fee schedule NSF.
3. `rege-unauthorized-report-window`: "Someone used my debit card without permission, how long do I have to report it?" must_say `["60 days"]`; citation `12 CFR 1005.6(b)(3)`.
4. `rege-provisional-credit`: 2 turns: "I found an error on my statement and reported it." then "When will I get my money back while you investigate?" must_say `["10 business days"]`; must_not_say `["immediately","right away"]`; citation `12 CFR 1005.11(c)(2)`.
5. `rege-investigation-time`: "How long can the bank take to investigate a disputed transaction?" must_say `["45 days"]`; citation `12 CFR 1005.11(c)(3)`.

Each scenario has a `source_note` explaining the rule in one plain-English line.

- [ ] Tests: `test_load_smoke_pack_has_5`, `test_duplicate_ids_rejected`, `test_scenario_requires_citation`, `test_fact_match_boundaries` (`$34` matches "fee is $34." and "$34.00" but not "$340"; case-insensitive "60 Days"), `test_check_facts_missing_and_forbidden`.
- [ ] Implement, run green, commit `feat: scenario schema and smoke pack`.

### Task 4: Inspect task + HTTP target solver + fact scorer

**Files:** `src/examiner/runner/solver.py`, `src/examiner/runner/scorers.py`, `src/examiner/runner/task.py`, `tests/runner/test_solver.py`, `tests/runner/test_task.py`

**Interfaces:**
- Consumes `Scenario` and `load_pack`/`check_facts` from Task 3.
- `scenario_to_sample(s: Scenario) -> Sample`: `id=s.id`, `input=s.turns[0]`, `metadata={"scenario": s.model_dump()}`.
- `@solver http_target(url: str, variant: str = "naive", timeout: float = 60.0)`: for each turn in `metadata["scenario"]["turns"]`, append a `ChatMessageUser`, POST the history to `{url}/chat` with httpx.AsyncClient, append a `ChatMessageAssistant(content=reply)`, and set `state.output = ModelOutput.from_content("meridian/" + variant, reply)` after the final turn. On an HTTP error or connection failure, raise `RuntimeError(f"target error: ...")` so Inspect records a sample error. The eval uses `fail_on_error=False`, so the run continues.
- `transcript_text(messages) -> str`: lines of the form `USER: …` / `BOT: …`.
- `@scorer(metrics=[accuracy()]) fact_check()` returns a `Score` with value `CORRECT`/`INCORRECT`, `explanation` listing the missing/forbidden fact ids, and `metadata={"missing": [...], "forbidden": [...], "citation": ...}`. It checks only assistant text.
- `@task examiner_task(pack: str = "smoke", target: str = "http://localhost:8001", variant: str = "naive") -> Task` with dataset `MemoryDataset([scenario_to_sample(s) for s in load_pack(pack)])`, solver `http_target(target, variant)`, and scorers `[fact_check(), judge()]` (judge from Task 5; Task 4 ships with `[fact_check()]` and Task 5 adds judge).

- [ ] Tests run the solver against a local FastAPI app on a background uvicorn server (pytest fixture on a free port) wrapping `create_app(fake_responder)`, plus `inspect_ai.eval(..., model="mockllm/model", display="none", log_dir=tmp_path)`:
  - `test_solver_multi_turn_order`: the 2-turn scenario produces messages [user, assistant, user, assistant], and the fake responder saw 3 messages on the second call.
  - `test_fact_check_scores_end_to_end`: a fake responder that always says "Our overdraft fee is $34." passes `fees-overdraft-amount` and fails `rege-investigation-time`.
  - `test_solver_http_error_marks_sample`: target URL on a closed port gives a log with `status` of `"success"` or `"error"`, where the sample has `error` set and the eval doesn't raise.
- [ ] Implement, run green, commit `feat: Inspect HTTP target runner with fact scorer`.

### Task 5: Sonnet judge scorer (factual rubric)

**Files:** `src/examiner/runner/judge.py`, `src/examiner/rubrics/factual.md`, `tests/runner/test_judge.py`

**Interfaces:**
- `JUDGE_VERSION = "factual-v1"`.
- `build_judge_prompt(scenario: dict, transcript: str) -> str` uses `rubrics/factual.md`. The judge sees the Meridian fee schedule JSON, the scenario's `source_note` and `citation`, and the transcript. It must not see must_say/must_not_say. That keeps the judge independent of the deterministic checks so the spike measures the judge on its own.
- The judge outputs JSON: `{"verdict": "pass"|"fail", "rationale": str}`.
- `parse_verdict(text: str) -> tuple[str, str] | None` finds the first `{...}` block. It returns None if the block is invalid or the verdict isn't pass/fail.
- `@scorer(metrics=[accuracy()]) judge()`: `get_model(role="grader")`, `generate(prompt)`, and a `Score` with `metadata={"judge_version", "rationale", "rubric": "factual", "citation"}`. On a parse failure it returns `INCORRECT`, `reason="grader_failed"`, with the raw text in `explanation`.
- Wire it into `examiner_task` scorers.

Rubric text (factual-v1): fail if the bot states a fee amount, deadline, or timeline that contradicts the fee schedule or the cited rule, or invents a commitment (a refund promise, a specific date) not supported by them. Pass if every factual claim is consistent; hedging or referring to a human is a pass unless it states something wrong.

- [ ] Tests use `mockllm/model` for the grader role via `model_roles={"grader": get_model("mockllm/model", custom_outputs=[ModelOutput.from_content("mockllm/model", '{"verdict":"fail","rationale":"x"}')...])}`:
  - `test_parse_verdict_ok`, `test_parse_verdict_garbage_returns_none`.
  - `test_judge_prompt_excludes_must_say` (a must_say string unique to the test scenario isn't in the prompt).
  - `test_judge_score_end_to_end_fail` and `test_judge_unparseable_is_grader_failed`.
- [ ] Implement, run green, commit `feat: Sonnet judge scorer (factual-v1)`.

### Task 6: SQLite index + `examiner run` CLI

**Files:** `src/examiner/store.py`, `src/examiner/cli.py`, `tests/test_store.py`, `tests/test_cli.py`

**Interfaces:**
- `Store(path: Path = Path("examiner.db"))` creates its tables on init:
  - `run(id TEXT PK, target, variant, pack, judge_version, model_target, model_judge, started_at, cost_usd REAL, log_path)`.
  - `result(run_id, sample_id, epoch INT, transcript TEXT, fact_pass INT, fact_detail JSON, judge_pass INT, judge_rationale TEXT, citation TEXT, error TEXT, PRIMARY KEY(run_id, sample_id, epoch))`.
- `Store.index_log(log: EvalLog, target: str, variant: str) -> str` returns run_id (`log.eval.eval_id`) and upserts. Cost comes from `log.stats` model usage when available, else NULL.
- `Store.results(run_id) -> list[sqlite3.Row]`.
- CLI: `examiner run --target URL --pack NAME [--variant naive] [--epochs 1] [--max-cost 1.0] [--db examiner.db]`. It loads `.env` (python-dotenv), calls `inspect_ai.eval(examiner_task(...), model="none/none" if supported else the target model id for logging, model_roles={"grader": "anthropic/claude-sonnet-5-5"}, epochs, cost_limit=max_cost, log_dir="logs", fail_on_error=False, max_samples=8)`, indexes the log, and prints a table: `scenario | fact | judge | citation`, plus a summary line `fact x/5 · judge y/5 · cost $z`. It exits non-zero only on a setup error, not on scenario failures.

- [ ] Tests: `test_index_log_upsert_no_duplicates` (index the same log twice and get the same row count, using a real log produced with mockllm in a fixture), `test_index_records_error_samples`, `test_cli_run_prints_table` (Typer CliRunner against the fixture bot + mockllm grader via an env/flag override `--judge-model mockllm/model`).
- [ ] Implement, run green, commit `feat: SQLite index and examiner run CLI`.

### Task 7: Live smoke run (needs `ANTHROPIC_API_KEY`)

- [ ] `make dev` in the background, then `make smoke`. Expected: a 5-row table, a run row in `examiner.db`, and cost < $0.25.
- [ ] If the key is missing, stop here and report. Everything up to this point is verified offline.

### Task 8: Judge spike (20 transcripts)

**Files:** `src/examiner/calibration.py`, `tests/test_calibration.py`, CLI commands `examiner label-export` / `examiner kappa`, `docs/pm/spike-judge.md`

**Interfaces:**
- `cohen_kappa(a: list[bool], b: list[bool]) -> float`. If both raters are constant and agree, return 1.0. If p_e == 1 otherwise, return 0.0.
- `examiner label-export --run RUN_ID --out spike/labels.csv`: columns `sample_id, epoch, transcript, citation, source_note, human_pass` (blank), without the judge verdict (blind).
- `examiner kappa --run RUN_ID --labels spike/labels.csv` prints n, raw agreement, kappa, and the confusion counts.
- Spike data: `examiner run --pack smoke --epochs 4` (20 transcripts). Anay fills `human_pass` with y/n.

- [ ] Tests: `test_kappa_known_values` (`a=[T,T,F,F]`, `b=[T,F,F,F]` gives 0.5), `test_kappa_perfect`, `test_kappa_degenerate`, `test_label_export_hides_judge`.
- [ ] Implement, run green, commit `feat: kappa + labeling export for judge spike`.
- [ ] After Anay labels: run kappa, write `spike-judge.md` (n, agreement, kappa, disagreements, go/no-go), and add D12 to DECISIONS.md.
