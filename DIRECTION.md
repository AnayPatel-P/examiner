# Direction: Examiner

Decided 2026-11-18 by design:ui-direct. Read before deciding: docs/pm/PRD.md, docs/pm/ROADMAP.md, docs/pm/DECISIONS.md (D1-D18), src/examiner/api/app.py (the real endpoints and fields), investedge/DESIGN.md and venturematch/DESIGN.md (for distinctness). No DESIGN.md, PRODUCT.md or frontend existed.

## Brief
- Who: a fintech AI engineer, after every change to the bot (several times a week); a compliance reviewer reading one run's findings occasionally; a hiring manager clicking through once.
- The one job: show which answers broke which rule, and whether the judge saying so can be trusted.
- Mood: exact, sober, trustworthy.
- References: loved Braintrust / LangSmith (runs and scores tables, diff views), Linear (keyboard speed, calm chrome), Stripe docs and dashboard (careful colour, precise numbers), a bank exam report or court filing (findings with citations, serif legal text). Avoided: the category's generic SaaS gray, chatbot-product gradients.

## Concept
No concept: a clean, characterful system.
Why: the strongest candidate, "a run as a bank examination report", comes from the domain (test 1 passes) but makes nothing clearer than a good table plus a well-built finding view (test 2 fails). Its one useful idea, leading each failure with the finding and the rule it breaks, is a voice and layout decision, recorded under Voice. It is also a close cousin of the spec-sheet/catalogue framing in his last three products.
Character comes from:
- **Type:** Public Sans (the US government's typeface, from the regulator's own world) for the interface, and Source Serif 4 for regulation text only, so the law always looks like the law.
- **One signal colour:** deep ledger teal, used with discipline.
- **Voice:** findings first, numbers exact.
- **One detail:** the citation block, which shows the paragraph id as a clickable eCFR reference above the official text, set in serif with a left rule.

## Surface map
| Surface | Route | Tier | Budget here |
|---|---|---|---|
| Runs list | `/` | Workhorse | Feedback and state changes only, ≤200 ms; row hover colour only |
| Run scorecard | `/runs/:id` | Workhorse | Same; the scorecard bars are drawn still, no grow-in |
| Results table (in run page) | `/runs/:id?status=fail` | Workhorse | Filters are instant |
| Finding (result drill-down) | `/runs/:id/results/:sample` | Workhorse | Rubric tabs ≤150 ms, no entrance |
| Label | `/label` | Workhorse | Keyboard actions instant (0 ms); next item swaps with no transition |
| Calibration | `/calibration` | Workhorse | Still |
| Diff | `/diff?a=&b=` | Feature | The signature (below), once per load; lists below it are Workhorse |
| App chrome (nav, run picker, not-legal-advice banner, toasts) | all | Workhorse | Toast 200 ms |

Mix: Workhorse-dominant: 0 Showcase, 1 Feature (Diff), 7 Workhorse.

## Signature moment
On the Diff page, two strips of 127 ticks, one per scenario in pack order, show run A and run B. On load, B's ticks change from A's verdict to their own in a single left-to-right wave (stagger 2 ms per tick, 300 ms total, `--ease-out`). Then the broke ticks (the rare, important ones) get a ring, and the headline count settles at "Fixed 90 · Broke 1". Fixed ticks read as red turning green without a ring. The still state is the two strips with the counts, which is also what reduced-motion users see. Clicking a tick opens that scenario's two transcripts side by side.

## Tokens
- **Theme:** light leads, dark offered (follows the system setting, with a toggle). Compliance reading happens by day, and long transcripts and legal text read best dark-on-light.
- **Colour (light):**
  - signal `ledger #0E5E6F` for links, focus rings, the selected run and the primary action; hover `#0B4C5A`.
  - pass `#1E7A46`, fail `#B3261E`, warning `#A15C07` (unscored, budget hit), info `#2457A6`, neutral or not judged `#6B6A66`.
  - Neutrals are warm paper: bg `#FAF9F6`, surface `#FFFFFF`, rule `#E4E1DA`, muted text `#5E5B55`, ink `#1B1A18`.
  - Dark: bg `#141615`, surface `#1C1F1E`, rule `#2E3231`, ink `#ECEAE4`, muted `#A3A09A`, signal `#5FB3C4`, pass `#5CC08A`, fail `#F07B72`, warning `#E0A04A`.
  - Pass and fail never rely on colour alone: every verdict carries a word or an icon (✓ Pass / ✕ Fail / – Not judged).
