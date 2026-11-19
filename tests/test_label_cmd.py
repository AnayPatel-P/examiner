import csv
from pathlib import Path

from typer.testing import CliRunner

from examiner.cli import app

FIELDS = ["sample_id", "epoch", "citation", "source_note", "transcript", "human_pass"]


def sheet(tmp_path: Path, labels: list[str]) -> Path:
    path = tmp_path / "labels.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for i, lab in enumerate(labels):
            w.writerow(
                {
                    "sample_id": f"s{i}",
                    "epoch": 1,
                    "citation": "12 CFR 1005.6(b)(3)",
                    "source_note": "Report within 60 days.",
                    "transcript": f"USER: q{i}\nBOT: a{i}",
                    "human_pass": lab,
                }
            )
    return path


def labels_of(path: Path) -> list[str]:
    return [r["human_pass"] for r in csv.DictReader(path.open())]


def test_label_shows_transcript_and_saves_answers(tmp_path: Path):
    path = sheet(tmp_path, ["", "", ""])
    res = CliRunner().invoke(app, ["label", "--labels", str(path)], input="y\nn\ny\n")
    assert res.exit_code == 0, res.output
    assert "BOT: a0" in res.output and "Report within 60 days." in res.output
    assert labels_of(path) == ["y", "n", "y"]
    assert "3/3 labeled" in res.output


def test_label_skips_already_labeled(tmp_path: Path):
    path = sheet(tmp_path, ["n", ""])
    res = CliRunner().invoke(app, ["label", "--labels", str(path)], input="y\n")
    assert "BOT: a0" not in res.output
    assert labels_of(path) == ["n", "y"]


def test_label_quit_keeps_progress(tmp_path: Path):
    path = sheet(tmp_path, ["", "", ""])
    CliRunner().invoke(app, ["label", "--labels", str(path)], input="y\nq\n")
    assert labels_of(path) == ["y", "", ""]


def test_label_reprompts_on_bad_input(tmp_path: Path):
    path = sheet(tmp_path, [""])
    res = CliRunner().invoke(app, ["label", "--labels", str(path)], input="maybe\nn\n")
    assert labels_of(path) == ["n"]
    assert "y, n, s or q" in res.output
