# Examiner

**An eval harness that grades a bank's chatbot against the actual regulation text.**

On 127 scenarios citing Regulation E and a fee schedule, a naive bot passes **21.3%**. A guarded version of the same bot passes **92.1%**. Run to run, that's **fixed 93, broke 3**, and the dashboard shows you which ones broke and why.

![Examiner dashboard walkthrough: runs, scorecards, the naive-to-guarded diff, a failing finding with its cited rule, and blind labeling](docs/demo/walkthrough.gif)

| Bot | Overall | Fact check | Factual | Discloses the fact | No invented promises |
|---|---|---|---|---|---|
| Naive (plain system prompt) | 21.3% | 38.6% | 51.2% | 33.9% | 100% |
| Guarded (grounded + rules) | **92.1%** | 96.1% | 96.1% | 100% | 100% |
| Misinformed (deliberately wrong, for calibration) | 0.8% | 16.5% | 5.5% | 18.1% | 57.5% |

Overall = the deterministic fact check AND all three judge rubrics pass. Runs from 2026-11-22, one attempt per scenario. A guarded run takes about 3 minutes and costs $1.76 ($0.014 per scenario, Sonnet 5.5 judge, Haiku 5.5 bot); bot latency is 1.4 s p50 and 4.0 s p95 per conversation.

**Judge agreement with a human is not measured yet.** The 102-item blind calibration batch is built and waiting for labels, so the judge's numbers above are unvalidated. Reading the guarded failures by hand already turned up one judge error (see [What fails](#what-fails)).

