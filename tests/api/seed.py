"""Seed a Store with hand-made rows (no Inspect, no network)."""

import json
from pathlib import Path

from examiner.store import Store


def add_run(store: Store, run_id: str, variant: str = "naive", started: str = "2026-11-18T10:00"):
    with store.db:
        store.db.execute(
            "INSERT INTO run (id, target, variant, pack, judge_version, model_target, model_judge, "
            "started_at, cost_usd, log_path, target_cost_usd, wall_seconds) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                "http://bot",
                variant,
                "v1",
                "factual-v2",
                "haiku",
                "sonnet",
                started,
                1.5,
                "logs/x.eval",
                0.02,
                200.0,
            ),
        )


def add_result(
    store: Store,
    run_id: str,
    sample_id: str,
    fact: int | None,
    verdicts: dict[str, int | None],
    epoch: int = 1,
    error: str | None = None,
):
    judge = None
    if verdicts and all(v is not None for v in verdicts.values()):
        judge = int(all(verdicts.values()))
    with store.db:
        store.db.execute(
            "INSERT INTO result (run_id, sample_id, epoch, transcript, fact_pass, fact_detail, "
            "judge_pass, judge_rationale, citation, error, target_cost_usd) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                sample_id,
                epoch,
                f"CUSTOMER: q {sample_id}\nBOT: a",
                fact,
                json.dumps({"missing": [], "forbidden": []}),
                judge,
                "notes",
                "cite",
                error,
                0.0001,
            ),
        )
        for rubric, passed in verdicts.items():
            store.db.execute(
                "INSERT INTO score VALUES (?,?,?,?,?,?,?)",
                (run_id, sample_id, epoch, rubric, passed, f"{rubric} rationale", f"{rubric}-v1"),
            )


ALL3 = ("factual", "disclosure", "commitments")


def verdicts(*vals: int | None) -> dict[str, int | None]:
    return dict(zip(ALL3, vals, strict=True))


def seeded(path: Path) -> Store:
    """Two runs on pack v1: naive (older) and guarded (newer)."""
    s = Store(path)
    add_run(s, "naive1", "naive", "2026-11-18T10:00")
    add_result(s, "naive1", "fees-001", 0, verdicts(1, 0, 1))
    add_result(s, "naive1", "fees-002", 1, verdicts(1, 1, 1))
    add_result(s, "naive1", "rege-020", 1, verdicts(0, 1, 1))
    add_result(s, "naive1", "rege-001", None, {}, error="target error: boom")
    add_run(s, "guard1", "guarded", "2026-11-18T11:00")
    add_result(s, "guard1", "fees-001", 1, verdicts(1, 1, 1))
    add_result(s, "guard1", "fees-002", 0, verdicts(1, 1, 1))
    add_result(s, "guard1", "rege-020", 1, verdicts(1, 1, None))
    add_result(s, "guard1", "rege-002", 1, verdicts(1, 1, 1))
    return s
