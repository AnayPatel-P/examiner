"""Pick a calibration labeling batch that mixes passes and failures.

The spike's kappa was 0.00 because every human label was a pass (D12). A batch is
stratified, per rubric, across (bot variant, judge verdict) cells with equal quotas.
A cell that runs short is topped up from the others, so the batch still reaches its
size. Selection uses the judge verdict, but the labeler never sees it, and the final
order is a seeded shuffle across rubrics.

Because the sample is balanced rather than drawn at each run's natural pass rate,
the kappa it yields describes agreement on a mixed set, not one run's population.
"""

import hashlib
from collections import defaultdict


def _rank(seed: str, item: dict) -> str:
    key = f"{seed}/{item['run_id']}/{item['sample_id']}/{item['epoch']}/{item['rubric']}"
    return hashlib.sha256(key.encode()).hexdigest()


def select_batch(candidates: list[dict], per_rubric: int, seed: str) -> list[dict]:
    """Candidates carry run_id, variant, sample_id, epoch, rubric and judge_pass (0/1)."""
    by_rubric: dict[str, dict[tuple, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for c in candidates:
        by_rubric[c["rubric"]][(c["variant"], c["judge_pass"])].append(c)

    chosen: list[dict] = []
    for rubric in sorted(by_rubric):
        cells = {k: sorted(v, key=lambda c: _rank(seed, c)) for k, v in by_rubric[rubric].items()}
        taken: list[dict] = []
        # Round-robin one item per cell until the quota is met or every cell is empty.
        order = sorted(cells)
        while len(taken) < per_rubric and any(cells[k] for k in order):
            for k in order:
                if cells[k] and len(taken) < per_rubric:
                    taken.append(cells[k].pop(0))
        chosen.extend(taken)
    return sorted(chosen, key=lambda c: _rank(seed + "/order", c))
