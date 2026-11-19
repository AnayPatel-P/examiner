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
    assert "12 CFR 1005.11(c)(3)" in result.output
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
