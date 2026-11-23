import json

from examiner.reports import failure_taxonomy, run_ops


def res(sid: str, fact: int | None, missing=(), forbidden=(), error=None, latency=None):
    return {
        "sample_id": sid,
        "epoch": 1,
        "fact_pass": fact,
        "judge_pass": None,
        "error": error,
        "fact_detail": json.dumps({"missing": list(missing), "forbidden": list(forbidden)}),
        "latency_s": latency,
        "target_cost_usd": 0.001,
    }


def sc(sid: str, rubric: str, passed: int | None):
    return {"sample_id": sid, "epoch": 1, "rubric": rubric, "passed": passed}


CITES = {
    "a": ["12 CFR 1005.6(b)(1)"],
    "b": ["12 CFR 1005.6(b)(2)", "12 CFR 1005.11(c)(1)"],
    "c": ["fee:overdraft"],
    "d": ["12 CFR 1005.11(c)(1)"],
}


def test_taxonomy_counts_failures_and_modes_per_clause():
    results = [
        res("a", 0, missing=["x"]),
        res("b", 1),
        res("c", 1),
        res("d", 1),
        res("e", None, error="boom"),
    ]
    scores = [
        sc("a", "factual", 0),
        sc("b", "disclosure", 0),
        sc("b", "factual", 1),
        sc("c", "factual", 1),
        sc("d", "factual", 1),
    ]
    tax = failure_taxonomy(results, scores, CITES)
    by = {row["citation"]: row for row in tax["clauses"]}
    assert by["12 CFR 1005.6(b)(1)"]["failed"] == 1
    assert by["12 CFR 1005.6(b)(1)"]["modes"] == {"fact_missing": 1, "factual": 1}
    assert (by["12 CFR 1005.11(c)(1)"]["n"], by["12 CFR 1005.11(c)(1)"]["failed"]) == (2, 1)
    assert by["fee:overdraft"]["failed"] == 0
    assert by["12 CFR 1005.6(b)(1)"]["section"] == "1005.6"
    assert "unauthorized" in by["12 CFR 1005.6(b)(1)"]["section_title"].lower()
    assert by["fee:overdraft"]["section"] == "fee schedule"
    # Sections roll up their clauses; sorted by failures, then name.
    secs = {s["section"]: s for s in tax["sections"]}
    assert (secs["1005.6"]["n"], secs["1005.6"]["failed"]) == (2, 2)
    assert (secs["1005.11"]["n"], secs["1005.11"]["failed"]) == (2, 1)
    assert tax["sections"][0]["section"] == "1005.6"
    assert tax["modes"] == {"fact_missing": 1, "factual": 1, "disclosure": 1}
    assert tax["failed_scenarios"] == 2 and tax["scored_scenarios"] == 4


def test_run_ops_latency_and_cost():
    run = {"cost_usd": 1.5, "target_cost_usd": 0.02, "wall_seconds": 200.0}
    results = [res(s, 1, latency=lat) for s, lat in zip("abcd", (1.0, 2.0, 3.0, 10.0), strict=True)]
    ops = run_ops(run, results)
    assert ops["latency_p50_s"] == 2.5
    assert ops["latency_p95_s"] == 10.0
    assert ops["total_cost_usd"] == 1.52
    assert ops["cost_per_scenario_usd"] == 0.38
    assert ops["wall_seconds"] == 200.0


def test_run_ops_without_latency():
    ops = run_ops({"cost_usd": None, "target_cost_usd": None, "wall_seconds": None}, [res("a", 1)])
    assert ops["latency_p50_s"] is None and ops["total_cost_usd"] is None