**[Live scorecard](https://anaypatel-p.github.io/examiner/)** (read-only snapshot of these runs) · **[Deployment memo](docs/memo.md)**: launch criteria, thresholds, and why the guarded bot isn't cleared yet.

Not legal advice. Meridian Bank is fictional.

## The problem

A bank that ships a chat agent has to know it won't tell a customer the wrong dispute deadline or invent a fee waiver. "It looked fine in testing" doesn't survive a compliance review. You need:

- tests written against the rule itself, not someone's memory of it
- a grader you can audit
- a number for how far that grader can be trusted
- a diff showing what a change fixed and what it broke

Examiner does that for one slice of US banking rules: Reg E (electronic transfers, disputes, liability) and a bank's fee schedule.

## How it works

```
scenario pack ──▶ Inspect runner ──▶ bot over HTTP ──▶ fact checks + LLM judge ──▶ SQLite ──▶ API ──▶ dashboard
 (cited rules)                                         (3 rubrics, budget-capped)                       ▲
                                                                                         human labels ──┘ (kappa)
```

- **Scenarios cite real paragraphs.**
  - 64 hand-written seeds plus 63 persona rewrites (a stressed customer, a non-native speaker, and so on).
  - Each one cites paragraphs like `12 CFR 1005.11(c)(2)(i)` or a fee-schedule entry.
  - The Reg E text is parsed from the official eCFR XML into 837 paragraphs, and a lint fails the build if any citation doesn't resolve.
- **Two kinds of grading.**
  - Deterministic must-say / must-not-say fact checks.
  - An LLM judge with three versioned rubrics:
    - **factual:** nothing false or misleading
    - **disclosure:** actually states the key fact
    - **commitments:** no invented promises
  - The judge reads the cited regulation text itself, not a paraphrase.
- **Runs on [Inspect](https://inspect.aisi.org.uk/)** (the UK AI Security Institute's eval framework). A custom solver drives any bot over HTTP, with retries and a concurrency limit.
- **The judge budget is actually capped.** Inspect's `cost_limit` only covers the solver, so the judge enforces a shared per-run budget itself. Prompt caching keeps judge input cheap (435k cached tokens read against 237k written on one run).
- **Judge calibration.**
  - You label transcripts blind on a keyboard-driven screen.
  - Examiner reports Cohen's kappa per rubric, with the confusion matrix and every disagreement linked.
  - A deliberately misinformed bot supplies real failures, so the label set isn't all passes.

### The dashboard

| Screen | What it shows |
|---|---|
| **Runs** | Every run with pass rates, cost and time |
| **Scorecard** | Pass rate by area and rubric; failures listed with the rule they break |
| **Finding** | Why it failed (judge rationale), the transcript, and the cited Reg E text linked to eCFR |
| **Label** | Blind labeling with the rubric shown word for word; Y / N / S / U keys |
| **Calibration** | Kappa and raw agreement per rubric, the 2x2 table, every disagreement |
| **Diff** | Two runs, one tick per scenario; fixed, broke, still failing, and both transcripts side by side |

## Run it

You need Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 20+, and an Anthropic API key in `.env` (`cp .env.example .env`).

1. Install:
   ```bash
   uv sync && (cd web && npm install)
   ```
2. Start the bot with `make dev` (Meridian on :8001), then in a second terminal do a full run (about 3 minutes, about $1.80):
   ```bash
   uv run examiner run --pack v1 --variant guarded
   ```
3. Open the dashboard at http://localhost:5173:
   ```bash
   make api & make web
   ```

Also useful:

| Command | What it does |
|---|---|
| `examiner diff <runA> <runB>` | Fixed, broke and still failing between two runs |
| `examiner taxonomy <run>` | Failures by Reg E section, clause and failure mode |
| `examiner gate` | Exit 1 if the latest guarded run regressed |
| `examiner label-batch` | Build a mixed pass/fail calibration batch for the Label screen |
| `examiner calibration` | Kappa per rubric from your labels (`--version factual-v2` for an older rubric) |
| `examiner rescore --rubric factual` | Re-judge stored transcripts after a rubric change, without calling the bot |
| `examiner export` then `npm --prefix web run build:static` | The read-only scorecard for GitHub Pages |

All commands run through `uv run` from the repo root.

## What fails

`examiner taxonomy <run>` groups failures by the clause each scenario cites, and by how it failed. The Run page shows the same breakdown.

- **Naive bot (100 of 127 fail).** Mostly it doesn't say the answer: 84 disclosure fails and 77 missing required facts, against 62 factual errors. Fee questions are the worst (57 of 59 fail), because a one-line prompt has no fee schedule. Error resolution under 1005.11 fails 24 of 34.
- **Guarded bot (10 of 127 fail),** read one by one:
  - 5 are fact-check false fails. Four NSF answers correctly say the fee is $0, then mention the $34 overdraft fee, which trips the must-not-say "$34". One correct 1005.10(e)(2) answer misses the expected phrase.
  - 1 is a judge error. The bot says provisional credit for new accounts comes within 20 business days. The judge failed it against the 10 days in 1005.11(c)(2)(i), but 1005.11(c)(3)(i) moves it to 20 for transfers within 30 days of the first deposit. The scenario only cites (c)(2)(i), so the judge never saw the exception.
  - 1 looks real: "will consider extending" where 1005.6(b)(4) says the bank shall extend.
  - 3 are strict readings worth a human call (1005.11(c)(2)(ii), and 1005.10(d)(1) twice).
- **Misinformed bot (126 of 127 fail).** This is the control: it's told wrong facts on purpose, so the rubrics have real failures to catch, including 54 invented commitments.

## Regression gate

`examiner gate` fails a guarded run if its overall pass rate drops below **85%**, or more than **4 points** below the accepted baseline in `gate/baseline.json` (currently 117/127). Both thresholds sit above run-to-run noise: two identical guarded runs once differed on 6 of 127 scenarios. Runs with under 95% of samples scored fail too, so errors or an exhausted judge budget can't pass.

- CI checks the committed baseline on every push.
- The `eval-gate` workflow runs the live guarded pack on PRs that touch the bot, rubrics, runner or packs, once an `ANTHROPIC_API_KEY` repo secret is set (about $2 per run).

## Design decisions

The full log, with the alternatives considered, is in [docs/pm/DECISIONS.md](docs/pm/DECISIONS.md). The ones that shaped it most:

- **Ground truth from the regulation, not paraphrase (D13).** Citations resolve against a parsed eCFR snapshot. The judge sees the paragraph and its sub-paragraphs.
- **Separate rubrics, scored and versioned separately (D13).** "Wrong", "didn't answer" and "promised something" are different failures with different fixes, and each gets its own kappa.
- **The budget lives in the judge (D14).** Found in review: Inspect's cost limit never touched the scorers, so the original $5 cap did nothing.
- **Kleene logic for pass rates (D17).** A definite fail counts as a fail even if another rubric went unjudged, so a judge running out of budget can't quietly raise the pass rate.
- **The guarded bot is grounded the way a real bank would do it (D16).** It uses the bank's fee schedule, FAQ and its Reg E initial disclosure (the one 1005.7 already requires), plus rules against promises and account actions. It doesn't use the test questions.
- **Blind labeling is enforced in code (D20).** The Label screen can only call the label queue and label endpoints, and a test checks that.

## Limits

- **Judge agreement isn't measured yet.**
  - A 20-label spike reached 0.80 raw agreement, but its kappa (0.00) means nothing: every human label was a pass.
  - The full calibration batch (102 items, 34 per rubric, mixed pass and fail across all three bots) is built but not labeled.
  - Until it is, the judge's numbers are unvalidated.
- **The judge only knows what a scenario cites.** An exception elsewhere in the rule reads as an error (rege-012, below).
- **The fact checks have false fails.**
  - 5 of guarded's 10 failures are the string match going wrong, and the judge passed all 5.
  - They're kept as-is so naive and guarded stay comparable (D18).
- **One attempt per scenario.** Two guarded runs differed on 6 scenarios, so a diff of a few scenarios between single-attempt runs is partly noise. More attempts per scenario would fix that, at proportional cost.
- **Narrow scope.** Two areas (Reg E and fees), one fictional bank, English only. Adversarial prompts and escalation are not in v1.
- **The judge and the bot are both Claude models,** so shared blind spots are possible. Calibration against human labels is the check on that.
- **The bot is fictional and the regulation snapshot is dated** (eCFR, 2026-11-17). Nothing here is legal advice.
- **The public scorecard is a snapshot.** `examiner export` freezes the runs into JSON for GitHub Pages; labeling only works in the local app.

## Project docs

PRD, roadmap and phase plans are in [docs/pm/](docs/pm/). The design direction is in [DIRECTION.md](DIRECTION.md). [docs/demo-script.md](docs/demo-script.md) is a narrated walkthrough script.
