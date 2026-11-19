"""Deterministic fact-check scorer."""

from inspect_ai.scorer import CORRECT, INCORRECT, Score, Scorer, Target, accuracy, scorer
from inspect_ai.solver import TaskState

from examiner.scenarios.facts import check_facts
from examiner.scenarios.schema import Scenario


@scorer(metrics=[accuracy()])
def fact_check() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        scenario = Scenario.model_validate(state.metadata["scenario"])
        bot_text = "\n".join(m.text for m in state.messages if m.role == "assistant")
        result = check_facts(scenario, bot_text)
        parts = []
        if result.missing:
            parts.append("missing: " + ", ".join(result.missing))
        if result.forbidden:
            parts.append("forbidden: " + ", ".join(result.forbidden))
        return Score(
            value=CORRECT if result.passed else INCORRECT,
            explanation="; ".join(parts) or "all facts ok",
            metadata={
                "missing": result.missing,
                "forbidden": result.forbidden,
                "citation": scenario.citation_display,
            },
        )

    return score
