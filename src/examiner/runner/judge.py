"""LLM judge scorer (grader model role)."""

import json
import re
from pathlib import Path

from inspect_ai.model import get_model
from inspect_ai.scorer import CORRECT, INCORRECT, Score, Scorer, Target, accuracy, scorer
from inspect_ai.solver import TaskState

from examiner.meridian.bank import load_fee_schedule
from examiner.runner.solver import transcript_text

JUDGE_VERSION = "factual-v1"
RUBRIC_PATH = Path(__file__).resolve().parents[1] / "rubrics" / "factual.md"


def build_judge_prompt(scenario: dict, transcript: str) -> str:
    return RUBRIC_PATH.read_text().format(
        fee_schedule=json.dumps(load_fee_schedule(), indent=2),
        citation=scenario["citation"],
        source_note=scenario["source_note"],
        transcript=transcript,
    )


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


@scorer(metrics=[accuracy()])
def judge() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        scenario = state.metadata["scenario"]
        prompt = build_judge_prompt(scenario, transcript_text(state.messages))
        output = await get_model(role="grader").generate(prompt)
        meta = {
            "judge_version": JUDGE_VERSION,
            "rubric": "factual",
            "citation": scenario["citation"],
        }
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
