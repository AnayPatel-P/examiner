"""Re-score stored transcripts with the current rubric, without re-running the bot.

Used after a rubric revision: the bot's replies are fixed, only the judge changes, so
kappa before and after compares like with like. Old verdicts move to `score_archive`.
"""

import asyncio
from dataclasses import dataclass, field

from inspect_ai.model import ChatMessageSystem, ChatMessageUser, Model

from examiner.reports import kleene_and, scenarios_for
from examiner.runner.budget import JudgeBudget
from examiner.runner.judge import JUDGE_CONFIG, RUBRICS, build_judge_messages, parse_verdict
from examiner.store import Store


@dataclass
class RescoreReport:
    rescored: int = 0
    changed: int = 0
    failed: list[str] = field(default_factory=list)
    skipped_budget: int = 0


async def rescore_run(
    store: Store,
    run_id: str,
    rubric: str,
    model: Model,
    budget: JudgeBudget | None = None,
    concurrency: int = 8,
) -> RescoreReport:
    run = store.run(run_id)
    if run is None:
        raise ValueError(f"no run {run_id}")
    version = RUBRICS[rubric].version
    pack = scenarios_for(run["pack"])
    old = {(s["sample_id"], s["epoch"]): s for s in store.scores(run_id, rubric)}
    todo = [
        r
        for r in store.results(run_id)
        if not r["error"] and (sc := pack.get(r["sample_id"])) is not None and rubric in sc.rubrics
    ]
    report = RescoreReport()
    sem = asyncio.Semaphore(concurrency)
    new: dict[tuple[str, int], tuple[int | None, str]] = {}

    async def one(r) -> None:
        key = (r["sample_id"], r["epoch"])
        async with sem:
            if budget is not None and budget.exhausted():
                report.skipped_budget += 1
                return
            scenario = pack[r["sample_id"]].model_dump()
            system, user = build_judge_messages(rubric, scenario, r["transcript"])
            try:
                out = await model.generate(
                    [ChatMessageSystem(content=system), ChatMessageUser(content=user)],
                    config=JUDGE_CONFIG,
                )
            except Exception as e:  # keep going; the old verdict stays
                report.failed.append(f"{r['sample_id']}: {type(e).__name__}")
                return
            if budget is not None:
                budget.charge(str(model), out.usage)
            parsed = parse_verdict(out.completion)
            if parsed is None:
                report.failed.append(f"{r['sample_id']}: unparseable")
                return
            verdict, rationale = parsed
            new[key] = (int(verdict == "pass"), rationale)

    await asyncio.gather(*(one(r) for r in todo))

    with store.db:
        for (sid, ep), (passed, rationale) in new.items():
            prev = old.get((sid, ep))
            if prev is not None and prev["judge_version"] != version:
                store.db.execute(
                    "INSERT OR REPLACE INTO score_archive "
                    "SELECT *, datetime('now') FROM score "
                    "WHERE run_id = ? AND sample_id = ? AND epoch = ? AND rubric = ?",
                    (run_id, sid, ep, rubric),
                )
                report.changed += prev["passed"] != passed
            store.db.execute(
                "INSERT OR REPLACE INTO score VALUES (?,?,?,?,?,?,?)",
                (run_id, sid, ep, rubric, passed, rationale, version),
            )
            report.rescored += 1
        # Keep the per-result judge summary in step with the per-rubric rows.
        for sid, ep in new:
            verdicts = [
                s["passed"]
                for s in store.db.execute(
                    "SELECT passed FROM score WHERE run_id = ? AND sample_id = ? AND epoch = ?",
                    (run_id, sid, ep),
                )
            ]
            combined = None if any(v is None for v in verdicts) else kleene_and(verdicts)
            store.db.execute(
                "UPDATE result SET judge_pass = ? WHERE run_id = ? AND sample_id = ? AND epoch = ?",
                (combined, run_id, sid, ep),
            )
        versions = {
            v["judge_version"]
            for v in store.db.execute(
                "SELECT DISTINCT judge_version FROM score WHERE run_id = ?", (run_id,)
            )
            if v["judge_version"]
        }
        store.db.execute(
            "UPDATE run SET judge_version = ? WHERE id = ?", (",".join(sorted(versions)), run_id)
        )
    return report
