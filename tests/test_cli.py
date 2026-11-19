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
    assert "12 CFR 1005.11(c)(2)" in result.output
    assert "fact 1/5" in result.output
    store = Store(db)
    [run] = store.runs()
    assert len(store.results(run["id"])) == 5


def test_cli_run_unknown_pack_fails_cleanly(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["run", "--pack", "nope", "--judge-model", "mockllm/model"])
    assert result.exit_code != 0
    assert "nope" in result.output


def test_cost_options_caps_priced_judge():
    from examiner.cli import cost_options

    opts = cost_options("anthropic/claude-sonnet-5-5", 0.5)
    assert opts["cost_limit"] == 0.5
    assert opts["model_cost_config"]["anthropic/claude-sonnet-5-5"].output == 10.0
    assert cost_options("mockllm/model", 0.5) == {}


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
        store.db.execute("UPDATE result SET judge_pass = 1")
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


def test_cost_cap_option_is_per_sample():
    result = CliRunner().invoke(app, ["run", "--help"])
    assert "--max-cost-per-sample" in result.output
