from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from examiner.api.app import create_api
from examiner.reports import diff_runs
from tests.api.seed import seeded


@pytest.fixture
def db(tmp_path: Path) -> Path:
    seeded(tmp_path / "x.db")
    return tmp_path / "x.db"


def _diff(db: Path, check: str = "overall") -> dict:
    from examiner.store import Store

    s = Store(db)
    return diff_runs(
        s.results("naive1"), s.scores("naive1"), s.results("guard1"), s.scores("guard1"), check
    )


def ids(d: dict, cat: str) -> list[str]:
    return [i["sample_id"] for i in d[cat]]


def test_diff_categories(db: Path):
    d = _diff(db)
    assert ids(d, "fixed") == ["fees-001"]
    assert ids(d, "broke") == ["fees-002"]
    assert d["fixed"][0] == {"sample_id": "fees-001", "epoch": 1, "a": 0, "b": 1}
    assert d["counts"]["fixed"] == 1 and d["counts"]["broke"] == 1


def test_diff_only_in_one_run(db: Path):
    d = _diff(db)
    assert ids(d, "only_a") == ["rege-001"] and ids(d, "only_b") == ["rege-002"]
    assert "rege-001" not in ids(d, "broke") + ids(d, "fixed")


def test_diff_null_is_unscored(db: Path):
    d = _diff(db)
    assert ids(d, "unscored") == ["rege-020"]
    assert d["counts"]["still_fail"] == 0


def test_diff_by_rubric(db: Path):
    d = _diff(db, "factual")
    assert ids(d, "fixed") == ["rege-020"]
    assert ids(d, "still_pass") == ["fees-001", "fees-002"]
    f = _diff(db, "fact")
    assert ids(f, "fixed") == ["fees-001"] and ids(f, "broke") == ["fees-002"]


def test_diff_unknown_check_raises():
    with pytest.raises(ValueError):
        diff_runs([], [], [], [], "vibes")


def test_diff_endpoint(db: Path):
    api = TestClient(create_api(db))
    body = api.get("/api/diff", params={"a": "naive1", "b": "guard1"}).json()
    assert body["a"]["id"] == "naive1" and body["b"]["variant"] == "guarded"
    assert body["check"] == "overall" and body["counts"]["fixed"] == 1
    assert api.get("/api/diff", params={"a": "naive1", "b": "zzz"}).status_code == 404
    bad = api.get("/api/diff", params={"a": "naive1", "b": "guard1", "check": "vibes"})
    assert bad.status_code == 422


def test_diff_cli(db: Path):
    from typer.testing import CliRunner

    from examiner.cli import app

    r = CliRunner().invoke(app, ["diff", "naive1", "guard1", "--db", str(db)])
    assert r.exit_code == 0, r.output
    assert "fixed 1" in r.output and "broke 1" in r.output and "fees-002" in r.output
