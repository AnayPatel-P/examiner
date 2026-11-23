from collections import Counter

from examiner.batch import select_batch


def cand(run: str, variant: str, sid: str, rubric: str, judge: int) -> dict:
    return {
        "run_id": run,
        "variant": variant,
        "sample_id": sid,
        "epoch": 1,
        "rubric": rubric,
        "judge_pass": judge,
    }


def pool() -> list[dict]:
    out = []
    for variant, fail_every in (("naive", 2), ("guarded", 10), ("misinformed", 1)):
        for i in range(40):
            for rubric in ("factual", "disclosure", "commitments"):
                judge = 0 if i % fail_every == 0 else 1
                out.append(cand(variant + "1", variant, f"s-{i:03}", rubric, judge))
    return out


def test_quota_per_rubric_and_both_classes():
    items = select_batch(pool(), per_rubric=34, seed="t")
    by_rubric = Counter(i["rubric"] for i in items)
    assert by_rubric == {"factual": 34, "disclosure": 34, "commitments": 34}
    for rubric in by_rubric:
        verdicts = Counter(i["judge_pass"] for i in items if i["rubric"] == rubric)
        assert verdicts[0] >= 10 and verdicts[1] >= 10
        variants = Counter(i["variant"] for i in items if i["rubric"] == rubric)
        assert set(variants) == {"naive", "guarded", "misinformed"}


def test_short_cells_are_topped_up_from_others():
    # misinformed has no passes at all: the batch still reaches its size.
    items = select_batch(pool(), per_rubric=34, seed="t")
    assert not any(i["variant"] == "misinformed" and i["judge_pass"] == 1 for i in items)
    assert len(items) == 102


def test_deterministic_and_seed_sensitive():
    a = select_batch(pool(), per_rubric=20, seed="x")
    assert a == select_batch(list(reversed(pool())), per_rubric=20, seed="x")
    assert a != select_batch(pool(), per_rubric=20, seed="y")


def test_no_duplicates_and_order_is_mixed():
    items = select_batch(pool(), per_rubric=34, seed="t")
    keys = [(i["run_id"], i["sample_id"], i["epoch"], i["rubric"]) for i in items]
    assert len(set(keys)) == len(keys)
    # Rubrics interleave rather than coming in blocks.
    assert len({i["rubric"] for i in items[:10]}) > 1


def test_small_pool_takes_everything():
    small = [cand("r", "naive", "a", "factual", 1), cand("r", "naive", "b", "factual", 0)]
    assert len(select_batch(small, per_rubric=34, seed="t")) == 2
