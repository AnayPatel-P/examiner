"""Examiner command line."""

from pathlib import Path

import typer
from dotenv import load_dotenv
from inspect_ai import eval as inspect_eval

from examiner.pricing import PRICES
from examiner.reports import scorecard
from examiner.runner.budget import JudgeBudget
from examiner.runner.task import examiner_task
from examiner.store import Store

app = typer.Typer(no_args_is_help=True, help="Compliance evals for banking chatbots.")

JUDGE_MODEL = "anthropic/claude-sonnet-5-5"


def judge_budget(judge_model: str, max_run_cost: float) -> JudgeBudget:
    if judge_model not in PRICES and not judge_model.startswith("mockllm/"):
        raise typer.BadParameter(f"no price known for {judge_model}; add it to pricing.PRICES")
    return JudgeBudget(limit_usd=max_run_cost)


def _mark(v: int | None) -> str:
    return {1: "pass", 0: "FAIL", None: "-"}[v]


@app.callback()
def main() -> None:
    load_dotenv()


CHECKS = ["overall", "fact", "factual", "disclosure", "commitments"]


def _pct(cell: dict) -> str:
    p, n = cell["passed"], cell["n"]
    return f"{p}/{n} ({100 * p / n:.0f}%)" if n else "-"


@app.command()
def run(
    target: str = typer.Option("http://localhost:8001", help="Base URL of the chat target."),
    pack: str = typer.Option("smoke", help="Scenario pack under packs/."),
    variant: str = typer.Option("naive", help="Target variant to request."),
    epochs: int = typer.Option(1, min=1),
    max_run_cost: float = typer.Option(
        5.0, help="Judge spend cap for the whole run, USD. Judging stops once it is reached."
    ),
    judge_model: str = typer.Option(JUDGE_MODEL),
    db: Path = typer.Option(Path("examiner.db")),
    show_all: bool = typer.Option(False, "--all", help="Print every scenario row."),
) -> None:
    """Run a scenario pack against a chat target and store the results."""
    from examiner.scenarios.schema import load_pack

    try:
        scenarios = load_pack(pack)
        budget = judge_budget(judge_model, max_run_cost)
        task = examiner_task(pack=pack, target=target, variant=variant, judge_budget=budget)
    except ValueError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(2) from e
    costs = {judge_model: PRICES[judge_model]} if judge_model in PRICES else None
    # The solver never calls the task model; using the judge here keeps every model priced.
    [log] = inspect_eval(
        task,
        model=judge_model,
        model_roles={"grader": judge_model},
        epochs=epochs,
        model_cost_config=costs,
        log_dir="logs",
        fail_on_error=False,
        retry_on_error=2,
        max_samples=8,
        display="none",
    )
    store = Store(db)
    run_id = store.index_log(log, target=target, variant=variant)
    rows = store.results(run_id)
    if show_all or len(rows) <= 30:
        width = max(len(r["sample_id"]) for r in rows) if rows else 10
        typer.echo(f"{'scenario':<{width}}  ep  fact  judge  citation")
        for r in rows:
            status = f"ERROR {r['error'][:60]}" if r["error"] else r["citation"]
            typer.echo(
                f"{r['sample_id']:<{width}}  {r['epoch']:>2}  {_mark(r['fact_pass']):<4}  "
                f"{_mark(r['judge_pass']):<5}  {status}"
            )
    areas = {s.id: s.area for s in scenarios}
    table = scorecard(rows, store.scores(run_id), areas)
    typer.echo(f"\n{'area':<7} {'errors':>6}  " + "  ".join(f"{c:<14}" for c in CHECKS))
    for area, t in table.items():
        typer.echo(f"{area:<7} {t['errors']:>6}  " + "  ".join(f"{_pct(t[c]):<14}" for c in CHECKS))
    n = len(rows)
    fact = sum(r["fact_pass"] or 0 for r in rows)
    judge = sum(r["judge_pass"] or 0 for r in rows)
    run_row = store.run(run_id)
    jc = run_row["cost_usd"] if run_row else None
    tc = run_row["target_cost_usd"] if run_row else None
    wall = run_row["wall_seconds"] if run_row else None
    money = lambda v: f"${v:.4f}" if v is not None else "n/a"  # noqa: E731
    if budget.exhausted():
        typer.echo(f"\nwarning: judge budget ${max_run_cost} reached; later rubrics not judged")
    if rows and all(r["error"] for r in rows):
        typer.echo(
            f"\nerror: all {len(rows)} samples errored. First error: {rows[0]['error'][:200]}",
            err=True,
        )
        raise typer.Exit(1)
    typer.echo(
        f"\nrun {run_id} · fact {fact}/{n} · judge {judge}/{n} · judge cost {money(jc)} · "
        f"target cost {money(tc)} · wall {wall:.0f}s"
        if wall is not None
        else f"\nrun {run_id} · fact {fact}/{n} · judge {judge}/{n} · judge cost {money(jc)} · "
        f"target cost {money(tc)}"
    )


