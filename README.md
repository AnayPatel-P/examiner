# Examiner

Compliance eval harness for banking chatbots: a regulation-grounded scenario pack (Reg E, fees and overdraft), run through Inspect, scored by deterministic fact checks and an LLM judge whose agreement with human labels is measured.

Work in progress. Plan: `docs/pm/`.

```bash
cp .env.example .env   # add ANTHROPIC_API_KEY
uv sync
make dev               # Meridian Bank reference bot on :8001
make smoke             # run the smoke pack
```

Not legal advice. Meridian Bank is fictional.
