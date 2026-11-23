import json
from pathlib import Path

from examiner.export import export_snapshot
from tests.api.seed import seeded


def test_export_writes_every_screen_and_no_label_queue(tmp_path: Path):
    db = tmp_path / "x.db"
    seeded(db)
    out = tmp_path / "data"
    n = export_snapshot(db, out)
    runs = json.loads((out / "runs.json").read_text())
    assert {r["id"] for r in runs} == {"naive1", "guard1"}
    detail = json.loads((out / "runs/naive1.json").read_text())
    assert {"run", "scorecard", "ops"} <= set(detail)
    details = json.loads((out / "runs/naive1/details.json").read_text())
    assert "fees-001/1" in details and details["fees-001/1"]["transcript"]
    diff = json.loads((out / "diff/naive1__guard1.json").read_text())
    assert diff["overall"]["counts"]["fixed"] >= 0 and "factual" in diff
    assert (out / "calibration.json").exists() and (out / "runs/naive1/taxonomy.json").exists()
    assert not list(out.rglob("*label*"))
    assert n == 1 + 2 * 4 + 1 + 2
