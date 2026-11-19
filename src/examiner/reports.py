"""Aggregates over stored results, shared by the CLI and the API."""

import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from functools import cache
from typing import Any

from examiner.scenarios.schema import RUBRIC_NAMES, load_pack

Row = Mapping[str, Any] | sqlite3.Row

CHECKS = ["overall", "fact", "judge", *RUBRIC_NAMES]


def overall_pass(row: Row) -> int | None:
    """Pass only if the fact check and every judged rubric passed; NULL if anything is missing."""
    if row["error"] or row["fact_pass"] is None or row["judge_pass"] is None:
        return None
    return int(bool(row["fact_pass"]) and bool(row["judge_pass"]))


@cache
def areas_for(pack: str) -> dict[str, str]:
    try:
        return {s.id: s.area for s in load_pack(pack)}
    except (FileNotFoundError, ValueError):
        return {}


def _cell(passed: int, n: int) -> dict:
    return {"passed": passed, "n": n, "rate": passed / n if n else None}


def check_value(row: Row, check: str, rubrics: Mapping[str, int | None]) -> int | None:
    if check == "overall":
        return overall_pass(row)
    if row["error"]:
        return None
    if check == "fact":
        return row["fact_pass"]
    if check == "judge":
        return row["judge_pass"]
    return rubrics.get(check)


def rubric_map(scores: Iterable[Row]) -> dict[tuple[str, int], dict[str, int | None]]:
    out: dict[tuple[str, int], dict[str, int | None]] = {}
    for s in scores:
        out.setdefault((s["sample_id"], s["epoch"]), {})[s["rubric"]] = s["passed"]
    return out


def scorecard(
    results: Iterable[Row], scores: Iterable[Row], areas: Mapping[str, str]
) -> dict[str, dict]:
    """{area: {check: {"passed", "n", "rate"}, "errors": n}}, areas sorted, then "all"."""
    by_key = rubric_map(scores)
    counts: dict[str, dict[str, list[int]]] = {}
    errors: dict[str, int] = {}
    for r in results:
        area = areas.get(r["sample_id"], "unknown")
        for a in (area, "all"):
            counts.setdefault(a, {c: [0, 0] for c in CHECKS})
            errors.setdefault(a, 0)
            if r["error"]:
                errors[a] += 1
                continue
            rubrics = by_key.get((r["sample_id"], r["epoch"]), {})
            for c in CHECKS:
                v = check_value(r, c, rubrics)
                if v is not None:
                    counts[a][c][0] += int(v)
                    counts[a][c][1] += 1
    order = sorted(a for a in counts if a != "all") + (["all"] if "all" in counts else [])
    return {a: {c: _cell(*counts[a][c]) for c in CHECKS} | {"errors": errors[a]} for a in order}


def run_summary(run: Row, results: Sequence[Row]) -> dict:
    keys = [
        "id",
        "target",
        "variant",
        "pack",
        "started_at",
        "judge_version",
        "cost_usd",
        "target_cost_usd",
        "wall_seconds",
    ]
    out = {k: run[k] for k in keys}
    out["n"] = len(results)
    out["errors"] = sum(1 for r in results if r["error"])
    for check in ("overall", "fact", "judge"):
        vals = [v for r in results if (v := check_value(r, check, {})) is not None]
        out[check] = _cell(sum(vals), len(vals))
    return out
