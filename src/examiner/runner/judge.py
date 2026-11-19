"""LLM judge scorers, one per rubric (grader model role)."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from inspect_ai.model import ChatMessageSystem, ChatMessageUser, GenerateConfig, get_model
from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    NOANSWER,
    Score,
    Scorer,
    Target,
    accuracy,
    scorer,
)
from inspect_ai.solver import TaskState

from examiner.meridian.bank import load_fee_schedule
from examiner.runner.budget import JudgeBudget
from examiner.runner.solver import transcript_text
from examiner.scenarios.schema import display_citation

RUBRIC_DIR = Path(__file__).resolve().parents[1] / "rubrics"
SPLIT = "=== USER ==="
JUDGE_CONFIG = GenerateConfig(reasoning_effort="medium", max_retries=3)


@dataclass(frozen=True)
class Rubric:
    name: str
    version: str

    @property
    def path(self) -> Path:
        return RUBRIC_DIR / f"{self.name}.md"


RUBRICS = {
    r.name: r
    for r in (
        Rubric("factual", "factual-v2"),
        Rubric("disclosure", "disclosure-v1"),
        Rubric("commitments", "commitments-v1"),
    )
}
JUDGE_VERSION = RUBRICS["factual"].version


def rubric_guide(name: str) -> str:
    """The rubric section the judge sees, verbatim, for human labelers."""
    rubric = RUBRICS[name]
    system = rubric.path.read_text().split(SPLIT)[0]
    start = system.index("## Rubric")
    return system[start:].replace("{version}", rubric.version).strip()


def rules_block(citations: list[str]) -> str:
    from examiner.scenarios.lint import cited_text

    return "\n".join(f"- {display_citation(c)}: {cited_text(c, children=True)}" for c in citations)


def key_facts_block(scenario: dict) -> str:
    facts = scenario.get("must_say") or []
    if not facts:
        return "- (none: this conversation has no required fact; PASS unless the reply is empty)"
    return "\n".join(
        f"- {f['id']}: any of {', '.join(repr(a) for a in f['any_of'])}" for f in facts
    )


def build_judge_messages(rubric: str, scenario: dict, transcript: str) -> tuple[str, str]:
    r = RUBRICS[rubric]
    system, user = r.path.read_text().split(SPLIT)
    system = system.format(
        version=r.version, fee_schedule=json.dumps(load_fee_schedule(), indent=2)
    ).strip()
    fields = {
        "rules": rules_block(scenario["citations"]),
        "source_note": scenario["source_note"],
        "transcript": transcript,
    }
    if rubric == "disclosure":
        fields["key_facts"] = key_facts_block(scenario)
    return system, user.format(**fields).strip()


def build_judge_prompt(scenario: dict, transcript: str, rubric: str = "factual") -> str:
    return "\n\n".join(build_judge_messages(rubric, scenario, transcript))


def parse_verdict(text: str) -> tuple[str, str] | None:
    for match in reversed(re.findall(r"\{[^{}]*\}", text)):
        try:
            data = json.loads(match)
        except json.JSONDecodeError:
            continue
        verdict = str(data.get("verdict", "")).strip().lower()
        if verdict in ("pass", "fail"):
            return verdict, str(data.get("rationale", ""))
    return None


def judge(rubric: str = "factual", budget: JudgeBudget | None = None) -> Scorer:
    r = RUBRICS[rubric]

    @scorer(metrics=[accuracy()], name=f"judge_{rubric}")
    def _judge() -> Scorer:
        async def score(state: TaskState, target: Target) -> Score:
            scenario = state.metadata["scenario"]
            meta = {
                "judge_version": r.version,
                "rubric": rubric,
                "citation": "; ".join(display_citation(c) for c in scenario["citations"]),
            }
            if rubric not in scenario.get("rubrics", ["factual"]):
                return Score(value=NOANSWER, metadata={**meta, "skipped": True})
            if budget is not None and budget.exhausted():
                return Score(
                    value=INCORRECT,
                    reason="budget_exhausted",
                    explanation=f"judge budget ${budget.limit_usd} used up",
                    metadata={**meta, "rationale": ""},
                )
            system, user = build_judge_messages(rubric, scenario, transcript_text(state.messages))
            model = get_model(role="grader")
            try:
                output = await model.generate(
                    [ChatMessageSystem(content=system), ChatMessageUser(content=user)],
                    config=JUDGE_CONFIG,
                )
            except Exception as e:  # one rubric's API failure must not sink the sample
                return Score(
                    value=INCORRECT,
                    reason="grader_failed",
                    explanation=f"{type(e).__name__}: {e}",
                    metadata={**meta, "rationale": ""},
                )
            if budget is not None:
                budget.charge(str(model), output.usage)
            parsed = parse_verdict(output.completion)
            if parsed is None:
                return Score(
                    value=INCORRECT,
                    reason="grader_failed",
                    explanation=output.completion,
                    metadata={**meta, "rationale": ""},
                )
            verdict, rationale = parsed
            return Score(
                value=CORRECT if verdict == "pass" else INCORRECT,
                explanation=rationale,
                metadata={**meta, "rationale": rationale},
            )

        return score

    return _judge()
