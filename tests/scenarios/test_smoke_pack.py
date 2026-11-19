"""Realistic bot replies against the smoke pack's fact checks (review findings)."""

from examiner.scenarios.facts import check_facts
from examiner.scenarios.schema import load_pack

PACK = {s.id: s for s in load_pack("smoke")}


def passes(sid: str, reply: str) -> bool:
    return check_facts(PACK[sid], reply).passed


def test_investigation_cites_paragraph_c2():
    assert PACK["rege-investigation-time"].citations[0] == "12 CFR 1005.11(c)(2)"


def test_nsf_fee_charged_below_zero_balance_fails():
    reply = "Yes, we charge a $34 fee for returned checks if your balance goes below $0."
    assert not passes("fees-nsf", reply)


def test_nsf_correct_answer_passes():
    assert passes("fees-nsf", "No, Meridian doesn't charge NSF fees for returned items.")


def test_provisional_credit_must_mention_credit():
    reply = "We finish investigations within 10 business days and refund you if valid."
    assert not passes("rege-provisional-credit", reply)


def test_provisional_credit_right_away_contact_not_forbidden():
    reply = (
        "You can call us right away. If we need more time, we'll give you provisional "
        "credit within ten (10) business days."
    )
    assert passes("rege-provisional-credit", reply)


def test_provisional_credit_immediately_is_forbidden():
    reply = (
        "We'll credit your account immediately, and provisional credit is within 10 business days."
    )
    assert not passes("rege-provisional-credit", reply)


def test_parenthetical_numbers_pass():
    assert passes("rege-unauthorized-report-window", "You have sixty (60) days from the statement.")
    assert passes("rege-investigation-time", "We may take up to forty-five (45) days.")
