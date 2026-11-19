"""Read API over the Examiner SQLite store, for the dashboard."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from examiner.calibration import calibration_by_rubric
from examiner.reports import areas_for, overall_pass, rubric_map, run_summary, scorecard
from examiner.runner.judge import rubric_guide
from examiner.scenarios.lint import cited_text
from examiner.scenarios.schema import RUBRIC_NAMES, Rubric, display_citation, load_pack
from examiner.store import Store


class LabelIn(BaseModel):
    run_id: str
    sample_id: str
    epoch: int = 1
    rubric: Rubric
    human_pass: bool


def _shuffle_key(run_id: str, sample_id: str, epoch: int) -> str:
    return hashlib.sha256(f"{run_id}/{sample_id}/{epoch}".encode()).hexdigest()


DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def create_api(db: Path = Path("examiner.db")) -> FastAPI:
    api = FastAPI(title="Examiner API")
    api.add_middleware(
        CORSMiddleware, allow_origins=DEV_ORIGINS, allow_methods=["*"], allow_headers=["*"]
    )

    def store() -> Store:
        # One connection per request: sqlite3 connections are not shared across threads.
        return Store(db)

    def get_run(s: Store, run_id: str):
        row = s.run(run_id)
        if row is None:
            raise HTTPException(404, f"no run {run_id}")
        return row

    @api.get("/api/runs")
    def runs() -> list[dict]:
        s = store()
        return [run_summary(r, s.results(r["id"])) for r in s.runs()]

    @api.get("/api/runs/{run_id}")
    def run_detail(run_id: str) -> dict:
        s = store()
        run = get_run(s, run_id)
        results = s.results(run_id)
        return {
            "run": run_summary(run, results),
            "scorecard": scorecard(results, s.scores(run_id), areas_for(run["pack"])),
        }

    @api.get("/api/runs/{run_id}/results")
    def results(
        run_id: str,
        area: str | None = None,
        status: Literal["pass", "fail", "error"] | None = None,
    ) -> list[dict]:
        s = store()
        run = get_run(s, run_id)
        areas = areas_for(run["pack"])
        rubrics = rubric_map(s.scores(run_id))
        out = []
        for r in s.results(run_id):
            row_area = areas.get(r["sample_id"], "unknown")
            overall = overall_pass(r)
            if area and row_area != area:
                continue
            if status == "error" and not r["error"]:
                continue
            if status == "pass" and overall != 1:
                continue
            if status == "fail" and overall != 0:
                continue
            out.append(
                {
                    "sample_id": r["sample_id"],
                    "epoch": r["epoch"],
                    "area": row_area,
                    "overall": overall,
                    "fact_pass": r["fact_pass"],
                    "judge_pass": r["judge_pass"],
                    "rubrics": rubrics.get((r["sample_id"], r["epoch"]), {}),
                    "citation": r["citation"],
                    "error": r["error"],
                }
            )
        return out

    @api.get("/api/runs/{run_id}/results/{sample_id}")
    def result_detail(run_id: str, sample_id: str, epoch: int = Query(1, ge=1)) -> dict:
        s = store()
        run = get_run(s, run_id)
        row = s.result(run_id, sample_id, epoch)
        if row is None:
            raise HTTPException(404, f"no result {sample_id} epoch {epoch} in run {run_id}")
        scenario = next((x for x in load_pack(run["pack"]) if x.id == sample_id), None)
        cites = scenario.citations if scenario else []
        return {
            "run_id": run_id,
            "sample_id": sample_id,
            "epoch": epoch,
            "area": scenario.area if scenario else "unknown",
            "overall": overall_pass(row),
            "fact_pass": row["fact_pass"],
            "judge_pass": row["judge_pass"],
            "error": row["error"],
            "transcript": row["transcript"],
            "fact_detail": json.loads(row["fact_detail"]) if row["fact_detail"] else None,
            "scenario": scenario.model_dump(
                include={"persona", "turns", "must_say", "must_not_say", "source_note", "seed_id"}
            )
            if scenario
            else None,
            "scores": [
                {k: sc[k] for k in ("rubric", "passed", "rationale", "judge_version")}
                for sc in s.scores(run_id)
                if sc["sample_id"] == sample_id and sc["epoch"] == epoch
            ],
            "citations": [
                {"cite": c, "display": display_citation(c), "text": cited_text(c, children=True)}
                for c in cites
            ],
        }

    @api.get("/api/label-queue")
    def label_queue(
        rubric: Rubric = "factual", run: str | None = None, limit: int = Query(20, ge=1, le=500)
    ) -> list[dict]:
        """Unlabeled, judged results for one rubric. Blind: no judge verdict or rationale."""
        s = store()
        run_rows = [get_run(s, run)] if run else s.runs()
        done = {(x["run_id"], x["sample_id"], x["epoch"]) for x in s.labels(rubric=rubric)}
        guide = rubric_guide(rubric)
        todo = []
        for run_row in run_rows:
            rid = run_row["id"]
            pack = {x.id: x for x in load_pack(run_row["pack"])}
            judged = {
                (x["sample_id"], x["epoch"])
                for x in s.scores(rid, rubric)
                if x["passed"] is not None
            }
            for r in s.results(rid):
                key = (r["sample_id"], r["epoch"])
                if r["error"] or key not in judged or (rid, *key) in done:
                    continue
                sc = pack.get(r["sample_id"])
                todo.append(
                    {
                        "run_id": rid,
                        "sample_id": r["sample_id"],
                        "epoch": r["epoch"],
                        "rubric": rubric,
                        "transcript": r["transcript"],
                        "citations": [
                            {
                                "cite": c,
                                "display": display_citation(c),
                                "text": cited_text(c, children=True),
                            }
                            for c in (sc.citations if sc else [])
                        ],
                        "source_note": sc.source_note if sc else "",
                        "key_facts": [f.any_of for f in sc.must_say] if sc else [],
                        "rubric_text": guide,
                    }
                )
        todo.sort(key=lambda i: _shuffle_key(i["run_id"], i["sample_id"], i["epoch"]))
        return todo[:limit]

    @api.post("/api/labels", status_code=201)
    def post_label(body: LabelIn) -> dict:
        s = store()
        get_run(s, body.run_id)
        if s.result(body.run_id, body.sample_id, body.epoch) is None:
            raise HTTPException(404, f"no result {body.sample_id} in run {body.run_id}")
        s.save_label(body.run_id, body.sample_id, body.epoch, body.rubric, body.human_pass)
        return body.model_dump()

    @api.get("/api/labels")
    def labels(rubric: Rubric | None = None, run: str | None = None) -> list[dict]:
        rows = store().labels(rubric=rubric, run_id=run)
        return [dict(r) | {"human_pass": bool(r["human_pass"])} for r in rows]

    @api.get("/api/calibration")
    def calibration() -> dict:
        s = store()
        return calibration_by_rubric({r: s.judged_with_labels(r) for r in RUBRIC_NAMES})

    return api
