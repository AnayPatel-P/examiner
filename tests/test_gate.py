from examiner.gate import gate_check

BASE = {"variant": "guarded", "pack": "v1", "passed": 115, "n": 127, "rate": 115 / 127}


def cur(passed: int, n: int = 127, variant: str = "guarded", pack: str = "v1") -> dict:
    return {
        "variant": variant,
        "pack": pack,
        "passed": passed,
        "n": n,
        "rate": passed / n if n else None,
    }


def test_passes_at_baseline_and_within_noise():
    assert gate_check(cur(115), BASE, floor=0.85, max_drop=0.04).ok
    assert gate_check(cur(111), BASE, floor=0.85, max_drop=0.04).ok  # -3.1 pts


def test_fails_on_drop_beyond_margin():
    r = gate_check(cur(109), BASE, floor=0.85, max_drop=0.04)  # -4.7 pts, still above floor
    assert not r.ok and any("baseline" in m for m in r.reasons)


def test_fails_below_floor():
    r = gate_check(cur(100), {**BASE, "passed": 104, "rate": 104 / 127}, floor=0.85, max_drop=0.1)
    assert not r.ok and any("floor" in m for m in r.reasons)


def test_refuses_mismatched_or_empty_runs():
    assert not gate_check(cur(115, variant="naive"), BASE, floor=0.85, max_drop=0.04).ok
    assert not gate_check(cur(115, pack="smoke"), BASE, floor=0.85, max_drop=0.04).ok
    assert not gate_check(cur(0, n=0), BASE, floor=0.85, max_drop=0.04).ok


def test_coverage_shortfall_fails():
    # Too many unscored samples (errors or budget) cannot sneak through as a pass.
    r = gate_check(
        {**cur(110, n=115), "total": 127}, BASE, floor=0.85, max_drop=0.04, min_coverage=0.95
    )
    assert not r.ok and any("scored" in m for m in r.reasons)


def test_load_baseline_rejects_wrong_variant_or_empty(tmp_path):
    import json

    import pytest

    from examiner.gate import load_baseline

    for bad in ({**BASE, "variant": "naive"}, {**BASE, "n": 0}):
        f = tmp_path / "b.json"
        f.write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            load_baseline(f)
