"""Aggregates over stored results, shared by the CLI and the API."""

import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import yaml

from examiner.scenarios.schema import RUBRIC_NAMES, Scenario, load_pack

Row = Mapping[str, Any] | sqlite3.Row

CHECKS = ["overall", "fact", "judge", *RUBRIC_NAMES]


def kleene_and(values: Iterable[int | None]) -> int | None:
    """0 if any value is a definite fail, else NULL if any is missing, else 1."""
    vals = list(values)
    if any(v == 0 for v in vals):
        return 0
    if not vals or any(v is None for v in vals):
        return None
    return 1


def overall_pass(row: Row, rubrics: Mapping[str, int | None] | None = None) -> int | None:
    """Fact check AND every judged rubric. A definite fail counts even if another part is
    missing; NULL only when nothing failed and something is missing. Errored samples are NULL."""
    if row["error"]:
        return None
    return kleene_and([row["fact_pass"], _judge(row, rubrics or {})])


def _judge(row: Row, rubrics: Mapping[str, int | None]) -> int | None:
    return kleene_and(rubrics.values()) if rubrics else row["judge_pass"]


def scenarios_for(pack: str) -> dict[str, Scenario]:
    """Scenarios by id, or {} if the pack is gone or unreadable (old runs stay browsable)."""
    try:
        return {s.id: s for s in load_pack(pack)}
    except (OSError, ValueError, yaml.YAMLError):
        return {}


def areas_for(pack: str) -> dict[str, str]:
    return {sid: s.area for sid, s in scenarios_for(pack).items()}


def _cell(passed: int, n: int) -> dict:
    return {"passed": passed, "n": n, "rate": passed / n if n else None}


def check_value(row: Row, check: str, rubrics: Mapping[str, int | None]) -> int | None:
    if check == "overall":
        return overall_pass(row, rubrics)
    if row["error"]:
        return None
    if check == "fact":
        return row["fact_pass"]
    if check == "judge":
        return _judge(row, rubrics)
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


def run_summary(run: Row, results: Sequence[Row], scores: Iterable[Row] = ()) -> dict:
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
    by_key = rubric_map(scores)
    for check in ("overall", "fact", "judge"):
        vals = [
            v
            for r in results
            if (v := check_value(r, check, by_key.get((r["sample_id"], r["epoch"]), {})))
            is not None
        ]
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


# Official headings of the Reg E sections the packs cite (12 CFR part 1005).
SECTION_TITLES = {
    "1005.6": "Liability of consumer for unauthorized transfers",
    "1005.8": "Change in terms notice; error resolution notice",
    "1005.9": "Receipts at electronic terminals; periodic statements",
    "1005.10": "Preauthorized transfers",
    "1005.11": "Procedures for resolving errors",
    "1005.17": "Requirements for overdraft services",
    "1005.33": "Procedures for resolving errors (remittance transfers)",
    "1005.34": "Procedures for cancellation and refund of remittance transfers",
}
FEE_SECTION = "fee schedule"


def section_of(cite: str) -> str:
    if cite.startswith("fee:"):
        return FEE_SECTION
    para = cite.removeprefix("12 CFR ").strip()
    return para.split("(")[0]


def failure_modes(row: Row, rubrics: Mapping[str, int | None]) -> list[str]:
    """How a scored result failed: fact_missing, fact_forbidden and/or each failed rubric."""
    import json

    modes = []
    detail = json.loads(row["fact_detail"]) if row["fact_detail"] else {}
    if row["fact_pass"] == 0:
        if detail.get("missing"):
            modes.append("fact_missing")
        if detail.get("forbidden"):
            modes.append("fact_forbidden")
    modes += [r for r in RUBRIC_NAMES if rubrics.get(r) == 0]
    return modes


def failure_taxonomy(
    results: Iterable[Row], scores: Iterable[Row], citations: Mapping[str, Sequence[str]]
) -> dict:
    """Which cited clauses fail, how often, and how. A scenario counts under each clause it
    cites. Errored and unscored results are left out."""
    by_key = rubric_map(scores)
    clauses: dict[str, dict] = {}
    sections: dict[str, dict] = {}
    modes_all: dict[str, int] = {}
    scored = failed = 0
    for r in results:
        rubrics = by_key.get((r["sample_id"], r["epoch"]), {})
        overall = overall_pass(r, rubrics)
        if overall is None:
            continue
        scored += 1
        modes = failure_modes(r, rubrics) if overall == 0 else []
        failed += overall == 0
        for m in modes:
            modes_all[m] = modes_all.get(m, 0) + 1
        cites = list(citations.get(r["sample_id"], []))
        for cite in cites:
            row = clauses.setdefault(
                cite,
                {
                    "citation": cite,
                    "section": section_of(cite),
                    "section_title": SECTION_TITLES.get(section_of(cite), ""),
                    "n": 0,
                    "failed": 0,
                    "modes": {},
                    "failing": [],
                },
            )
            row["n"] += 1
            if overall == 0:
                row["failed"] += 1
                row["failing"].append(r["sample_id"])
                for m in modes:
                    row["modes"][m] = row["modes"].get(m, 0) + 1
        for sec in {section_of(c) for c in cites}:
            s = sections.setdefault(
                sec,
                {"section": sec, "section_title": SECTION_TITLES.get(sec, ""), "n": 0, "failed": 0},
            )
            s["n"] += 1
            s["failed"] += overall == 0
    order = lambda d: (-d["failed"], d.get("citation", d["section"]))  # noqa: E731
    return {
        "scored_scenarios": scored,
        "failed_scenarios": failed,
        "modes": modes_all,
        "sections": sorted(sections.values(), key=order),
        "clauses": sorted(clauses.values(), key=order),
    }


def run_ops(run: Row, results: Sequence[Row]) -> dict:
    """Cost and latency for one run. Latency is time waiting on the bot, per scenario."""
    import math
    import statistics

    lat = sorted(r["latency_s"] for r in results if r["latency_s"] is not None)
    costs = [run["cost_usd"], run["target_cost_usd"]]
    # A missing part makes the total unknown, not smaller.
    total = None if any(c is None for c in costs) else round(sum(costs), 6)
    n = len(results)
    return {
        "n": n,
        "judge_cost_usd": run["cost_usd"],
        "target_cost_usd": run["target_cost_usd"],
        "total_cost_usd": total,
        "cost_per_scenario_usd": round(total / n, 6) if total is not None and n else None,
        "wall_seconds": run["wall_seconds"],
        "latency_p50_s": round(statistics.median(lat), 3) if lat else None,
        "latency_p95_s": round(lat[math.ceil(0.95 * len(lat)) - 1], 3) if lat else None,
        "latency_mean_s": round(statistics.fmean(lat), 3) if lat else None,
    }
