# Examiner — PRD

_Version 1.0 · 2026-11-18 · Status: Draft_

## 1. Vision
Teams shipping LLM chatbots in banking can find out, before customers or regulators do, where their bot misstates fees or mishandles a Reg E dispute. They can trust that answer because the judge's agreement with a human reviewer is measured, not assumed.

**One-liner:** Examiner helps fintech AI engineers catch compliance failures in their banking chatbots by running a regulation-grounded scenario pack scored by a calibrated LLM judge, unlike generic eval tools, which ship no banking scenarios and rarely show how reliable their judge is.

## 2. Problem
- **Who has it:** engineers at banks, credit unions and fintechs building customer-facing chat agents.
- **What they do today:** spot-check transcripts by hand, or run generic red-team tools (Promptfoo, Giskard, Patronus) with no banking-specific scenarios or ground truth.
- **Why that's painful:** the CFPB has said chatbot answers must comply with consumer finance law (2023 Issue Spotlight). Wrong fee amounts or wrong error-resolution timelines are UDAAP and Reg E exposure, and teams can't tell whether a prompt change made things better or worse.

## 3. Target users
| Persona | Description | Key need |
|---------|-------------|----------|
| AI engineer (primary) | Builds/maintains the bank's chat agent | Run the suite on every change, see what regressed, see failing transcripts |
| Compliance reviewer (secondary) | Signs off on the bot | A readable scorecard where each failure cites the rule it breaks |
| Hiring manager (portfolio) | Reviews Anay's GitHub/demo | Sees real evals, a calibrated judge, honest limitations |

