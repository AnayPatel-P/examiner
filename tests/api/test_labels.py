from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from examiner.api.app import create_api
from examiner.store import Store
from tests.api.seed import seeded

QUEUE_KEYS = {
    "run_id",
    "sample_id",
    "epoch",
    "rubric",
    "transcript",
    "citations",
    "source_note",
    "key_facts",
    "rubric_text",
}


@pytest.fixture
def db(tmp_path: Path) -> Path:
    seeded(tmp_path / "x.db")
    return tmp_path / "x.db"


@pytest.fixture
def api(db: Path) -> TestClient:
    return TestClient(create_api(db))


def label(api: TestClient, run: str, sid: str, passed: bool, rubric: str = "factual"):
    return api.post(
        "/api/labels",
        json={"run_id": run, "sample_id": sid, "epoch": 1, "rubric": rubric, "human_pass": passed},
    )


def test_label_queue_is_blind(api: TestClient):
    items = api.get("/api/label-queue", params={"run": "naive1", "rubric": "factual"}).json()
    assert items and all(set(i) == QUEUE_KEYS for i in items)
    flat = str(items)
    assert "factual rationale" not in flat and "notes" not in flat  # judge text from seed
    assert "## Rubric" in items[0]["rubric_text"] and "=== USER ===" not in items[0]["rubric_text"]


def test_label_queue_skips_labeled_and_errors(api: TestClient):
    ids = lambda: {  # noqa: E731
        i["sample_id"]
        for i in api.get("/api/label-queue", params={"run": "naive1", "rubric": "factual"}).json()
    }
    assert ids() == {"fees-001", "fees-002", "rege-020"}  # rege-001 errored
    assert label(api, "naive1", "fees-001", True).status_code == 201
    assert ids() == {"fees-002", "rege-020"}


def test_label_queue_skips_null_judge(api: TestClient):
    items = api.get("/api/label-queue", params={"run": "guard1", "rubric": "commitments"}).json()
    assert "rege-020" not in {i["sample_id"] for i in items}


def test_label_queue_all_runs_and_limit(api: TestClient):
    items = api.get("/api/label-queue", params={"rubric": "factual", "limit": 2}).json()
    assert len(items) == 2
    every = api.get("/api/label-queue", params={"rubric": "factual"}).json()
    assert {i["run_id"] for i in every} == {"naive1", "guard1"}


def test_post_label_upserts(api: TestClient, db: Path):
    label(api, "naive1", "fees-001", True)
    label(api, "naive1", "fees-001", False)
    rows = api.get("/api/labels", params={"rubric": "factual"}).json()
    assert len(rows) == 1 and rows[0]["human_pass"] is False
    assert len(Store(db).labels(rubric="factual")) == 1


def test_post_label_unknown_result_404(api: TestClient):
    assert label(api, "naive1", "fees-999", True).status_code == 404
    assert label(api, "nope", "fees-001", True).status_code == 404


def test_post_label_unknown_rubric_422(api: TestClient):
    assert label(api, "naive1", "fees-001", True, rubric="vibes").status_code == 422


def test_calibration_per_rubric(api: TestClient):
    # naive1 factual judge: fees-001 1, fees-002 1, rege-020 0
    label(api, "naive1", "fees-001", True)
    label(api, "naive1", "fees-002", False)
    label(api, "naive1", "rege-020", False)
    label(api, "naive1", "fees-001", False, rubric="disclosure")  # judge 0
    cal = api.get("/api/calibration").json()
    f = cal["factual"]
    assert f["n"] == 3 and f["both_pass"] == 1 and f["judge_pass_human_fail"] == 1
    assert f["both_fail"] == 1 and f["raw_agreement"] == pytest.approx(2 / 3)
    assert f["disagreements"] == [{"run_id": "naive1", "sample_id": "fees-002", "epoch": 1}]
    assert cal["disclosure"]["n"] == 1 and cal["disclosure"]["both_fail"] == 1
    assert "commitments" not in cal


def test_calibration_ignores_null_judge(api: TestClient):
    label(api, "guard1", "rege-020", True, rubric="commitments")  # judge NULL
    cal = api.get("/api/calibration").json()
    assert cal["commitments"]["n"] == 0


def test_labels_import_csv(db: Path, tmp_path: Path):
    from typer.testing import CliRunner

    from examiner.cli import app

    csv_path = tmp_path / "l.csv"
    csv_path.write_text(
        "sample_id,epoch,citation,source_note,transcript,human_pass\n"
        "fees-001,1,c,s,t,y\nfees-002,1,c,s,t,n\nrege-020,1,c,s,t,\n"
    )
    r = CliRunner().invoke(
        app,
        [
            "labels-import",
            "--csv",
            str(csv_path),
            "--run",
            "naive1",
            "--rubric",
            "factual",
            "--db",
            str(db),
        ],
    )
    assert r.exit_code == 0, r.output
    rows = Store(db).labels(rubric="factual")
    assert {(x["sample_id"], x["human_pass"]) for x in rows} == {("fees-001", 1), ("fees-002", 0)}
    r = CliRunner().invoke(app, ["kappa", "--run", "naive1", "--db", str(db)])
    assert r.exit_code == 0 and "n=2" in r.output, r.output


def test_calibration_no_comparable_labels_is_null(api: TestClient):
    label(api, "guard1", "rege-020", True, rubric="commitments")  # judge NULL
    c = api.get("/api/calibration").json()["commitments"]
    assert c["n"] == 0 and c["n_labels"] == 1 and c["kappa"] is None
    assert c["raw_agreement"] is None


def test_batch_queue_mixes_rubrics_in_order_and_stays_blind(api: TestClient, db: Path):
    s = Store(db)
    s.save_batch(
        "calib",
        [
            {"run_id": "guard1", "sample_id": "fees-002", "epoch": 1, "rubric": "disclosure"},
            {"run_id": "naive1", "sample_id": "fees-001", "epoch": 1, "rubric": "factual"},
            {"run_id": "naive1", "sample_id": "rege-020", "epoch": 1, "rubric": "commitments"},
        ],
    )
    items = api.get("/api/label-queue", params={"batch": "calib"}).json()
    assert [(i["sample_id"], i["rubric"]) for i in items] == [
        ("fees-002", "disclosure"),
        ("fees-001", "factual"),
        ("rege-020", "commitments"),
    ]
    assert all(set(i) == QUEUE_KEYS for i in items)
    assert "disclosure" in items[0]["rubric_text"].lower()
    flat = str(items)
    assert "rationale" not in flat and "judge_pass" not in flat
    # Labeling one item removes only that item from the batch queue.
    assert label(api, "naive1", "fees-001", False, rubric="factual").status_code == 201
    left = api.get("/api/label-queue", params={"batch": "calib"}).json()
    assert [i["sample_id"] for i in left] == ["fees-002", "rege-020"]
    [b] = api.get("/api/batches").json()
    assert b == {"name": "calib", "n": 3, "labeled": 1}


def test_unknown_batch_is_404(api: TestClient):
    assert api.get("/api/label-queue", params={"batch": "nope"}).status_code == 404
