from examiner.scenarios.facts import check_facts, fact_present
from examiner.scenarios.schema import Fact, Scenario

FEE = Fact(id="od-34", any_of=["$34"])


def test_fact_match_boundaries():
    assert fact_present(FEE, "Our fee is $34.")
    assert fact_present(FEE, "It costs $34.00 per item")
    assert fact_present(FEE, "($34)")
    assert not fact_present(FEE, "It costs $340")
    assert not fact_present(FEE, "It costs $34.50")
    assert fact_present(Fact(id="d", any_of=["60 days"]), "You have 60 Days to report")
    assert not fact_present(Fact(id="d", any_of=["60 days"]), "within 160 days")


def test_fact_any_of_alternatives():
    nsf = Fact(id="nsf", any_of=["no NSF fee", "don't charge an NSF"])
    assert fact_present(nsf, "We don't charge an NSF fee.")
    assert not fact_present(nsf, "The NSF fee is $35.")


def test_check_facts_missing_and_forbidden():
    s = Scenario(
        id="fees-x",
        area="fees",
        persona="p",
        turns=["q"],
        must_say=[FEE],
        must_not_say=[Fact(id="od-35", any_of=["$35"])],
        citations=["fee:overdraft"],
        source_note="n",
    )
    bad = check_facts(s, "The fee is $35.")
    assert bad.missing == ["od-34"] and bad.forbidden == ["od-35"] and not bad.passed
    good = check_facts(s, "The fee is $34.")
    assert good.passed and good.missing == [] and good.forbidden == []
