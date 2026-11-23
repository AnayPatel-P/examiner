from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from examiner.api.app import create_api
from tests.api.seed import seeded


@pytest.fixture
def api(tmp_path: Path) -> TestClient:
    seeded(tmp_path / "x.db")
    return TestClient(create_api(tmp_path / "x.db"))


def test_runs_list(api: TestClient):
    runs = api.get("/api/runs").json()
    assert [r["id"] for r in runs] == ["guard1", "naive1"]
    naive = runs[1]
    assert naive["variant"] == "naive" and naive["n"] == 4 and naive["errors"] == 1
    assert naive["overall"] == {"passed": 1, "n": 3, "rate": 1 / 3}
    assert naive["cost_usd"] == 1.5 and naive["target_cost_usd"] == 0.02


def test_run_detail_scorecard(api: TestClient):
    body = api.get("/api/runs/naive1").json()
    assert body["run"]["id"] == "naive1"
    card = body["scorecard"]
    assert card["fees"]["disclosure"] == {"passed": 1, "n": 2, "rate": 0.5}
    assert card["reg_e"]["errors"] == 1
    assert card["all"]["overall"]["n"] == 3


def test_results_filter_fail(api: TestClient):
    rows = api.get("/api/runs/naive1/results", params={"status": "fail"}).json()
    assert [r["sample_id"] for r in rows] == ["fees-001", "rege-020"]
    r = rows[0]
    assert r["area"] == "fees" and r["overall"] == 0
    assert r["rubrics"] == {"factual": 1, "disclosure": 0, "commitments": 1}
    errs = api.get("/api/runs/naive1/results", params={"status": "error"}).json()
    assert [r["sample_id"] for r in errs] == ["rege-001"]
    fees = api.get("/api/runs/naive1/results", params={"area": "fees"}).json()
    assert {r["sample_id"] for r in fees} == {"fees-001", "fees-002"}


def test_results_bad_status_422(api: TestClient):
    assert api.get("/api/runs/naive1/results", params={"status": "meh"}).status_code == 422


def test_result_detail_has_citation_text(api: TestClient):
    d = api.get("/api/runs/naive1/results/rege-020").json()
    assert d["transcript"].startswith("CUSTOMER:")
    assert d["scenario"]["persona"] and d["scenario"]["turns"]
    assert d["scenario"]["must_say"][0]["id"] == "five-bd"
    assert d["fact_detail"] == {"missing": [], "forbidden": []}
    assert {s["rubric"] for s in d["scores"]} == {"factual", "disclosure", "commitments"}
    [cite] = d["citations"]
    assert cite["cite"] == "12 CFR 1005.11(d)(2)(ii)"
    assert "five business days" in cite["text"]


def test_unknown_run_404(api: TestClient):
    assert api.get("/api/runs/nope").status_code == 404
    assert api.get("/api/runs/nope/results").status_code == 404


def test_unknown_sample_404(api: TestClient):
    assert api.get("/api/runs/naive1/results/fees-999").status_code == 404
    assert api.get("/api/runs/naive1/results/fees-001", params={"epoch": 2}).status_code == 404


def test_cors_allows_vite(api: TestClient):
    r = api.get("/api/runs", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_run_with_missing_pack_does_not_500(tmp_path: Path):
    from tests.api.seed import add_result, add_run, verdicts

    s = seeded(tmp_path / "y.db")
    add_run(s, "gone1")
    s.db.execute("UPDATE run SET pack = 'deleted-pack' WHERE id = 'gone1'")
    s.db.commit()
    add_result(s, "gone1", "fees-001", 1, verdicts(1, 1, 1))
    api = TestClient(create_api(tmp_path / "y.db"), raise_server_exceptions=False)
    d = api.get("/api/runs/gone1/results/fees-001")
    assert d.status_code == 200 and d.json()["scenario"] is None
    assert api.get("/api/label-queue").status_code == 200


def test_run_detail_has_ops_and_taxonomy(tmp_path):
    from fastapi.testclient import TestClient

    from examiner.api.app import create_api
    from tests.api.seed import seeded

    seeded(tmp_path / "x.db")
    api = TestClient(create_api(tmp_path / "x.db"))
    ops = api.get("/api/runs/naive1").json()["ops"]
    assert ops["total_cost_usd"] == 1.52 and ops["n"] == 4
    tax = api.get("/api/runs/naive1/taxonomy").json()
    assert set(tax) == {"scored_scenarios", "failed_scenarios", "modes", "sections", "clauses"}
    assert api.get("/api/runs/nope/taxonomy").status_code == 404
