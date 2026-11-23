"""Static scorecard export: every read endpoint the dashboard uses, written as JSON.

The files come from the real API (through a test client), so the static site and
the live dashboard can't drift apart in shape. Labeling stays local-only.
"""

import json
from itertools import permutations
from pathlib import Path

from fastapi.testclient import TestClient

from examiner.api.app import create_api
from examiner.reports import CHECKS


def export_snapshot(db: Path, out: Path) -> int:
    client = TestClient(create_api(db))

    def get(path: str, **params) -> object:
        res = client.get(path, params=params)
        res.raise_for_status()
        return res.json()

    def write(rel: str, data: object) -> None:
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, separators=(",", ":")))

    files = 0
    runs = get("/api/runs")
    assert isinstance(runs, list)
    write("runs.json", runs)
    files += 1
    for r in runs:
        rid = r["id"]
        write(f"runs/{rid}.json", get(f"/api/runs/{rid}"))
        results = get(f"/api/runs/{rid}/results")
        assert isinstance(results, list)
        write(f"runs/{rid}/results.json", results)
        details = {
            f"{x['sample_id']}/{x['epoch']}": get(
                f"/api/runs/{rid}/results/{x['sample_id']}", epoch=x["epoch"]
            )
            for x in results
        }
        write(f"runs/{rid}/details.json", details)
        write(f"runs/{rid}/taxonomy.json", get(f"/api/runs/{rid}/taxonomy"))
        files += 4
    write("calibration.json", get("/api/calibration"))
    files += 1
    for a, b in permutations([r["id"] for r in runs], 2):
        write(f"diff/{a}__{b}.json", {c: get("/api/diff", a=a, b=b, check=c) for c in CHECKS})
        files += 1
    return files
