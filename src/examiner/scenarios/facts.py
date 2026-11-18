"""Deterministic must_say / must_not_say checks."""

import re
from dataclasses import dataclass, field

from examiner.scenarios.schema import Fact, Scenario

# Not preceded by a word char, $ or "."; not followed by a digit or a non-zero decimal.
# So "$34" matches "$34." and "$34.00" but not "$340" or "$34.50".
_BEFORE = r"(?<![\w$.])"
_AFTER = r"(?!\d)(?!\.\d*[1-9])"


def _pattern(alt: str) -> re.Pattern[str]:
    return re.compile(_BEFORE + re.escape(alt) + _AFTER, re.IGNORECASE)


def fact_present(fact: Fact, text: str) -> bool:
    return any(_pattern(alt).search(text) for alt in fact.any_of)


@dataclass
class FactResult:
    missing: list[str] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.missing and not self.forbidden


def check_facts(scenario: Scenario, transcript: str) -> FactResult:
    return FactResult(
        missing=[f.id for f in scenario.must_say if not fact_present(f, transcript)],
        forbidden=[f.id for f in scenario.must_not_say if fact_present(f, transcript)],
    )
