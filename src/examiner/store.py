"""SQLite index of Inspect eval logs."""

import json
import sqlite3
from pathlib import Path

from inspect_ai.log import EvalLog

from examiner.runner.solver import transcript_text
from examiner.scenarios.schema import display_citation

SCHEMA = """
CREATE TABLE IF NOT EXISTS run (
    id TEXT PRIMARY KEY,
    target TEXT, variant TEXT, pack TEXT, judge_version TEXT,
    model_target TEXT, model_judge TEXT, started_at TEXT,
    cost_usd REAL, log_path TEXT
);
CREATE TABLE IF NOT EXISTS result (
    run_id TEXT NOT NULL REFERENCES run(id),
    sample_id TEXT NOT NULL,
    epoch INTEGER NOT NULL,
    transcript TEXT,
    fact_pass INTEGER, fact_detail TEXT,
    judge_pass INTEGER, judge_rationale TEXT,
    citation TEXT, error TEXT,
    PRIMARY KEY (run_id, sample_id, epoch)
);
CREATE TABLE IF NOT EXISTS score (
    run_id TEXT NOT NULL REFERENCES run(id),
    sample_id TEXT NOT NULL,
    epoch INTEGER NOT NULL,
    rubric TEXT NOT NULL,
    passed INTEGER,
    rationale TEXT,
    judge_version TEXT,
    PRIMARY KEY (run_id, sample_id, epoch, rubric)
);
"""

TARGET_MODEL = "anthropic/claude-haiku-5-5"
# Haiku 5.5 list price, USD per million tokens (input, output).
TARGET_PRICE = (0.10, 0.50)

# Columns added after the first schema; added to old databases on open.
MIGRATIONS = {
    "run": {"target_cost_usd": "REAL", "wall_seconds": "REAL"},
    "result": {"target_cost_usd": "REAL"},
}


def target_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * TARGET_PRICE[0] + output_tokens * TARGET_PRICE[1]) / 1_000_000


def _passed(value: object) -> int | None:
    return None if value is None else int(value == "C")


class Store:
    def __init__(self, path: Path = Path("examiner.db")):
        self.path = Path(path)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        for table, cols in MIGRATIONS.items():
            have = {r["name"] for r in self.db.execute(f"PRAGMA table_info({table})")}
            for col, typ in cols.items():
                if col not in have:
                    self.db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")

    def index_log(self, log: EvalLog, target: str, variant: str) -> str:
        spec = log.eval
        run_id = spec.eval_id
        roles = spec.model_roles or {}
        grader = roles.get("grader")
        if isinstance(grader, list):
            grader = grader[0] if grader else None
        judge_model = grader.model if grader else None
        costs = [u.total_cost for u in (log.stats.model_usage or {}).values()]
        cost = sum(c for c in costs if c is not None) if any(c is not None for c in costs) else None
        versions: set[str] = set()
        rows = []
        score_rows = []
        for s in log.samples or []:
            scores = s.scores or {}
            fact = scores.get("fact_check")
            cites = s.metadata.get("scenario", {}).get("citations") or []
            citation = "; ".join(display_citation(c) for c in cites) or None
            verdicts: list[int | None] = []
            notes: list[str] = []
            for key, sc in scores.items():
                meta = sc.metadata or {}
                if not key.startswith("judge_") or meta.get("skipped"):
                    continue
                rubric = key.removeprefix("judge_")
                failed = sc.reason == "grader_failed"
                passed = None if failed else _passed(sc.value)
                rationale = f"grader_failed: {sc.explanation}" if failed else sc.explanation
                version = meta.get("judge_version")
                if version:
                    versions.add(version)
                verdicts.append(passed)
                notes.append(f"[{rubric}] {rationale}")
                score_rows.append((run_id, str(s.id), s.epoch, rubric, passed, rationale, version))
            tu = s.metadata.get("target_usage")
            tcost = target_cost(tu["input_tokens"], tu["output_tokens"]) if tu else None
            if not verdicts or any(v is None for v in verdicts):
                judge_pass = None
            else:
                judge_pass = int(all(verdicts))
            rows.append(
                (
                    run_id,
                    str(s.id),
                    s.epoch,
                    transcript_text(s.messages),
                    _passed(fact.value) if fact else None,
                    json.dumps(fact.metadata) if fact else None,
                    judge_pass,
                    "\n".join(notes) or None,
                    citation,
                    s.error.message if s.error else None,
                    tcost,
                )
            )
        judge_version = ",".join(sorted(versions)) or None
        tcosts = [r[-1] for r in rows if r[-1] is not None]
        run_target_cost = sum(tcosts) if tcosts else None
        wall = None
        if log.stats.started_at and log.stats.completed_at:
            from datetime import datetime

            wall = (
                datetime.fromisoformat(log.stats.completed_at)
                - datetime.fromisoformat(log.stats.started_at)
            ).total_seconds()
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO run (id, target, variant, pack, judge_version, "
                "model_target, model_judge, started_at, cost_usd, log_path, target_cost_usd, "
                "wall_seconds) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    target,
                    variant,
                    (spec.metadata or {}).get("pack") or spec.dataset.name,
                    judge_version,
                    TARGET_MODEL,
                    judge_model,
                    spec.created,
                    cost,
                    log.location,
                    run_target_cost,
                    wall,
                ),
            )
            self.db.executemany(
                "INSERT OR REPLACE INTO result (run_id, sample_id, epoch, transcript, fact_pass, "
                "fact_detail, judge_pass, judge_rationale, citation, error, target_cost_usd) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
            self.db.executemany("INSERT OR REPLACE INTO score VALUES (?,?,?,?,?,?,?)", score_rows)
        return run_id

    def run(self, run_id: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM run WHERE id = ?", (run_id,)).fetchone()

    def runs(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM run ORDER BY started_at DESC").fetchall()

    def scores(self, run_id: str, rubric: str | None = None) -> list[sqlite3.Row]:
        sql = "SELECT * FROM score WHERE run_id = ?"
        args: tuple = (run_id,)
        if rubric:
            sql += " AND rubric = ?"
            args += (rubric,)
        return self.db.execute(sql + " ORDER BY sample_id, epoch, rubric", args).fetchall()

    def results(self, run_id: str) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM result WHERE run_id = ? ORDER BY sample_id, epoch", (run_id,)
        ).fetchall()
