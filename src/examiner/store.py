"""SQLite index of Inspect eval logs."""

import json
import sqlite3
from pathlib import Path

from inspect_ai.log import EvalLog

from examiner.runner.solver import transcript_text

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
"""

TARGET_MODEL = "anthropic/claude-haiku-5-5"


def _passed(value: object) -> int | None:
    return None if value is None else int(value == "C")


class Store:
    def __init__(self, path: Path = Path("examiner.db")):
        self.path = Path(path)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

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
        judge_version = None
        rows = []
        for s in log.samples or []:
            scores = s.scores or {}
            fact = scores.get("fact_check")
            judge = scores.get("judge")
            if judge and judge.metadata:
                judge_version = judge.metadata.get("judge_version", judge_version)
            citation = s.metadata.get("scenario", {}).get("citation")
            judge_failed = bool(judge and judge.reason == "grader_failed")
            if judge is None or judge_failed:
                judge_pass = None
            else:
                judge_pass = _passed(judge.value)
            rationale = judge.explanation if judge else None
            if judge_failed:
                rationale = f"grader_failed: {rationale}"
            rows.append(
                (
                    run_id,
                    str(s.id),
                    s.epoch,
                    transcript_text(s.messages),
                    _passed(fact.value) if fact else None,
                    json.dumps(fact.metadata) if fact else None,
                    judge_pass,
                    rationale,
                    citation,
                    s.error.message if s.error else None,
                )
            )
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO run VALUES (?,?,?,?,?,?,?,?,?,?)",
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
                ),
            )
            self.db.executemany("INSERT OR REPLACE INTO result VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
        return run_id

    def run(self, run_id: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM run WHERE id = ?", (run_id,)).fetchone()

    def runs(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM run ORDER BY started_at DESC").fetchall()

    def results(self, run_id: str) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM result WHERE run_id = ? ORDER BY sample_id, epoch", (run_id,)
        ).fetchall()
