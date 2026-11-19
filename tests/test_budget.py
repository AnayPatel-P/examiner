from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from inspect_ai import eval as inspect_eval

from examiner.cli import per_sample_cap, summarize
from examiner.meridian.app import create_app
from examiner.runner.task import examiner_task
from examiner.store import Store, target_cost


def run_smoke(url: str, tmp_path: Path, sample_id: str):
    [log] = inspect_eval(
        examiner_task(pack="smoke", target=url, use_judge=False),
        model="none",
        display="none",
        log_dir=str(tmp_path / "logs"),
        sample_id=sample_id,
    )
    return log


def test_chat_returns_usage_when_responder_reports_it():
    async def responder(system, messages):
        return "hi", {"input_tokens": 10, "output_tokens": 5}

    r = TestClient(create_app(responder)).post(
        "/chat", json={"messages": [{"role": "user", "content": "x"}]}
    )
    assert r.json()["usage"] == {"input_tokens": 10, "output_tokens": 5}


def test_solver_sums_target_usage(bot, tmp_path: Path):
    url, srv = bot
    srv.usage = {"input_tokens": 100, "output_tokens": 20}
    log = run_smoke(url, tmp_path, "rege-provisional-credit")
    [sample] = log.samples or []
    assert sample.metadata["target_usage"] == {"input_tokens": 200, "output_tokens": 40}
    store = Store(tmp_path / "x.db")
    run_id = store.index_log(log, target="t", variant="naive")
    [row] = store.results(run_id)
    assert row["target_cost_usd"] == pytest.approx(target_cost(200, 40))
    run = store.run(run_id)
    assert run is not None
    assert run["target_cost_usd"] == pytest.approx(target_cost(200, 40))


def test_missing_usage_is_null_cost(bot, tmp_path: Path):
    url, _ = bot
    log = run_smoke(url, tmp_path, "fees-nsf")
    store = Store(tmp_path / "x.db")
    run_id = store.index_log(log, target="t", variant="naive")
    [row] = store.results(run_id)
    assert row["target_cost_usd"] is None


def test_target_cost_uses_haiku_prices():
    assert target_cost(1_000_000, 1_000_000) == pytest.approx(0.60)


def test_per_sample_cap_from_run_cap():
    assert per_sample_cap(5.0, 120, 1) == pytest.approx(5.0 / 120)
    assert per_sample_cap(5.0, 20, 4) == pytest.approx(5.0 / 80)


def test_summary_by_area():
    results = [
        {"sample_id": "fees-001", "epoch": 1, "fact_pass": 1, "error": None},
        {"sample_id": "fees-002", "epoch": 1, "fact_pass": 0, "error": None},
        {"sample_id": "rege-001", "epoch": 1, "fact_pass": 1, "error": None},
        {"sample_id": "rege-002", "epoch": 1, "fact_pass": None, "error": "boom"},
    ]
    scores = [
        {"sample_id": "fees-001", "epoch": 1, "rubric": "factual", "passed": 1},
        {"sample_id": "fees-002", "epoch": 1, "rubric": "factual", "passed": 1},
        {"sample_id": "rege-001", "epoch": 1, "rubric": "factual", "passed": 0},
        {"sample_id": "fees-001", "epoch": 1, "rubric": "disclosure", "passed": None},
    ]
    areas = {"fees-001": "fees", "fees-002": "fees", "rege-001": "reg_e", "rege-002": "reg_e"}
    table = summarize(results, scores, areas)
    assert table["fees"]["fact"] == (1, 2)
    assert table["fees"]["factual"] == (2, 2)
    assert table["fees"]["disclosure"] == (0, 0)
    assert table["reg_e"]["fact"] == (1, 1)
    assert table["reg_e"]["errors"] == 1