- **Type:**
  - Public Sans 400/500/600 for all UI, with tabular figures (`font-variant-numeric: tabular-nums`) on every rate, count, cost and duration.
  - Source Serif 4 400 for cited regulation text and source notes.
  - Transcripts use Public Sans with speaker labels; no mono except ids (`fees-005--v1`, run ids), set in `ui-monospace` at 0.92em.
  - Why: Public Sans carries the regulator register without costume; the serif marks "this is the official text".
  - Sizes: 13 / 14 (body) / 16 / 20 / 28.
- **Spacing:** 4 / 8 / 12 / 16 / 24 / 32 / 48. **Radius:** 4 on inputs, chips and cells; 8 on panels; no pills except status chips.
- **Motion** (mapped to ui-build motion.md §3):
  - `--dur-press` 120 (press row)
  - `--dur-state` 150 (state-change row, Workhorse cap)
  - `--dur-overlay` 200 (modal or toast, Workhorse)
  - `--dur-signature` 300 total (stagger row: Feature, total ≤300)
  - Easings `--ease-out`, `--ease-in-out`, `--ease-drawer` as defined there.

## Voice
- **Register:** dry and exact, like a careful examiner's note. Plain words; no hype, no exclamation marks.
- **Domain nouns** (each picked once and kept):
  - run (not eval, job)
  - scenario (not test case, prompt)
  - finding (a failed result, on the drill-down)
  - rule (the cited paragraph or fee entry)
  - check (fact, judge)
  - rubric (factual, disclosure, commitments)
  - label (a human verdict)
  - agreement and kappa
  - fixed and broke
- **How limits are stated:** "Not legal advice. Meridian Bank is fictional; scenarios test public Reg E rules and a made-up fee schedule." and "Judge agreement is measured on 0 labels for this rubric. Label 20 to get a first kappa."
- **Example lines:**
  - Heading: "Guarded · v1 pack · 90.6% overall".
  - Finding lead: "Stated 10 business days for a new account. The rule allows 20."
  - Button: "Label next (Y / N / S)".
  - Empty state: "No runs yet. Start the bot, then run `examiner run --pack v1`."

## House tics
| Tic | Used? | Why (if used) |
|---|---|---|
| tic-eyebrow | No | Run and scenario ids appear inline in mono, never as uppercase labels above headings |
| tic-numbered-callouts | No | — |
| tic-font-repeat | No | Public Sans and Source Serif 4; neither used in his other products |
| Dark-first | No: light leads, dark offered | Daytime reading of transcripts and legal text |

Swap test: passes. The warm-paper light theme, the teal signal (not orange), the serif legal blocks and the absence of mono eyebrows and condensed display type separate it from InvestEdge, VentureMatch and JARVIS.

## Banned for this product
- No gauges, speedometers or "AI score" dials for pass rates: plain numbers with a thin bar.
- No gavel, scales-of-justice or shield icons, and no bank-vault imagery.
- No chat-bubble styling that makes the bot look like a consumer app. Transcripts are a record: speaker label, then text.
- No motion on any screen except the Diff signature and Workhorse feedback.
- No green/red-only verdicts (always word or icon too); no gradients.
- No judge verdict, rationale or pass-rate anywhere on the Label screen.

## Open questions
- None blocking. The GitHub Pages static export (Phase 5) reuses these screens read-only.

## Revisions
- 2026-11-18: first direction.
- 2026-11-18: signature rings only broke ticks. Ringing all 91 changed ticks hid the one that mattered (seen in ui-verify screenshots).
