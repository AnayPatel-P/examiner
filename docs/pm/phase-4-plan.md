# Phase 4: Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** the Examiner web app: runs list, run scorecard, finding drill-down, blind labeling, calibration report and run diff, against the real Phase 3 API, built to DIRECTION.md.

**Architecture:** A Vite + React + TypeScript SPA in `web/`. A typed API client (`web/src/api.ts`) mirrors the FastAPI shapes. Pure logic lives in small tested modules: formatting, diff strip model, label keyboard reducer. Screens are routes (react-router). In dev, Vite proxies `/api` to `localhost:8002`. Styling is plain CSS with tokens from DIRECTION.md in `web/src/tokens.css`, with no UI framework. Fonts are self-hosted via @fontsource (Public Sans, Source Serif 4).

**Tech Stack:** Vite 6, React 19, TypeScript 5, react-router 7, Vitest + Testing Library, @fontsource. The design skills are ui-build, ui-verify, dataviz, react-best-practices and web-design-guidelines.

**Spec:** `docs/pm/PRD.md` F5, F6, F7 and §14, `DIRECTION.md`, `docs/pm/ROADMAP.md` Phase 4 (4.0-4.7), the API in `src/examiner/api/app.py`.

## Global Constraints
- The Label screen never fetches or shows judge output (it uses `/api/label-queue` and `POST /api/labels` only).
- Every verdict has a word or icon as well as its colour. Rates use tabular figures and show `n` (e.g. "90.6% · 115/127").
- Workhorse screens get no decorative motion; animation is ≤200 ms and 0 on keyboard. The only signature is the Diff strip wave, 300 ms total, and it respects reduced motion.
- Works at 1440 and 768 widths; every action is keyboard reachable; axe is clean.
- The "Not legal advice. Meridian Bank is fictional." banner shows on every screen.
- `npm run build`, `npm test` and `tsc --noEmit` pass; Python tests are still green.

## Review Focus
1. **Label keyboard races**: pressing Y twice fast must not save two labels or skip an item. → reducer test locks input while a save is in flight.
2. **NULL verdicts** (`null` overall, unscored, errored) render as "Not judged" or "Error", never as Fail. → format test.
3. **API down or empty DB**: every screen shows a stated error or an empty state with the command to run. → test for the client error and states in ui-verify.
4. **Long transcripts and long regulation text** must wrap, with no horizontal overflow at 768. → ui-verify overflow check.
5. **Diff with only_a/only_b and unscored**: the strip shows these as distinct ticks, and the counts add up to the union of samples. → strip model test.

---

### Task 1: Scaffold, tokens, API client (4.1)
**Files:** `web/` (Vite React TS), `web/src/tokens.css`, `web/src/base.css`, `web/src/api.ts`, `web/src/format.ts`, tests, `Makefile` target `web`, `.gitignore` for `web/node_modules` and `web/dist`.
**Produces:**
- Types `RunSummary`, `Cell`, `Scorecard`, `ResultRow`, `ResultDetail`, `QueueItem`, `Calibration`, `Diff`.
- `api.runs()`, `api.run(id)`, `api.results(id, {area, status})`, `api.result(id, sample, epoch)`, `api.labelQueue({rubric, run, limit})`, `api.postLabel(...)`, `api.calibration()`, `api.diff(a, b, check)`. Each throws `ApiError(status, detail)`.
- `format.ts`: `pct(cell)` → "90.6%" or "–"; `verdict(v)` → {word, tone} for 1/0/null/error; `money`, `secs`.
- An app shell with nav (Runs, Label, Calibration, Diff), the banner and the theme toggle.
- [ ] Tests: `api.test.ts` (URL building, ApiError on 404 with detail), `format.test.ts` (null is "Not judged", not Fail; rate with n).
- [ ] Implement, green, commit.

### Task 2: Runs list + run scorecard + results table (4.2)
**Produces:**
- `/` is a runs table: variant, pack, started, overall/fact/judge with a thin bar and n, judge + target cost, wall time. A row click goes to the run.
- `/runs/:id` is a header ("Guarded · v1 pack · 90.6% overall"), a scorecard grid (areas × checks), and a results table with status and area filters synced to the URL query.
- [ ] Tests: `scorecard.test.tsx` renders the "all" row last and "–" for n=0.
- [ ] Implement, green, commit.

### Task 3: Finding drill-down (4.3)
**Produces:** `/runs/:id/results/:sample?epoch=1`.
- A lead line: the first failed rubric's rationale, or the fact-check miss.
- Verdict chips per check.
- The transcript as a record.
- Fact detail (missing and forbidden phrases).
- Rubric rationales.
- Citation blocks: id, display, official text in serif. A Reg E cite links to `https://www.ecfr.gov/current/title-12/part-1005/section-1005.<sec>#p-1005.<sec>(...)`.
- Prev/next finding with J/K.
- [ ] Tests: `ecfrUrl.test.ts` (1005.11(c)(2)(i) → correct anchor; fee cites → no link).
- [ ] Implement, green, commit.

### Task 4: Label screen (4.4)
**Produces:** `/label?rubric=factual&run=`.
- Shows the rubric text verbatim, the citations, the source note, the key facts and the transcript.
- Keys: Y = pass, N = fail, S = skip, U = undo the last label. It shows progress and the count labeled this session.
- Uses a pure reducer `labelReducer(state, action)` with states `idle | saving`, and it ignores keys while saving.
- [ ] Tests: `labelReducer.test.ts` (Y while saving is ignored; skip advances without a save; undo re-queues the last item), plus a test that `Label.tsx` imports nothing from the judge-carrying endpoints.
- [ ] Implement, green, commit.

### Task 5: Calibration report (4.5)
**Produces:** `/calibration` with one panel per rubric:
- kappa (with a plain reading: <0.2 slight, 0.2-0.4 fair, 0.4-0.6 moderate, 0.6-0.8 substantial, >0.8 almost perfect)
- raw agreement, n and n_labels
- a 2×2 confusion matrix (judge × human) with counts
- a disagreement list linking to findings

n=0 shows "No comparable labels yet" plus a link to Label.
- [ ] Tests: `kappaWord.test.ts` (bands, null).
- [ ] Implement, green, commit.

### Task 6: Diff + signature (4.6)
**Produces:** `/diff?a=&b=&check=overall`.
- Run pickers, defaulting to the newest naive vs the newest guarded.
- A headline "Fixed N · Broke M".
- The strip: `stripModel(diff) -> Tick[]` ordered by sample id, each tick `{sample_id, epoch, a, b, category}`.
- The wave runs once per (a, b, check) and is skipped under reduced motion.
- Category lists (broke first). An item or a tick click shows the A and B transcripts side by side (fetched on demand).
- [ ] Tests: `stripModel.test.ts` (counts add up to the union; only_a has b=null; categories match the API).
- [ ] Implement, green, commit.

### Task 7: Verify + close-out (4.7)
- [ ] Run the API on the real DB, then the Vite dev server; run design:ui-verify on all routes at 1440 and 768, light and dark. Fix its findings.
- [ ] Final whole-branch review (subagent), fix Critical/Important.
- [ ] Label 10 transcripts through the UI as the demo check (Anay may do this himself).
- [ ] Update ROADMAP, STATUS, DECISIONS; README "Dashboard" section.
