from pathlib import Path

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.log import EvalLog
from inspect_ai.model import ModelOutput, get_model

from examiner.runner.task import examiner_task
from examiner.store import Store
from tests.conftest import free_port


def judged_log(
    url: str, log_dir: Path, judge_text: str = '{"verdict":"pass","rationale":"ok"}'
) -> EvalLog:
    grader = get_model(
        "mockllm/model",
        custom_outputs=[ModelOutput.from_content("mockllm/model", judge_text)] * 5,
    )
    [log] = inspect_eval(
        examiner_task(pack="smoke", target=url),
        model="none",
        model_roles={"grader": grader},
        display="none",
        log_dir=str(log_dir),
    )
    return log


@pytest.fixture
def log(bot, tmp_path: Path) -> EvalLog:
    url, _ = bot
    return judged_log(url, tmp_path / "logs")


def test_index_log_writes_run_and_results(log: EvalLog, tmp_path: Path):
    store = Store(tmp_path / "x.db")
    run_id = store.index_log(log, target="http://bot", variant="naive")
    run = store.run(run_id)
    assert run is not None
    assert run["pack"] == "smoke" and run["variant"] == "naive"
    assert run["judge_version"] == "factual-v2"
    rows = {r["sample_id"]: r for r in store.results(run_id)}
    assert len(rows) == 5
    od = rows["fees-overdraft-amount"]
    assert od["fact_pass"] == 1 and od["judge_pass"] == 1
    assert od["judge_rationale"] == "[factual] ok"
    assert od["citation"] == "Meridian fee schedule: overdraft"
    assert "BOT: Our overdraft fee is $34." in od["transcript"]
    assert rows["rege-investigation-time"]["fact_pass"] == 0
    assert all(r["latency_s"] is not None and r["latency_s"] >= 0 for r in rows.values())


def test_index_log_upsert_no_duplicates(log: EvalLog, tmp_path: Path):
    store = Store(tmp_path / "x.db")
    run_id = store.index_log(log, target="t", variant="naive")
    store.index_log(log, target="t", variant="naive")
    assert len(store.results(run_id)) == 5


def test_index_records_error_samples(tmp_path: Path):
    [log] = inspect_eval(
        examiner_task(pack="smoke", target=f"http://127.0.0.1:{free_port()}", use_judge=False),
        model="none",
        display="none",
        log_dir=str(tmp_path / "logs"),
        fail_on_error=False,
        sample_id="fees-nsf",
    )
    store = Store(tmp_path / "x.db")
    [row] = store.results(store.index_log(log, target="t", variant="naive"))
    assert "target error" in row["error"]
    assert row["fact_pass"] is None and row["judge_pass"] is None


def test_grader_failed_stored_as_no_verdict(bot, tmp_path: Path):
    url, _ = bot
    log = judged_log(url, tmp_path / "logs", judge_text="no json here")
    store = Store(tmp_path / "x.db")
    rows = store.results(store.index_log(log, target="t", variant="naive"))
    assert all(r["judge_pass"] is None for r in rows)
    assert all("grader_failed" in r["judge_rationale"] for r in rows)


def test_batch_save_and_progress(tmp_path: Path):
    from tests.api.seed import seeded

    store = seeded(tmp_path / "x.db")
    items = [
        {"run_id": "naive1", "sample_id": "fees-001", "epoch": 1, "rubric": "factual"},
        {"run_id": "guard1", "sample_id": "fees-002", "epoch": 1, "rubric": "disclosure"},
    ]
    store.save_batch("b1", items)
    assert [r["sample_id"] for r in store.batch_items("b1")] == ["fees-001", "fees-002"]
    store.save_label("naive1", "fees-001", 1, "factual", True)
    store.save_label("naive1", "fees-001", 1, "disclosure", True)  # not in the batch
    [b] = store.batches()
    assert (b["name"], b["n"], b["labeled"]) == ("b1", 2, 1)
    store.save_batch("b1", items[:1])  # replacing a batch drops the old items
    assert len(store.batch_items("b1")) == 1