LABEL_FIELDS = ["sample_id", "epoch", "citation", "source_note", "transcript", "human_pass"]


@app.command("label-export")
def label_export(
    run: str = typer.Option(..., "--run", help="Run id to label."),
    out: Path = typer.Option(Path("spike/labels.csv")),
    db: Path = typer.Option(Path("examiner.db")),
) -> None:
    """Write a blind labeling sheet (no judge verdicts) for a run."""
    import csv

    from examiner.scenarios.schema import load_pack

    store = Store(db)
    run_row = store.run(run)
    if run_row is None:
        typer.echo(f"error: no run {run}", err=True)
        raise typer.Exit(2)
    notes = {s.id: s.source_note for s in load_pack(run_row["pack"])}
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LABEL_FIELDS)
        w.writeheader()
        for r in store.results(run):
            if r["error"]:
                continue
            w.writerow(
                {
                    "sample_id": r["sample_id"],
                    "epoch": r["epoch"],
                    "citation": r["citation"],
                    "source_note": notes.get(r["sample_id"], ""),
                    "transcript": r["transcript"],
                    "human_pass": "",
                }
            )
    typer.echo(f"wrote {out}: fill human_pass with y/n, then run `examiner kappa`")


@app.command()
def kappa(
    run: str | None = typer.Option(None, "--run", help="Limit to one run's labels."),
    labels: Path | None = typer.Option(None, help="CSV sheet; omit to use labels in the DB."),
    db: Path = typer.Option(Path("examiner.db")),
    rubric: str = typer.Option("factual", help="Rubric the labels were made against."),
) -> None:
    """Compare the judge's verdicts on one rubric with your labels."""
    from examiner.calibration import agreement_report, read_labels

    store = Store(db)
    if labels is not None:
        if run is None:
            raise typer.BadParameter("--run is required with --labels")
        judge = {(r["sample_id"], r["epoch"]): r["passed"] for r in store.scores(run, rubric)}
        human = read_labels(labels)
    else:
        rows = [r for r in store.judged_with_labels(rubric) if run is None or r["run_id"] == run]
        judge = {(f"{r['run_id']}/{r['sample_id']}", r["epoch"]): r["judge_pass"] for r in rows}
        human = {
            (f"{r['run_id']}/{r['sample_id']}", r["epoch"]): bool(r["human_pass"]) for r in rows
        }
    verdicts = {k: (None if v is None else bool(v)) for k, v in judge.items()}
    rep = agreement_report(verdicts, human)
    typer.echo(
        f"n={rep.n}  raw agreement={rep.raw_agreement:.2f}  kappa={rep.kappa:.2f}\n"
        f"                 human pass  human fail\n"
        f"judge pass       {rep.both_pass:>10}  {rep.judge_pass_human_fail:>10}\n"
        f"judge fail       {rep.judge_fail_human_pass:>10}  {rep.both_fail:>10}"
    )
    for sid, ep in rep.disagreements:
        typer.echo(f"disagree: {sid} (epoch {ep})")


@app.command("labels-import")
def labels_import(
    csv_path: Path = typer.Option(..., "--csv"),
    run: str = typer.Option(..., "--run"),
    rubric: str = typer.Option("factual"),
    db: Path = typer.Option(Path("examiner.db")),
) -> None:
    """Load a filled CSV labeling sheet into the labels table."""
    from examiner.calibration import read_labels
    from examiner.scenarios.schema import RUBRIC_NAMES

    if rubric not in RUBRIC_NAMES:
        raise typer.BadParameter(f"rubric must be one of {', '.join(RUBRIC_NAMES)}")
    store = Store(db)
    if store.run(run) is None:
        typer.echo(f"error: no run {run}", err=True)
        raise typer.Exit(2)
    n = 0
    for (sid, ep), passed in read_labels(csv_path).items():
        if store.result(run, sid, ep) is None:
            typer.echo(f"skip: {sid} (epoch {ep}) not in run {run}", err=True)
            continue
        store.save_label(run, sid, ep, rubric, passed)
        n += 1
    typer.echo(f"imported {n} {rubric} labels for run {run}")


def _save_sheet(path: Path, rows: list[dict]) -> None:
    import csv

    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


