from collections import Counter

from examiner.scenarios.lint import lint_pack
from examiner.scenarios.schema import load_pack

SEEDS = [s for s in load_pack("v1") if s.seed_id is None]


def test_v1_seed_counts():
    counts = Counter(s.area for s in SEEDS)
    assert counts["reg_e"] >= 30 and counts["fees"] >= 30


def test_v1_lint_clean():
    assert lint_pack("v1") == {}


def test_v1_reg_e_seeds_cite_reg_e():
    for s in SEEDS:
        if s.area == "reg_e":
            assert any(c.startswith("12 CFR 1005.") for c in s.citations), s.id


def test_every_seed_has_a_fact_check():
    assert all(s.must_say or s.must_not_say for s in SEEDS)


def test_multi_turn_seeds_present():
    assert sum(len(s.turns) > 1 for s in SEEDS) >= 6


def test_fee_schedule_extended():
    from examiner.meridian.bank import load_fee_schedule

    fees = load_fee_schedule()
    assert fees["wire_international_outgoing"]["fee_usd"] == 45
    assert fees["overdraft"]["no_fee_if_overdrawn_by_usd_or_less"] == 10


def test_v1_variants_keep_seed_ground_truth():
    pack = {s.id: s for s in load_pack("v1")}
    variants = [s for s in pack.values() if s.seed_id]
    assert len(variants) >= 55
    for v in variants:
        assert v.seed_id is not None
        seed = pack[v.seed_id]
        assert (v.must_say, v.must_not_say, v.citations, v.area) == (
            seed.must_say,
            seed.must_not_say,
            seed.citations,
            seed.area,
        ), v.id
        assert len(v.turns) == len(seed.turns), v.id


def test_v1_total_size():
    assert len(load_pack("v1")) >= 120
