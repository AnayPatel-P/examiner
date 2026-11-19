from pathlib import Path

from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, get_model

from examiner.runner.judge import JUDGE_VERSION, build_judge_prompt, parse_verdict
from examiner.runner.task import examiner_task
from examiner.scenarios.schema import load_pack


def grader(*texts: str):
    return get_model(
        "mockllm/model",
        custom_outputs=[ModelOutput.from_content("mockllm/model", t) for t in texts],
    )


def run_judged(url: str, tmp_path: Path, judge_text: str):
    [log] = inspect_eval(
        examiner_task(pack="smoke", target=url),
        model="none",
        model_roles={"grader": grader(judge_text)},
        display="none",
        log_dir=str(tmp_path),
        sample_id="fees-overdraft-amount",
    )
    [sample] = log.samples or []
    assert sample.scores
    return sample.scores["judge_factual"]


def test_parse_verdict_ok():
    assert parse_verdict('Sure. {"verdict": "fail", "rationale": "wrong fee"} done') == (
        "fail",
        "wrong fee",
    )


def test_parse_verdict_garbage_returns_none():
    assert parse_verdict("I think it passes") is None
    assert parse_verdict('{"verdict": "maybe", "rationale": "x"}') is None
    assert parse_verdict("{not json}") is None


def test_judge_prompt_excludes_must_say():
    s = next(s for s in load_pack("smoke") if s.id == "fees-nsf")
    prompt = build_judge_prompt(s.model_dump(), "USER: q\nBOT: a")
    assert "don't charge NSF" not in prompt
    assert s.citation_display in prompt and s.source_note in prompt
    assert '"fee_per_item_usd": 34' in prompt
    assert "USER: q\nBOT: a" in prompt


def test_judge_score_end_to_end_fail(bot, tmp_path: Path):
    url, _ = bot
    score = run_judged(url, tmp_path, '{"verdict": "fail", "rationale": "invented a date"}')
    assert score.value == "I"
    assert score.metadata is not None
    assert score.metadata["rationale"] == "invented a date"
    assert score.metadata["judge_version"] == JUDGE_VERSION
    assert score.metadata["citation"] == "Meridian fee schedule: overdraft"


def test_judge_score_end_to_end_pass(bot, tmp_path: Path):
    url, _ = bot
    score = run_judged(url, tmp_path, '{"verdict": "pass", "rationale": "ok"}')
    assert score.value == "C"


def test_judge_unparseable_is_grader_failed(bot, tmp_path: Path):
    url, _ = bot
    score = run_judged(url, tmp_path, "Looks fine to me!")
    assert score.value == "I"
    assert score.reason == "grader_failed"
    assert "Looks fine to me!" in (score.explanation or "")
