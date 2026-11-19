# Examiner

Compliance eval harness for banking chatbots: a regulation-grounded scenario pack (Reg E, fees and overdraft), run through Inspect, scored by deterministic fact checks and an LLM judge whose agreement with human labels is measured.

Work in progress. Plan: `docs/pm/`.

```bash
cp .env.example .env   # add ANTHROPIC_API_KEY
uv sync
make dev               # Meridian Bank reference bot on :8001
make smoke             # run the smoke pack
uv run examiner run --pack v1 --variant guarded   # full pack (~3 min, ~$2)
```

## Dashboard

```bash
make api               # read API on :8002 (examiner serve)
cd web && npm install && cd ..
make web               # dashboard on http://localhost:5173
```

Screens: runs, run scorecard, finding drill-down (transcript, judge rationale, cited Reg E text), blind labeling (keys Y / N / S / U), calibration (Cohen's kappa per rubric), and run diff. Design direction: `DIRECTION.md`.

Not legal advice. Meridian Bank is fictional.
