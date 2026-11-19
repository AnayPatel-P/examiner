from pathlib import Path

from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, get_model
from typer.testing import CliRunner

from examiner.cli import app
from examiner.runner.judge import RUBRICS, build_judge_prompt
from examiner.runner.task import examiner_task
from examiner.scenarios.schema import load_pack
from examiner.store import Store

V1 = {s.id: s for s in load_pack("v1")}


def run_v1(url: str, tmp_path: Path, *judge_texts: str):
    grader = get_model(
        "mockllm/model",
        custom_outputs=[ModelOutput.from_content("mockllm/model", t) for t in judge_texts],
    )
    [log] = inspect_eval(
        examiner_task(pack="v1", target=url),
        model="none",
        model_roles={"grader": grader},
        display="none",
        log_dir=str(tmp_path / "logs"),
        sample_id="fees-001",
    )
    return log


PASS = '{"verdict": "pass", "rationale": "ok"}'
FAIL = '{"verdict": "fail", "rationale": "bad"}'


def test_rubric_versions():
    assert {k: v.version for k, v in RUBRICS.items()} == {
        "factual": "factual-v2",
        "disclosure": "disclosure-v1",
        "commitments": "commitments-v1",
    }


def test_each_rubric_scored_separately(bot, tmp_path: Path):
    url, _ = bot
    log = run_v1(url, tmp_path, PASS, FAIL, PASS)
    [sample] = log.samples or []
    assert sample.scores is not None
    assert sample.scores["judge_factual"].value == "C"
    assert sample.scores["judge_disclosure"].value == "I"
    assert sample.scores["judge_commitments"].value == "C"
    store = Store(tmp_path / "x.db")
    run_id = store.index_log(log, target="t", variant="naive")
    rows = {r["rubric"]: r for r in store.scores(run_id)}
    assert rows["disclosure"]["passed"] == 0 and rows["disclosure"]["judge_version"] == (
        "disclosure-v1"
    )
    [result] = store.results(run_id)
    assert result["judge_pass"] == 0


def test_one_rubric_grader_failed_keeps_others(bot, tmp_path: Path):
    url, _ = bot
    log = run_v1(url, tmp_path, PASS, "garbage", FAIL)
    store = Store(tmp_path / "x.db")
    run_id = store.index_log(log, target="t", variant="naive")
    rows = {r["rubric"]: r["passed"] for r in store.scores(run_id)}
    assert rows == {"factual": 1, "disclosure": None, "commitments": 0}
    [result] = store.results(run_id)
    assert result["judge_pass"] is None


def test_smoke_pack_runs_factual_only(bot, tmp_path: Path):
    url, _ = bot
    [log] = inspect_eval(
        examiner_task(pack="smoke", target=url),
        model="none",
        model_roles={
            "grader": get_model(
                "mockllm/model", custom_outputs=[ModelOutput.from_content("mockllm/model", PASS)]
            )
        },
        display="none",
        log_dir=str(tmp_path / "logs"),
        sample_id="fees-nsf",
    )
    store = Store(tmp_path / "x.db")
    rows = store.scores(store.index_log(log, target="t", variant="naive"))
    assert [r["rubric"] for r in rows] == ["factual"]


def test_disclosure_prompt_includes_key_facts():
    prompt = build_judge_prompt(V1["fees-001"].model_dump(), "USER: q\nBOT: a", "disclosure")
    assert "$34" in prompt and "disclosure-v1" in prompt


def test_factual_prompt_excludes_must_say():
    s = V1["fees-005"]
    prompt = build_judge_prompt(s.model_dump(), "USER: q\nBOT: a", "factual")
    assert "doesn't charge an NSF" not in prompt


def test_commitments_prompt_mentions_promises():
    prompt = build_judge_prompt(V1["fees-029"].model_dump(), "USER: q\nBOT: a", "commitments")
    assert "promise" in prompt.lower()


def test_kappa_by_rubric(bot, tmp_path: Path, monkeypatch):
    import csv

    url, _ = bot
    log = run_v1(url, tmp_path, PASS, FAIL, PASS)
    db = tmp_path / "x.db"
    run_id = Store(db).index_log(log, target="t", variant="naive")
    labels = tmp_path / "l.csv"
    with labels.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sample_id", "epoch", "human_pass"])
        w.writeheader()
        w.writerow({"sample_id": "fees-001", "epoch": 1, "human_pass": "n"})
    res = CliRunner().invoke(
        app,
        [
            "kappa",
            "--run",
            run_id,
            "--labels",
            str(labels),
            "--db",
            str(db),
            "--rubric",
            "disclosure",
        ],
    )
    assert res.exit_code == 0, res.output
    assert "raw agreement=1.00" in res.output
