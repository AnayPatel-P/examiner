# Deployment memo: Meridian guarded chatbot

**Date:** 2026-11-22 · **System:** Meridian Bank customer chatbot, guarded variant (Claude Haiku 5.5) · **Evidence:** Examiner pack v1, runs of 2026-11-22 · **Decision:** not cleared for launch yet (2 of 4 criteria open)

Meridian Bank is fictional. This memo shows how an eval harness like Examiner would feed a launch decision. It is not legal advice.

## Problem

A bank chatbot that answers questions about electronic transfers and fees is a consumer-facing disclosure channel. If it states the wrong dispute deadline, softens a requirement ("we'll consider extending" when Reg E says the bank must), or promises a refund, the bank owns that statement. "It looked fine in testing" isn't evidence a compliance or model risk reviewer can accept. They need tests written against the rule text, a grader they can audit, a measure of how far that grader can be trusted, and a gate that stops a regression from shipping.

## What was tested

- 127 scenarios: 68 on Regulation E (12 CFR 1005: unauthorized-transfer liability, error resolution, preauthorized transfers, overdraft opt-in, remittances) and 59 on the bank's fee schedule. 64 are hand-written; 63 are persona rewrites of them.
- Each scenario cites the paragraph it tests, resolved against an eCFR snapshot (2026-11-17).
- Grading: deterministic must-say / must-not-say fact checks, plus an LLM judge (Claude Sonnet 5.5) on three rubrics: factual accuracy, disclosure of the key fact, and no invented commitments. Overall pass = fact check AND all three rubrics.

## Results (one attempt per scenario)

| Bot | Overall | Fact check | Factual | Disclosure | Commitments |
|---|---|---|---|---|---|
| Naive (one-line prompt) | 21.3% | 38.6% | 51.2% | 33.9% | 100% |
| **Guarded (candidate)** | **92.1%** | 96.1% | 96.1% | 100% | 100% |
| Misinformed (control, wrong on purpose) | 0.8% | 16.5% | 5.5% | 18.1% | 57.5% |

Naive to guarded: 93 scenarios fixed, 3 broke. A full run takes about 3 minutes and costs $1.76 for the guarded bot ($0.014 per scenario). Bot latency per conversation: p50 1.4 s, p95 4.0 s.

**The 10 guarded failures, read one by one:**
- 5 are fact-check false fails: the bot was right and the string match was wrong. Four NSF answers correctly say the NSF fee is $0, then mention the $34 overdraft fee, which trips the must-not-say "$34". One correct answer on 1005.10(e)(2) doesn't contain the expected phrase.
- 5 are judge calls, not yet validated against human labels:
  - **One is a judge error.** The bot says provisional credit for new accounts comes within 20 business days. The judge failed it against the 10 days in 1005.11(c)(2)(i), but 1005.11(c)(3)(i) substitutes 20 business days for transfers within 30 days of the first deposit. The scenario only cites (c)(2)(i), so the judge never saw the exception (rege-012).
  - One looks real: the bot softens the 1005.6(b)(4) duty to extend reporting periods ("shall extend") into "will consider extending" (rege-002--v1).
  - Three are strict readings: "yes, in most cases" for full use of provisional credit (rege-014--v1), and "the notice comes from the payee" where 1005.10(d)(1) allows the payee or the institution (rege-024 and its variant).

## Launch criteria

| # | Criterion | Threshold | Status |
|---|---|---|---|
| 1 | Guarded overall pass rate on pack v1 | at least 85%, and no more than 4 pts below the accepted baseline | **Met**: 92.1%; baseline committed in `gate/baseline.json`, enforced by `examiner gate` and the eval-gate workflow |
| 2 | Judge agreement with a human reviewer, per rubric | Cohen's kappa at least 0.6 on a mixed pass/fail set of about 100 labels | **Open**: the 102-item blind batch is built, labels not yet collected |
| 3 | No confirmed factual error on Reg E error-resolution deadlines (1005.11) | 0 | **Open**: two judge flags; rege-012 is a judge error against the rule text, rege-014--v1 needs human review |
| 4 | No invented commitments (refunds, waivers, account actions) | 0 | **Met** by the judge (127/127), pending the same calibration as #2 |

The 85% floor and the 4-point margin come from noise: two identical guarded runs earlier differed on 6 of 127 scenarios, so smaller drops can't be told apart from chance with one attempt per scenario.

## Residual risk

- **Unvalidated grader.** Until criterion 2 is measured, every judge number above is the judge's opinion. Rege-012 shows one way it goes wrong: the judge only knows the paragraphs a scenario cites, so an exception elsewhere in the rule reads as an error. The judge and the bot are both Claude models, so they can share blind spots that agreement between them would hide.
- **Fact-check noise.** String matching produced half of guarded's failures. It errs toward failing, so it understates the pass rate rather than hiding errors, but it adds review work.
- **Coverage.** Two areas, one fictional bank, English only, single-turn and short multi-turn questions. No adversarial prompts, no prompt injection, no escalation flows.
- **Sampling.** One attempt per scenario. Rare failures (under about 1 in 20) are unlikely to show up.
- **Snapshot drift.** The regulation text is dated 2026-11-17 and the fee schedule is fixed. A rule or fee change needs a pack update before the gate means anything.

## Next steps to clear launch

1. Collect the 102 human labels (`/label?batch=calib-v1`), compute kappa per rubric, and revise any rubric under 0.6, then re-score the stored transcripts offline (`examiner rescore`).
2. Add 1005.11(c)(3) to the citations of the provisional-credit scenarios so the judge sees the new-account exception, re-score, and get a human read on rege-014--v1.
3. Fix the guarded prompt's wording on 1005.6(b)(4) ("must extend", not "will consider") and re-run behind the gate.
4. Fix the two fact-check patterns above (NSF "$34", 1005.10(e)(2) phrasing) and re-score.
