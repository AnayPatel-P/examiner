from examiner.reports import overall_pass, scorecard


def test_overall_pass_null_rules():
    assert overall_pass({"fact_pass": 1, "judge_pass": 1, "error": None}) == 1
    assert overall_pass({"fact_pass": 0, "judge_pass": 1, "error": None}) == 0
    assert overall_pass({"fact_pass": 1, "judge_pass": 0, "error": None}) == 0
    assert overall_pass({"fact_pass": 1, "judge_pass": None, "error": None}) is None
    assert overall_pass({"fact_pass": None, "judge_pass": 1, "error": None}) is None
    assert overall_pass({"fact_pass": 1, "judge_pass": 1, "error": "x"}) is None


def test_scorecard_by_area_and_all():
    results = [
        {"sample_id": "fees-001", "epoch": 1, "fact_pass": 1, "judge_pass": 1, "error": None},
        {"sample_id": "fees-002", "epoch": 1, "fact_pass": 0, "judge_pass": 1, "error": None},
        {"sample_id": "rege-001", "epoch": 1, "fact_pass": 1, "judge_pass": 0, "error": None},
        {
            "sample_id": "rege-002",
            "epoch": 1,
            "fact_pass": None,
            "judge_pass": None,
            "error": "boom",
        },
    ]
    scores = [
        {"sample_id": "fees-001", "epoch": 1, "rubric": "factual", "passed": 1},
        {"sample_id": "fees-002", "epoch": 1, "rubric": "factual", "passed": 1},
        {"sample_id": "rege-001", "epoch": 1, "rubric": "factual", "passed": 0},
        {"sample_id": "fees-001", "epoch": 1, "rubric": "disclosure", "passed": None},
    ]
    areas = {"fees-001": "fees", "fees-002": "fees", "rege-001": "reg_e", "rege-002": "reg_e"}
    card = scorecard(results, scores, areas)
    assert card["fees"]["fact"] == {"passed": 1, "n": 2, "rate": 0.5}
    assert card["fees"]["factual"] == {"passed": 2, "n": 2, "rate": 1.0}
    assert card["fees"]["disclosure"] == {"passed": 0, "n": 0, "rate": None}
    # fees-001 has an unjudged rubric and nothing failed -> unscored; fees-002 fact fail
    assert card["fees"]["overall"] == {"passed": 0, "n": 1, "rate": 0.0}
    assert card["reg_e"]["fact"]["n"] == 1 and card["reg_e"]["errors"] == 1
    assert card["all"]["overall"] == {"passed": 0, "n": 2, "rate": 0.0}
    assert card["all"]["judge"] == {"passed": 1, "n": 2, "rate": 0.5}
    assert card["all"]["errors"] == 1
    assert list(card)[-1] == "all"


def test_scorecard_unknown_area():
    results = [{"sample_id": "zzz", "epoch": 1, "fact_pass": 1, "judge_pass": 1, "error": None}]
    card = scorecard(results, [], {})
    assert card["unknown"]["overall"]["passed"] == 1


def test_overall_definite_fail_beats_null():
    # fact 0 with an unjudged rubric is still a fail (Kleene AND)
    assert overall_pass({"fact_pass": 0, "judge_pass": None, "error": None}) == 0


def test_judge_fail_on_one_rubric_beats_null_on_another():
    from examiner.reports import check_value

    row = {"fact_pass": 1, "judge_pass": None, "error": None}
    rubrics = {"factual": 0, "disclosure": None, "commitments": 1}
    assert check_value(row, "judge", rubrics) == 0
    assert check_value(row, "overall", rubrics) == 0
    assert check_value(row, "judge", {"factual": 1, "disclosure": None}) is None
