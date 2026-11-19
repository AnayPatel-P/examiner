from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from inspect_ai import eval as inspect_eval

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


def test_null_usage_values_do_not_crash(bot, tmp_path: Path):
    url, srv = bot
    srv.usage = {"input_tokens": None, "output_tokens": 5}
    log = run_smoke(url, tmp_path, "fees-nsf")
    [sample] = log.samples or []
    assert sample.error is None
    assert sample.metadata["target_usage"] is None
