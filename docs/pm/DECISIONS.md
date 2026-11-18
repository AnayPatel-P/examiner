# Decisions log

| # | Date | Decision | Why | Alternatives considered |
|---|------|----------|-----|-------------------------|
| D1 | 2026-11-18 | Build Examiner (picked with Abroad from a lightbulb shortlist); Examiner first | Shorter build, purest eval/MLE story, lines up with the Wio chat agent work | DisputeKit, Lapse, PriceSync, RateCon |
| D2 | 2026-11-18 | Primary user: fintech AI engineer; compliance reviewer secondary | Engineers run it on every change; the report still has to read well for compliance | Compliance-first report tool |
| D3 | 2026-11-18 | Demo target: fictional "Meridian Bank" bot, naive + guarded | Controlled ground truth and a real before/after; no real bank data | Open-source bank bots, raw-model targets only |
| D4 | 2026-11-18 | Form factor: web app dashboard | Demoable, and frontend practice (a known weak spot) | CLI + static HTML, CLI only |
| D5 | 2026-11-18 | v1 scenario areas: Reg E disputes/errors + fees/overdraft | Checkable ground truth (reg text, fee schedule) | Adversarial, escalation → v1.1 |
| D6 | 2026-11-18 | Judge calibrated on ~100 hand labels from a blind labeling screen; report Cohen's kappa | Most credible way to trust the judge; best interview story | Seeded truth only; seeded + 50 labels |
| D7 | 2026-11-18 | Runner: Inspect (inspect_ai) | Used by AI labs and AISI; learning it is a direct signal | Own runner, Promptfoo |
| D8 | 2026-11-18 | Adopted: reg citation per failure, run-vs-run diff | Compliance readability + the engineer's main need | Disagreement explorer, model leaderboard → backlog |
| D9 | 2026-11-18 | Defaults: no auth, must_say/must_not_say facts, seed+variant generation, Haiku target + Sonnet judge + caching + budget cap, "not legal advice" banner | Keeps v1 to 2-3 weeks and runs to ≤ $5 | — |
| D10 | 2026-11-18 | Stack: Python 3.12 (uv) + FastAPI + Inspect + SQLite; React + Vite + TS dashboard; static export to GitHub Pages | Python for eval work (his strength); a light SPA is enough for a single-user local tool | Next.js UI; Streamlit |
| D11 | 2026-11-18 | Public material only; no Wio data | Wio material stays off the personal Mac | — |