@app.command()
def label(labels: Path = typer.Option(Path("spike/labels.csv"))) -> None:
    """Label transcripts one at a time: y = pass, n = fail, s = skip, q = quit."""
    import csv

    rows = list(csv.DictReader(labels.open(newline="")))
    todo = [r for r in rows if not (r.get("human_pass") or "").strip()]
    typer.echo(
        f"{len(todo)} to label. Rule (factual-v1): n if the bot states a wrong fee, deadline "
        "or timeline, or invents a commitment; y otherwise (hedging is y)."
    )
    for i, row in enumerate(todo, 1):
        typer.echo("\n" + "=" * 72)
        typer.echo(f"[{i}/{len(todo)}] {row['sample_id']} (epoch {row['epoch']})")
        typer.echo(f"Rule: {row['citation']}\nTruth: {row['source_note']}")
        typer.echo("-" * 72 + "\n" + row["transcript"] + "\n" + "-" * 72)
        while True:
            answer = typer.prompt("pass? [y/n/s/q]").strip().lower()
            if answer in ("y", "n", "s", "q"):
                break
            typer.echo("type y, n, s or q")
        if answer == "q":
            break
        if answer in ("y", "n"):
            row["human_pass"] = answer
            _save_sheet(labels, rows)
    done = sum(1 for r in rows if (r.get("human_pass") or "").strip())
    typer.echo(f"\n{done}/{len(rows)} labeled, saved to {labels}")


@app.command("label-batch")
def label_batch(
    name: str = typer.Option("calib-v1", help="Batch name, shown on the Label screen."),
    runs: list[str] = typer.Option(None, "--run", help="Runs to draw from (default: all)."),
    per_rubric: int = typer.Option(34, min=1, help="Items per rubric."),
    seed: str = typer.Option("phase-5"),
    db: Path = typer.Option(Path("examiner.db")),
) -> None:
    """Pick a mixed pass/fail calibration batch across runs, variants and rubrics."""
    from collections import Counter

    from examiner.batch import select_batch

    store = Store(db)
    run_rows = [store.run(r) for r in runs] if runs else store.runs()
    if not run_rows or any(r is None for r in run_rows):
        typer.echo("error: no such run(s)", err=True)
        raise typer.Exit(2)
    labeled = {(x["run_id"], x["sample_id"], x["epoch"], x["rubric"]) for x in store.labels()}
    candidates = []
    for run_row in run_rows:
        assert run_row is not None
        errored = {(r["sample_id"], r["epoch"]) for r in store.results(run_row["id"]) if r["error"]}
        for sc in store.scores(run_row["id"]):
            key = (run_row["id"], sc["sample_id"], sc["epoch"], sc["rubric"])
            if sc["passed"] is None or key in labeled or key[1:3] in errored:
                continue
            candidates.append(
                {
                    "run_id": run_row["id"],
                    "variant": run_row["variant"],
                    "sample_id": sc["sample_id"],
                    "epoch": sc["epoch"],
                    "rubric": sc["rubric"],
                    "judge_pass": sc["passed"],
                }
            )
    items = select_batch(candidates, per_rubric=per_rubric, seed=seed)
    store.save_batch(name, items)
    typer.echo(f"batch {name}: {len(items)} items")
    cells = Counter((i["rubric"], i["variant"]) for i in items)
    for (rubric, variant), n in sorted(cells.items()):
        typer.echo(f"  {rubric:<12} {variant:<12} {n}")
    typer.echo("Label it at /label?batch=" + name + " (judge verdicts stay hidden).")


@app.command()
def taxonomy(
    run: str = typer.Argument(..., help="Run id."),
    db: Path = typer.Option(Path("examiner.db")),
    top: int = typer.Option(15, help="Clauses to print."),
) -> None:
    """Which cited clauses fail, how often, and how (fact check vs each judge rubric)."""
    from examiner.reports import failure_taxonomy, scenarios_for

    store = Store(db)
    run_row = store.run(run)
    if run_row is None:
        typer.echo(f"error: no run {run}", err=True)
        raise typer.Exit(2)
    cites = {sid: sc.citations for sid, sc in scenarios_for(run_row["pack"]).items()}
    tax = failure_taxonomy(store.results(run), store.scores(run), cites)
    typer.echo(
        f"{tax['failed_scenarios']}/{tax['scored_scenarios']} scored scenarios fail · modes: "
        + ", ".join(f"{k} {v}" for k, v in sorted(tax["modes"].items(), key=lambda kv: -kv[1]))
    )
    typer.echo(f"\n{'section':<14} {'failed':>8}  title")
    for sec in tax["sections"]:
        typer.echo(f"{sec['section']:<14} {sec['failed']:>3}/{sec['n']:<4}  {sec['section_title']}")
    typer.echo(f"\n{'clause':<30} {'failed':>8}  how")
    for c in tax["clauses"][:top]:
        how = ", ".join(f"{k} {v}" for k, v in sorted(c["modes"].items()))
        typer.echo(f"{c['citation']:<30} {c['failed']:>3}/{c['n']:<4}  {how}")


