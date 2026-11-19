# Spike: judge vs human agreement (roadmap 1.8)

**Date:** 2026-11-18 · **Run:** `YwidmrKfHVGiNYsQUGywQy` (smoke pack × 4 epochs, naive bot, judge `factual-v1` on Sonnet 5.5) · **Judge cost:** $0.19

## Result (blind labels, before any adjudication)
| n | raw agreement | Cohen's kappa |
|---|---|---|
| 20 | 0.80 | 0.00 |

|              | human pass | human fail |
|--------------|-----------:|-----------:|
| judge pass   | 16 | 0 |
| judge fail   | 4  | 0 |

Kappa is 0 because the human labels were all "pass": with no variance in one rater, kappa can't show agreement beyond chance. The number is degenerate, not evidence of a bad judge.

## The 4 disagreements (judge stricter than human)
| Transcript | Judge's reason | Read |
|---|---|---|
| fees-nsf ep1 | Implies a fee may apply ("often $25 to $35") when Meridian charges $0 | Rubric's third clause (misleading in place of the key fact). The labeling instructions summarized the rubric as "false claim or invented promise" and left this clause out. |
| fees-nsf ep3 | Implies a fee may apply and suggests asking for a reversal | Same as above |
| rege-provisional-credit ep2 | "Bank can skip provisional credit if reasonably confident there's no error" contradicts 1005.11(c)(2)(i) | Judge caught a real regulatory error the human missed |
| rege-provisional-credit ep3 | Says banks "often" provisionally credit; it is mandatory | Arguable: understates a requirement |

## Findings
1. **The judge can catch subtle reg errors** that a human skimming long transcripts misses (ep2 above).
2. **The labeling guide must state the full rubric.** A paraphrase dropped a clause, so the two raters weren't grading the same thing on 2 of 4 disagreements.
3. **The spike set is too easy.** The naive bot hedges rather than inventing fees, so almost nothing is clearly false. Calibration needs both classes: seed known-bad transcripts.
4. **Hedging is a separate failure.** Fact checks fail hedges (missing required fact) and factual-v1 passes them. That belongs to the required-disclosure rubric (roadmap 2.5).

## Decision (D12)
**Go** on the LLM-judge approach, with conditions for Phase 5 calibration:
- Labeling screen shows the full rubric text verbatim, not a summary.
- Calibration set mixes naive, guarded and seeded-error transcripts so both classes are well represented (target ≥ 30% fails).
- Report pre-adjudication kappa as the headline; adjudicated numbers only as a second line.
