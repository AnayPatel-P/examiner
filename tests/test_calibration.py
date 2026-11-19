import csv
from pathlib import Path

import pytest

from examiner.calibration import agreement_report, cohen_kappa, read_labels

T, F = True, False


def test_kappa_known_values():
    assert cohen_kappa([T, T, F, F], [T, F, F, F]) == pytest.approx(0.5)


def test_kappa_perfect():
    assert cohen_kappa([T, F, T], [T, F, T]) == 1.0


def test_kappa_degenerate():
    assert cohen_kappa([T, T, T], [T, T, T]) == 1.0
    assert cohen_kappa([], []) == 0.0


def test_kappa_length_mismatch():
    with pytest.raises(ValueError):
        cohen_kappa([T], [T, F])


def test_read_labels_skips_blank_and_parses_yn(tmp_path: Path):
    path = tmp_path / "l.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sample_id", "epoch", "human_pass"])
        w.writeheader()
        w.writerows(
            [
                {"sample_id": "a", "epoch": "1", "human_pass": "y"},
                {"sample_id": "b", "epoch": "1", "human_pass": " N "},
                {"sample_id": "c", "epoch": "1", "human_pass": ""},
            ]
        )
    assert read_labels(path) == {("a", 1): True, ("b", 1): False}


def test_read_labels_rejects_bad_value(tmp_path: Path):
    path = tmp_path / "l.csv"
    path.write_text("sample_id,epoch,human_pass\na,1,maybe\n")
    with pytest.raises(ValueError, match="maybe"):
        read_labels(path)


def test_agreement_report_counts():
    judge = {("a", 1): T, ("b", 1): T, ("c", 1): F, ("d", 1): F, ("e", 1): None}
    human = {("a", 1): T, ("b", 1): F, ("c", 1): F, ("d", 1): F, ("e", 1): T}
    r = agreement_report(judge, human)
    assert r.n == 4  # e has no judge verdict
    assert r.raw_agreement == pytest.approx(0.75)
    assert r.kappa == pytest.approx(0.5)
    assert (r.both_pass, r.judge_pass_human_fail, r.judge_fail_human_pass, r.both_fail) == (
        1,
        1,
        0,
        2,
    )
    assert r.disagreements == [("b", 1)]
