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


DIFF_CATEGORIES = ["fixed", "broke", "still_fail", "still_pass", "unscored", "only_a", "only_b"]


def diff_runs(
    a_results: Iterable[Row],
    a_scores: Iterable[Row],
    b_results: Iterable[Row],
    b_scores: Iterable[Row],
    check: str = "overall",
) -> dict:
    """Compare two runs sample by sample on one check (overall, fact, judge or a rubric)."""
    if check not in CHECKS:
        raise ValueError(f"unknown check {check!r}; use one of {', '.join(CHECKS)}")

    def values(results: Iterable[Row], scores: Iterable[Row]) -> dict[tuple[str, int], int | None]:
        rubrics = rubric_map(scores)
        return {
            (r["sample_id"], r["epoch"]): check_value(
                r, check, rubrics.get((r["sample_id"], r["epoch"]), {})
            )
            for r in results
        }

    a, b = values(a_results, a_scores), values(b_results, b_scores)
    out: dict = {c: [] for c in DIFF_CATEGORIES}
    for key in sorted(a.keys() | b.keys()):
        if key not in b:
            cat = "only_a"
        elif key not in a:
            cat = "only_b"
        else:
            va, vb = a[key], b[key]
            if va is None or vb is None:
                cat = "unscored"
            else:
                cat = {(0, 1): "fixed", (1, 0): "broke", (0, 0): "still_fail"}.get(
                    (va, vb), "still_pass"
                )
        out[cat].append({"sample_id": key[0], "epoch": key[1], "a": a.get(key), "b": b.get(key)})
    out["counts"] = {c: len(out[c]) for c in DIFF_CATEGORIES}
    return out
