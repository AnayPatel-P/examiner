"""Run-level judge budget.

Inspect's cost_limit only covers the solver, and the judge runs in scorers, so the
budget is enforced here: checked before each judge call, charged after it.
Up to `max_samples` calls already in flight can finish past the limit.
"""

from dataclasses import dataclass, field

from inspect_ai.model import ModelCost, ModelUsage

from examiner.pricing import PRICES, usage_cost


@dataclass
class JudgeBudget:
    limit_usd: float | None
    prices: dict[str, ModelCost] = field(default_factory=lambda: dict(PRICES))
    spent_usd: float = 0.0
    unpriced_calls: int = 0

    def exhausted(self) -> bool:
        return self.limit_usd is not None and self.spent_usd >= self.limit_usd

    def charge(self, model: str, usage: ModelUsage | None) -> None:
        price = self.prices.get(model)
        if price is None or usage is None:
            self.unpriced_calls += 1
            return
        self.spent_usd += usage_cost(usage, price)