def _latest_run(store: Store, variant: str, pack: str):
    for r in store.runs():
        if r["variant"] == variant and r["pack"] == pack:
            return r
    return None


@app.command()
def gate(
    run: str | None = typer.Option(None, "--run", help="Run to check (default: latest guarded)."),
    baseline: Path = typer.Option(Path("gate/baseline.json")),
    db: Path = typer.Option(Path("examiner.db")),
    write_baseline: bool = typer.Option(False, help="Accept this run as the new baseline."),
    check_baseline: bool = typer.Option(
        False, help="Only check the committed baseline against the floor (no database)."
    ),
) -> None:
    """Fail (exit 1) if the guarded bot's overall pass rate regressed."""
    import json

    from examiner.gate import FLOOR, MAX_DROP, gate_check, load_baseline
    from examiner.reports import run_summary

    if check_baseline:
        base = load_baseline(baseline)
        rate = base["passed"] / base["n"]
        ok = rate >= FLOOR
        typer.echo(f"baseline {base['passed']}/{base['n']} = {rate:.1%}; floor {FLOOR:.0%}")
        raise typer.Exit(0 if ok else 1)
    store = Store(db)
    base = None if write_baseline else load_baseline(baseline)
    row = store.run(run) if run else _latest_run(store, "guarded", (base or {}).get("pack", "v1"))
    if row is None:
        typer.echo("error: no run to check", err=True)
        raise typer.Exit(2)
    results = store.results(row["id"])
    summ = run_summary(row, results, store.scores(row["id"]))
    current = {
        "variant": row["variant"],
        "pack": row["pack"],
        "passed": summ["overall"]["passed"],
        "n": summ["overall"]["n"],
        "total": len(results),
        "run_id": row["id"],
        "started_at": row["started_at"],
        "judge_version": row["judge_version"],
    }
    if write_baseline:
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text(json.dumps(current, indent=2) + "\n")
        typer.echo(f"wrote {baseline}: {current['passed']}/{current['n']}")
        return
    assert base is not None
    res = gate_check(current, base)
    typer.echo(
        f"gate {'PASS' if res.ok else 'FAIL'}: {res.summary} (floor {FLOOR:.0%}, "
        f"max drop {100 * MAX_DROP:.0f} pts) · run {row['id']}"
    )
    for reason in res.reasons:
        typer.echo(f"  - {reason}")
    raise typer.Exit(0 if res.ok else 1)


@app.command()
def rescore(
    rubric: str = typer.Option(..., help="Rubric to re-judge with its current version."),
    runs: list[str] = typer.Option(None, "--run", help="Runs (default: every run)."),
    judge_model: str = typer.Option(JUDGE_MODEL),
    max_cost: float = typer.Option(5.0, help="Judge spend cap for this command, USD."),
    db: Path = typer.Option(Path("examiner.db")),
) -> None:
    """Re-judge stored transcripts after a rubric change (the bot is not called)."""
    import asyncio

    from inspect_ai.model import get_model

    from examiner.rescore import rescore_run
    from examiner.scenarios.schema import RUBRIC_NAMES

    if rubric not in RUBRIC_NAMES:
        raise typer.BadParameter(f"rubric must be one of {', '.join(RUBRIC_NAMES)}")
    store = Store(db)
    budget = judge_budget(judge_model, max_cost)
    model = get_model(judge_model, config=None)
    targets = runs or [r["id"] for r in store.runs()]
    for rid in targets:
        rep = asyncio.run(rescore_run(store, rid, rubric, model, budget))
        typer.echo(
            f"{rid}: rescored {rep.rescored}, changed {rep.changed}, failed {len(rep.failed)}, "
            f"skipped (budget) {rep.skipped_budget}"
        )
    typer.echo(f"judge spend ${budget.spent_usd:.4f}")


