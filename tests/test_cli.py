from pathlib import Path

from typer.testing import CliRunner

from examiner.cli import app
from examiner.store import Store


def test_cli_run_prints_table(bot, tmp_path: Path, monkeypatch):
    url, _ = bot
    monkeypatch.chdir(tmp_path)
    db = tmp_path / "e.db"
    result = CliRunner().invoke(
        app,
        [
            "run",
            "--target",
            url,
            "--pack",
            "smoke",
            "--judge-model",
            "mockllm/model",
            "--db",
            str(db),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "fees-overdraft-amount" in result.output
    assert "12 CFR 1005.11(c)(3)(ii)" in result.output
    assert "fact 1/5" in result.output
    store = Store(db)
    [run] = store.runs()
    assert len(store.results(run["id"])) == 5


def test_cli_run_unknown_pack_fails_cleanly(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["run", "--pack", "nope", "--judge-model", "mockllm/model"])
    assert result.exit_code != 0
    assert "nope" in result.output


def test_cli_builds_run_budget_from_prices():
    from examiner.cli import judge_budget

    b = judge_budget("anthropic/claude-sonnet-5-5", 0.5)
    assert b.limit_usd == 0.5 and "anthropic/claude-sonnet-5-5" in b.prices


def test_label_export_hides_judge_and_kappa_roundtrip(bot, tmp_path: Path, monkeypatch):
    import csv

    url, _ = bot
    monkeypatch.chdir(tmp_path)
    db = str(tmp_path / "e.db")
    runner = CliRunner()
    runner.invoke(
        app,
        ["run", "--target", url, "--judge-model", "mockllm/model", "--db", db],
    )
    store = Store(tmp_path / "e.db")
    [run] = store.runs()
    # mockllm's judge output is unparseable; give every result a verdict for the kappa step
    with store.db:
        store.db.execute("UPDATE score SET passed = 1")
    out = tmp_path / "labels.csv"
    res = runner.invoke(app, ["label-export", "--run", run["id"], "--out", str(out), "--db", db])
    assert res.exit_code == 0, res.output
    rows = list(csv.DictReader(out.open()))
    assert len(rows) == 5
    assert set(rows[0]) == {
        "sample_id",
        "epoch",
        "citation",
        "source_note",
        "transcript",
        "human_pass",
    }
    for row in rows:
        row["human_pass"] = "n"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    res = runner.invoke(app, ["kappa", "--run", run["id"], "--labels", str(out), "--db", db])
    assert res.exit_code == 0, res.output
    assert "n=5" in res.output and "kappa" in res.output


def test_run_cost_cap_option():
    import re

    # CI runners make Rich color the help text; strip ANSI codes before matching.
    result = CliRunner().invoke(app, ["run", "--help"], env={"NO_COLOR": "1", "TERM": "dumb"})
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert "--max-run-cost" in plain


def test_label_batch_command(tmp_path: Path):
    from tests.api.seed import seeded

    db = tmp_path / "x.db"
    store = seeded(db)
    store.save_label("naive1", "fees-001", 1, "factual", True)
    res = CliRunner().invoke(app, ["label-batch", "--db", str(db), "--per-rubric", "3"])
    assert res.exit_code == 0, res.output
    items = Store(db).batch_items("calib-v1")
    keys = {(i["run_id"], i["sample_id"], i["rubric"]) for i in items}
    assert ("naive1", "fees-001", "factual") not in keys  # already labeled
    assert all(i["sample_id"] != "rege-001" for i in items)  # errored
    assert ("guard1", "rege-020", "commitments") not in keys  # no judge verdict
    assert len(items) == 9


def test_cli_run_fails_when_every_sample_errors(tmp_path: Path, monkeypatch):
    from tests.conftest import free_port

    monkeypatch.chdir(tmp_path)
    dead = f"http://127.0.0.1:{free_port()}"  # nothing listens here
    result = CliRunner().invoke(
        app, ["run", "--pack", "smoke", "--target", dead, "--judge-model", "mockllm/model"]
    )
    assert result.exit_code == 1
    assert "all 5 samples errored" in result.output


def test_label_batch_refuses_to_replace_labeled_batch(tmp_path: Path):
    from tests.api.seed import seeded

    db = tmp_path / "x.db"
    seeded(db)
    args = ["label-batch", "--db", str(db), "--per-rubric", "3"]
    assert CliRunner().invoke(app, args).exit_code == 0
    first = Store(db).batch_items("calib-v1")[0]
    Store(db).save_label(first["run_id"], first["sample_id"], 1, first["rubric"], True)
    res = CliRunner().invoke(app, args)
    assert res.exit_code == 2 and "already has 1 labels" in res.output
    assert CliRunner().invoke(app, [*args, "--force"]).exit_code == 0
