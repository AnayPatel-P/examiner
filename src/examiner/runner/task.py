"""The Examiner Inspect task."""

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.scorer import Scorer

from examiner.runner.scorers import fact_check
from examiner.runner.solver import http_target
from examiner.scenarios.schema import Scenario, load_pack


def scenario_to_sample(s: Scenario) -> Sample:
    return Sample(id=s.id, input=s.turns[0], metadata={"scenario": s.model_dump()})


@task
def examiner_task(
    pack: str = "smoke",
    target: str = "http://localhost:8001",
    variant: str = "naive",
    use_judge: bool = True,
) -> Task:
    scorers: list[Scorer] = [fact_check()]
    return Task(
        dataset=MemoryDataset([scenario_to_sample(s) for s in load_pack(pack)], name=pack),
        solver=http_target(target, variant),
        scorer=scorers,
        metadata={"pack": pack, "target": target, "variant": variant},
    )
