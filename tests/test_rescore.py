import asyncio
from pathlib import Path

from inspect_ai.model import ModelOutput, get_model

from examiner.rescore import rescore_run
from examiner.runner.judge import RUBRICS
from examiner.store import Store
from tests.api.seed import seeded


def grader(*texts: str):
    return get_model(
        "mockllm/model",
        custom_outputs=[ModelOutput.from_content("mockllm/model", t) for t in texts],
    )


FAIL = '{"verdict": "fail", "rationale": "new rubric says no"}'


def test_rescore_replaces_verdicts_and_archives_old(tmp_path: Path):
    store = seeded(tmp_path / "x.db")
    store.save_label("naive1", "fees-002", 1, "factual", False)
    before = store.judged_with_labels("factual")
    assert [r["judge_pass"] for r in before] == [1]
    rep = asyncio.run(rescore_run(store, "naive1", "factual", grader(*[FAIL] * 10)))
    assert rep.rescored == 3 and rep.failed == []  # rege-001 errored
    assert rep.changed == 2  # fees-001 and fees-002 were passes; rege-020 was already a fail
    rows = {r["sample_id"]: r for r in store.scores("naive1", "factual")}
    assert all(r["passed"] == 0 for r in rows.values())
    assert rows["fees-002"]["judge_version"] == RUBRICS["factual"].version
    # Combined judge verdict follows, and the old version stays queryable.
    res = store.result("naive1", "fees-002", 1)
    assert res is not None and res["judge_pass"] == 0
    old = store.judged_with_labels("factual", judge_version="factual-v1")
    assert [r["judge_pass"] for r in old] == [1]
    assert [r["judge_pass"] for r in store.judged_with_labels("factual")] == [0]
    # Other runs are untouched.
    assert {r["passed"] for r in store.scores("guard1", "factual")} == {1}


def test_rescore_keeps_old_verdict_on_garbage(tmp_path: Path):
    store = seeded(tmp_path / "x.db")
    rep = asyncio.run(rescore_run(store, "naive1", "factual", grader(*["no json"] * 10)))
    assert rep.rescored == 0 and len(rep.failed) == 3
    assert {r["passed"] for r in Store(tmp_path / "x.db").scores("naive1", "factual")} == {0, 1}


def test_rescoring_twice_at_same_version_does_not_double_count(tmp_path: Path):
    store = seeded(tmp_path / "x.db")
    store.save_label("naive1", "fees-002", 1, "factual", False)
    for _ in range(2):
        asyncio.run(rescore_run(store, "naive1", "factual", grader(*[FAIL] * 10)))
    version = RUBRICS["factual"].version
    assert len(store.judged_with_labels("factual", judge_version=version)) == 1
    assert len(store.judged_with_labels("factual", judge_version="factual-v1")) == 1
