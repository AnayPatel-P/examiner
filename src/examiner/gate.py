"""Regression gate: fail when the guarded bot's overall pass rate drops.

Two rules, both on the overall check (fact check AND every judge rubric):
- a hard floor, so a slow slide across many accepted baselines still trips it;
- a maximum drop from the committed baseline, set just above run-to-run noise
  (two identical guarded runs differed on 6 of 127 scenarios, D16).
A run with too few scored samples (errors, exhausted judge budget) fails too,
so missing judgments cannot pass the gate.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

BASELINE = Path("gate/baseline.json")
FLOOR = 0.85
MAX_DROP = 0.04
MIN_COVERAGE = 0.95


@dataclass
class GateResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    summary: str = ""


def gate_check(
    current: dict,
    baseline: dict,
    floor: float = FLOOR,
    max_drop: float = MAX_DROP,
    min_coverage: float = MIN_COVERAGE,
) -> GateResult:
    """`current` and `baseline` carry variant, pack, passed, n (scored) and, for current,
    optionally total (all samples). Rates are passed / n."""
    reasons = []
    for k in ("variant", "pack"):
        if current.get(k) != baseline.get(k):
            reasons.append(f"{k} {current.get(k)!r} does not match baseline {baseline.get(k)!r}")
    n = current.get("n") or 0
    if n == 0:
        return GateResult(False, [*reasons, "no scored samples"], "no data")
    total = current.get("total") or baseline.get("n") or n
    if n / total < min_coverage:
        reasons.append(f"only {n}/{total} samples scored (need {min_coverage:.0%})")
    rate = current["passed"] / n
    base = baseline["passed"] / baseline["n"]
    if rate < floor:
        reasons.append(f"overall {rate:.1%} is below the floor {floor:.0%}")
    if rate < base - max_drop:
        reasons.append(
            f"overall {rate:.1%} dropped {100 * (base - rate):.1f} pts from baseline {base:.1%} "
            f"(allowed {100 * max_drop:.0f})"
        )
    summary = f"overall {current['passed']}/{n} = {rate:.1%} vs baseline {base:.1%}"
    return GateResult(not reasons, reasons, summary)


def load_baseline(path: Path = BASELINE) -> dict:
    base = json.loads(Path(path).read_text())
    if not base.get("n") or base.get("variant") != "guarded":
        raise ValueError(f"{path}: baseline must be a guarded run with scored samples")
    return base
