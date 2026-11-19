from pathlib import Path

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelCost, ModelOutput, ModelUsage, get_model

import examiner.runner.judge as judge_mod
from examiner.pricing import PRICES, usage_cost
from examiner.runner.budget import JudgeBudget
from examiner.runner.task import examiner_task
from examiner.store import Store

PASS = '{"verdict": "pass", "rationale": "ok"}'


def out(text: str, output_tokens: int = 10) -> ModelOutput:
    o = ModelOutput.from_content("mockllm/model", text)
    o.usage = ModelUsage(input_tokens=0, output_tokens=output_tokens, total_tokens=output_tokens)
    return o


def run_v1(url: str, tmp_path: Path, budget: JudgeBudget | None, outputs):
    [log] = inspect_eval(
        examiner_task(pack="v1", target=url, judge_budget=budget),
        model="none",
        model_roles={"grader": get_model("mockllm/model", custom_outputs=outputs)},
        display="none",
        log_dir=str(tmp_path / "logs"),
        sample_id="fees-001",
    )
    [sample] = log.samples or []
    assert sample.scores is not None
    return log, sample.scores


def test_usage_cost_counts_cache_tokens():
    u = ModelUsage(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        total_tokens=0,
        input_tokens_cache_write=1_000_000,
        input_tokens_cache_read=1_000_000,
    )
    assert usage_cost(u, PRICES["anthropic/claude-sonnet-5-5"]) == pytest.approx(
        2.0 + 10.0 + 2.5 + 0.10
    )


def test_zero_budget_skips_every_judge_call(bot, tmp_path: Path):
    url, _ = bot
    _, scores = run_v1(url, tmp_path, JudgeBudget(limit_usd=0.0), [])
    for r in ("factual", "disclosure", "commitments"):
        assert scores[f"judge_{r}"].reason == "budget_exhausted"


def test_budget_stops_after_spend(bot, tmp_path: Path):
    url, _ = bot
    prices = {
        "mockllm/model": ModelCost(input=0, output=1000, input_cache_write=0, input_cache_read=0)
    }
    budget = JudgeBudget(limit_usd=0.005, prices=prices)  # one call costs 0.01
    log, scores = run_v1(url, tmp_path, budget, [out(PASS)] * 3)
    reasons = [scores[f"judge_{r}"].reason for r in ("factual", "disclosure", "commitments")]
    assert reasons == [None, "budget_exhausted", "budget_exhausted"]
    assert budget.spent_usd == pytest.approx(0.01)
    store = Store(tmp_path / "x.db")
    rows = {r["rubric"]: r["passed"] for r in store.scores(store.index_log(log, "t", "naive"))}
    assert rows == {"factual": 1, "disclosure": None, "commitments": None}


def test_grader_exception_is_grader_failed_and_keeps_others(bot, tmp_path: Path, monkeypatch):
    url, _ = bot
    real = get_model("mockllm/model", custom_outputs=[out(PASS), out(PASS)])
    calls = {"n": 0}

    class Flaky:
        def __str__(self) -> str:
            return "mockllm/model"

        async def generate(self, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("api down")
            return await real.generate(*args, **kwargs)

    monkeypatch.setattr(judge_mod, "get_model", lambda **kw: Flaky())
    log, scores = run_v1(url, tmp_path, None, [])
    assert scores["judge_factual"].value == "C"
    assert scores["judge_disclosure"].reason == "grader_failed"
    assert "api down" in (scores["judge_disclosure"].explanation or "")
    assert scores["judge_commitments"].value == "C"
    assert not (log.samples or [])[0].error
