from examiner.runner.judge import build_judge_prompt
from examiner.scenarios.lint import lint_pack, lint_scenario
from examiner.scenarios.schema import Scenario, load_pack


def scenario(*citations: str) -> Scenario:
    return Scenario(
        id="x",
        area="reg_e",
        persona="p",
        turns=["q"],
        must_say=[],
        must_not_say=[],
        citations=list(citations),
        source_note="n",
    )


def test_lint_accepts_real_paragraph_and_fee_key():
    assert lint_scenario(scenario("12 CFR 1005.11(c)(2)(i)", "fee:overdraft")) == []


def test_lint_rejects_unknown_paragraph():
    errors = lint_scenario(scenario("12 CFR 1005.11(c)(3)(iii)"))
    assert errors and "1005.11(c)(3)(iii)" in errors[0]


def test_lint_rejects_unknown_fee_key():
    assert lint_scenario(scenario("fee:teleportation"))


def test_lint_rejects_free_text_citation():
    assert lint_scenario(scenario("Reg E somewhere"))


def test_lint_smoke_pack_clean():
    assert lint_pack("smoke") == {}


def test_citation_display_names_fee_schedule():
    s = scenario("fee:overdraft", "12 CFR 1005.6(b)(3)")
    assert s.citation_display == "Meridian fee schedule: overdraft; 12 CFR 1005.6(b)(3)"


def test_judge_prompt_includes_reg_text():
    s = next(s for s in load_pack("smoke") if s.id == "rege-provisional-credit")
    prompt = build_judge_prompt(s.model_dump(), "USER: q\nBOT: a")
    assert "Provisionally credits the consumer's account" in prompt