@app.command()
def calibration(
    out: Path | None = typer.Option(None, help="Write the report as JSON here."),
    version: list[str] = typer.Option(
        None, "--version", help="Rubric version to compare, e.g. factual-v2 (repeatable)."
    ),
    db: Path = typer.Option(Path("examiner.db")),
) -> None:
    """Kappa per rubric from your labels (current verdicts, or named rubric versions)."""
    import json

    from examiner.calibration import calibration_by_rubric
    from examiner.scenarios.schema import RUBRIC_NAMES

    store = Store(db)
    if version:
        rows = {v: store.judged_with_labels(v.rsplit("-", 1)[0], judge_version=v) for v in version}
    else:
        rows = {r: store.judged_with_labels(r) for r in RUBRIC_NAMES}
    rep = calibration_by_rubric(rows)
    for name, d in rep.items():
        k = "n/a" if d["kappa"] is None else f"{d['kappa']:.2f}"
        ra = "n/a" if d["raw_agreement"] is None else f"{d['raw_agreement']:.2f}"
        typer.echo(
            f"{name:<16} n={d['n']:<4} kappa={k:<5} raw={ra:<5} "
            f"TP/FN/FP/TN(human pass=pos)={d['both_pass']}/{d['judge_fail_human_pass']}/"
            f"{d['judge_pass_human_fail']}/{d['both_fail']}"
        )
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rep, indent=2) + "\n")
        typer.echo(f"wrote {out}")


@app.command()
def export(
    out: Path = typer.Option(Path("web/public/data"), help="Where the JSON snapshot goes."),
    db: Path = typer.Option(Path("examiner.db")),
) -> None:
    """Write a static JSON snapshot of every run for the GitHub Pages scorecard."""
    import shutil

    from examiner.export import export_snapshot

    if out.exists():
        shutil.rmtree(out)
    n = export_snapshot(db, out)
    typer.echo(f"wrote {n} files to {out}; build with `npm --prefix web run build:static`")


@app.command("regs-fetch")
def regs_fetch(
    date: str = typer.Option(..., help="eCFR point-in-time date, YYYY-MM-DD."),
    out: Path | None = typer.Option(None, help="Snapshot path (default: the packaged one)."),
) -> None:
    """Refresh the Reg E paragraph snapshot from eCFR."""
    from examiner.regs import ecfr

    n = ecfr.write_snapshot(date, out or ecfr.SNAPSHOT)
    typer.echo(f"wrote {n} paragraphs of 12 CFR 1005 as of {date}")


@app.command()
def variants(
    pack: str = typer.Option("v1"),
    n: int = typer.Option(1, help="Variant number to generate for each seed."),
) -> None:
    """Generate persona/paraphrase variants for a pack's seeds (Haiku). Existing files are kept."""
    import asyncio

    from examiner.scenarios.variants import anthropic_paraphraser, generate_variants

    report = asyncio.run(generate_variants(pack, anthropic_paraphraser(), n=n))
    typer.echo(f"written {report.written}, kept {report.skipped}, failed {len(report.failed)}")
    for sid in report.failed:
        typer.echo(f"failed: {sid}")


@app.command()
def index(
    pack: str = typer.Option("v1"),
    out: Path = typer.Option(Path("docs/pack-v1.md")),
) -> None:
    """Write a human-readable index of a pack's seeds."""
    from examiner.scenarios.variants import render_index

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_index(pack))
    typer.echo(f"wrote {out}")


@app.command()
def serve(
    db: Path = typer.Option(Path("examiner.db")),
    port: int = typer.Option(8002),
) -> None:
    """Serve the read API (runs, results, labels, diff) for the dashboard."""
    import uvicorn

    from examiner.api.app import create_api

    uvicorn.run(create_api(db), port=port)


@app.command()
def diff(
    a: str = typer.Argument(..., help="Baseline run id."),
    b: str = typer.Argument(..., help="New run id."),
    check: str = typer.Option("overall", help="overall, fact, judge or a rubric name."),
    db: Path = typer.Option(Path("examiner.db")),
) -> None:
    """What run B fixed and broke compared with run A."""
    from examiner.reports import diff_runs

    store = Store(db)
    for rid in (a, b):
        if store.run(rid) is None:
            typer.echo(f"error: no run {rid}", err=True)
            raise typer.Exit(2)
    try:
        d = diff_runs(store.results(a), store.scores(a), store.results(b), store.scores(b), check)
    except ValueError as e:
        raise typer.BadParameter(str(e)) from e
    c = d["counts"]
    typer.echo(
        f"{check}: fixed {c['fixed']} · broke {c['broke']} · still fail {c['still_fail']} · "
        f"still pass {c['still_pass']} · unscored {c['unscored']} · "
        f"only in A {c['only_a']} · only in B {c['only_b']}"
    )
    for cat in ("broke", "fixed", "still_fail"):
        for item in d[cat]:
            typer.echo(f"  {cat:<10} {item['sample_id']} (epoch {item['epoch']})")