## 4. Goals and non-goals
**Goals (v1):**
- A reproducible suite of ~120 Reg E and fees/overdraft scenarios with explicit ground truth.
- A judge whose agreement with human labels is reported (Cohen's kappa, per rubric).
- A visible before/after: naive vs guarded Meridian Bank bot.
- A dashboard to browse runs, drill into failures, label transcripts and diff two runs.

**Non-goals (v1):**
- Auth, multi-tenant or hosted SaaS.
- Adversarial/jailbreak and escalation/doom-loop packs (v1.1).
- Legal advice. Scenarios are interpretations of public regulation text, labeled as such.
- Any Wio material. Public sources only.

## 5. Features (MoSCoW)
| # | Feature | Priority | Notes |
|---|---------|----------|-------|
| F1 | Meridian Bank reference bot (naive + guarded) over HTTP | Must | Fictional fee schedule + FAQ; Haiku 5.5 |
| F2 | Scenario pack: ~30 seeds/area × variants, Reg E + fees/overdraft, with must_say / must_not_say facts and reg citations | Must | YAML/JSON, versioned |
| F3 | Inspect-based runner against any HTTP chat target | Must | Multi-turn where needed |
| F4 | LLM judge (Sonnet 5.5) with per-rubric scoring + fact checks | Must | Rubrics: factual accuracy, required disclosure, no invented commitments |
| F5 | Labeling screen + calibration report (kappa per rubric) | Must | ~100 human labels, blind to judge score |
| F6 | Dashboard: runs list, scorecard, failure drill-down with transcript + citation | Must | React/Vite |
| F7 | Run-vs-run regression diff | Should | "Fixed 9, broke 2" + transcripts |
| F8 | Static scorecard export (GitHub Pages) | Should | Public demo without API keys |
| F9 | Budget cap + prompt caching | Must | A full run costs a few dollars |
| F10 | Judge disagreement explorer | Could | v1.1 |
| F11 | Base-model leaderboard | Won't (v1) | Future add-on |
| F12 | Adversarial + escalation packs, CI gate (GitHub Action) | Won't (v1) | v1.1 |

_v1 = all Musts + F7 (one Should). F8 is pulled in only if Phase 5 has room; otherwise it ships as v1.1._

## 6. User stories and acceptance criteria
### F1 — Meridian Bank bot
- **As an** engineer **I want** a realistic target bot in two versions **so that** the suite shows a real before/after.
- **Done when:**
  - [ ] `POST /chat` accepts a message history and returns a reply, for `variant=naive|guarded`.
  - [ ] Guarded uses the fee schedule + FAQ as grounding and refuses to invent fees or commitments; naive is a plain system prompt.
  - [ ] Fee schedule and FAQ are fictional, stored as data files, and cited by scenarios.

### F2 — Scenario pack
- **As an** engineer **I want** scenarios with explicit ground truth **so that** scores aren't vibes.
- **Done when:**
  - [ ] Each scenario has: id, area, persona, turns, must_say, must_not_say, rubric ids, reg citation (e.g. 12 CFR 1005.11(c)), source note.
  - [ ] ≥ 30 seeds per area; variant generator produces paraphrase/persona variants with a stable id scheme (~120 total).
  - [ ] Schema validated by tests; a human-readable index is generated.

### F3 — Runner
- **Done when:**
  - [ ] `examiner run --target <url> --pack v1` executes all scenarios through Inspect and writes logs.
  - [ ] Results are indexed into SQLite (run, scenario, transcript, scores, cost).
  - [ ] Retries, concurrency limit and a budget cap that aborts cleanly.

### F4 — Judge
- **Done when:**
  - [ ] Per-rubric pass/fail + short rationale, plus deterministic checks for must_say/must_not_say facts.
  - [ ] Every failure records the citation it breaks.
  - [ ] Judge prompt and rubric are versioned; the version is stored on each score.

### F5 — Labeling + calibration
- **As** the reviewer **I want** to label transcripts blind **so that** the judge's reliability is measured.
- **Done when:**
  - [ ] Labeling screen shows the transcript + rubric, hides the judge score, saves labels with keyboard shortcuts.
  - [ ] Calibration report: Cohen's kappa and raw agreement per rubric, with confusion counts, on ≥ 100 labels.
  - [ ] At least one rubric revision logged, with kappa before/after.

### F6 — Dashboard
- **Done when:**
  - [ ] Runs list (target, variant, date, pass rate, cost).
  - [ ] Scorecard by area and rubric.
  - [ ] Failure drill-down: transcript, judge rationale, failed facts, reg citation.
  - [ ] Works at laptop and tablet widths; keyboard navigable.

### F7 — Regression diff
- **Done when:**
  - [ ] Pick two runs → lists fixed / broke / unchanged-fail with links to both transcripts.

## 7. User flow
1. Engineer starts the Meridian bot (`naive`) and runs `examiner run`.
2. Opens the dashboard → sees the scorecard → drills into failures (e.g. "stated a $25 overdraft fee; schedule says $34", citation shown).
3. Labels 100 transcripts on the labeling screen → calibration report shows judge kappa per rubric.
4. Switches the target to `guarded`, reruns, opens the diff: "fixed 31, broke 3."
5. Exports the static scorecard for the README/demo.

## 8. Non-functional requirements
- **Performance:** a full 120-scenario run in < 10 min with concurrency ≤ 8.
- **Platforms:** local macOS; static export works on GitHub Pages.
- **Privacy/security:** API keys only in `.env` (never committed); no real customer data; fictional bank.
- **Accessibility:** keyboard navigation, readable contrast, no color-only pass/fail.
- **Cost:** ≤ $5 per full run (Haiku target, Sonnet judge, caching); hard budget cap.

## 9. Tech approach (summary)
Python 3.12 + uv · Inspect (inspect_ai) runner with a custom HTTP target solver and model-graded + deterministic scorers · Anthropic SDK (Haiku 5.5 target, Sonnet 5.5 judge) · FastAPI serving runs/labels from SQLite · React + Vite + TypeScript dashboard (style set by ui-direct) · static export = Vite build over a JSON snapshot. Details in DECISIONS.md.

**Data model sketch:** `scenario(id, area, seed_id, persona, turns, must_say[], must_not_say[], rubrics[], citation)` · `run(id, target, variant, pack_version, judge_version, started_at, cost)` · `result(run_id, scenario_id, transcript, rubric_scores{}, fact_checks{}, passed)` · `label(scenario_id, run_id, rubric, human_pass, note, labeled_at)`.

## 10. Success metrics
| Metric | Target | How measured |
|--------|--------|--------------|
| Judge agreement | kappa ≥ 0.6 on each rubric (or documented why not) | Calibration report on ≥ 100 labels |
| Before/after | Guarded beats naive by ≥ 20 pts overall pass rate | Run diff |
| Cost | ≤ $5 per full run | Run cost column |
| Demo | 60-second video + public scorecard + README case study | Exists and links work |

## 11. Risks and assumptions
| Risk / assumption | Impact | Likelihood | Mitigation / how we test it early |
|-------------------|--------|------------|-----------------------------------|
| LLM judge can't reach useful agreement on judgment rubrics | High | Med | Phase 1 spike: 20 transcripts, label, measure. Fall back to more deterministic fact checks |
| Inspect is awkward for an external multi-turn HTTP target | Med | Med | Phase 1 spike: custom solver against the Meridian endpoint |
| Reg E scenarios misread the regulation | Med | Med | Each scenario cites the exact section + plain-English source note; "not legal advice" banner; limitations in README |
| Naive vs guarded gap too small to be interesting | Low | Low | Pick fee/timeline facts a naive bot will plausibly invent |
| Frontend takes longer than planned (weak area) | Med | Med | ui-direct sets a tight direction; dashboard screens kept to 5 |

## 12. Open questions
- [ ] Is the 2023 CFPB chatbot spotlight still current? Check before writing the README framing.
- [ ] Multi-turn scenarios: how many in v1 (Reg E disputes often need 2-3 turns)?

## 13. Future add-ons (backlog)
| Idea | Why it's valuable | Size | Suggested version |
|------|-------------------|------|-------------------|
| Judge disagreement explorer | Strongest MLE story: fix rubric, show kappa lift | M | v1.1 |
| Adversarial/jailbreak pack | Promises refunds, investment advice, data leaks | M | v1.1 |
| Escalation / doom-loop pack | The CFPB's headline complaint | M | v1.1 |
| CI gate (GitHub Action) | Fail the PR if pass rate drops | S | v1.1 |
| Base-model leaderboard | Blog/LinkedIn reach | M | v1.2 |
| More regs (Reg Z credit cards, FCRA disputes) | Breadth for a real buyer | L | v2 |

## 14. Design
Direction: `DIRECTION.md` (ui-direct, 2026-11-18). No concept: a clean, characterful system. Character from Public Sans UI + Source Serif 4 for regulation text, one ledger-teal signal (#0E5E6F), a dry "findings first" voice, and the citation block. Light leads, dark offered. Workhorse-dominant (7 Workhorse, 1 Feature). Signature: the Diff page's two 127-tick strips, where run B's ticks flip from A's verdicts in one 300 ms wave and settle on "Fixed N · Broke M".
