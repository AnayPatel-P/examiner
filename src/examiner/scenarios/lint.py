"""Citation lint: every citation must resolve to real text."""

from examiner.meridian.bank import load_fee_schedule
from examiner.regs.ecfr import reg_text, reg_text_with_children
from examiner.scenarios.schema import Scenario, load_pack


def cited_text(cite: str, children: bool = False) -> str | None:
    """The regulation paragraph (optionally with sub-paragraphs) or fee entry a citation names."""
    if cite.startswith("12 CFR "):
        return reg_text_with_children(cite) if children else reg_text(cite)
    if cite.startswith("fee:"):
        entry = load_fee_schedule().get(cite.removeprefix("fee:"))
        return None if entry is None else str(entry)
    return None


def lint_scenario(s: Scenario) -> list[str]:
    errors = []
    for cite in s.citations:
        if not (cite.startswith("12 CFR ") or cite.startswith("fee:")):
            errors.append(f"{s.id}: citation {cite!r} must start with '12 CFR ' or 'fee:'")
        elif cited_text(cite) is None:
            errors.append(f"{s.id}: citation {cite!r} not found in Reg E snapshot or fee schedule")
    return errors


def lint_pack(name: str) -> dict[str, list[str]]:
    return {s.id: errs for s in load_pack(name) if (errs := lint_scenario(s))}
