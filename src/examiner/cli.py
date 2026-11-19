"""Examiner command line."""

from pathlib import Path

import typer
from dotenv import load_dotenv
from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelCost

from examiner.runner.task import examiner_task
from examiner.store import Store

app = typer.Typer(no_args_is_help=True, help="Compliance evals for banking chatbots.")

JUDGE_MODEL = "anthropic/claude-sonnet-5-5"

# USD per million tokens (Anthropic list prices, 2026-11). Cache write = 1.25x input.
PRICES: dict[str, ModelCost] = {
    "anthropic/claude-sonnet-5-5": ModelCost(
        input=2.0, output=10.0, input_cache_write=2.5, input_cache_read=0.10
    ),
    "anthropic/claude-haiku-5-5": ModelCost(
        input=0.10, output=0.50, input_cache_write=0.125, input_cache_read=0.01
    ),
}


def cost_options(judge_model: str, max_cost: float) -> dict:
    """Budget cap for priced models. Test models (mockllm) run uncapped."""
    if judge_model in PRICES:
        return {"cost_limit": max_cost, "model_cost_config": {judge_model: PRICES[judge_model]}}
    if judge_model.startswith("mockllm/"):
        return {}
    raise typer.BadParameter(f"no price known for {judge_model}; add it to PRICES")


def _mark(v: int | None) -> str:
    return {1: "pass", 0: "FAIL", None: "-"}[v]


@app.callback()
def main() -> None:
    load_dotenv()


def per_sample_cap(max_run_cost: float, n_samples: int, epochs: int) -> float:
    """Inspect's cost_limit is per sample; split the run budget evenly so judge spend <= cap."""
    return max_run_cost / max(1, n_samples * epochs)


CHECKS = ["fact", "factual", "disclosure", "commitments"]


def summarize(results, scores, areas: dict[str, str]) -> dict[str, dict]:
    """Pass counts by area: {area: {check: (passed, judged), "errors": n}}."""
    table: dict[str, dict] = {}
    for area in sorted(set(areas.values())):
        table[area] = {c: (0, 0) for c in CHECKS} | {"errors": 0}

    def add(area: str, check: str, value) -> None:
        if value is None:
            return
        p, n = table[area][check]
        table[area][check] = (p + int(value), n + 1)

    for r in results:
        area = areas[r["sample_id"]]
        if r["error"]:
            table[area]["errors"] += 1
            continue
        add(area, "fact", r["fact_pass"])
    for s in scores:
        add(areas[s["sample_id"]], s["rubric"], s["passed"])
    return table


def _pct(pair: tuple[int, int]) -> str:
    p, n = pair
    return f"{p}/{n} ({100 * p / n:.0f}%)" if n else "-"


@app.command()
def run(
    target: str = typer.Option("http://localhost:8001", help="Base URL of the chat target."),
    pack: str = typer.Option("smoke", help="Scenario pack under packs/."),
    variant: str = typer.Option("naive", help="Target variant to request."),
    epochs: int = typer.Option(1, min=1),
    max_run_cost: float = typer.Option(
        5.0, help="Judge spend cap for the whole run, USD (split evenly per sample)."
    ),
    judge_model: str = typer.Option(JUDGE_MODEL),
    db: Path = typer.Option(Path("examiner.db")),
    show_all: bool = typer.Option(False, "--all", help="Print every scenario row."),
) -> None:
    """Run a scenario pack against a chat target and store the results."""
    from examiner.scenarios.schema import load_pack

    try:
        scenarios = load_pack(pack)
        task = examiner_task(pack=pack, target=target, variant=variant)
    except ValueError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(2) from e
    budget = cost_options(judge_model, per_sample_cap(max_run_cost, len(scenarios), epochs))
    # The solver never calls the task model; using the judge here keeps every model priced.
    [log] = inspect_eval(
        task,
        model=judge_model,
        model_roles={"grader": judge_model},
        epochs=epochs,
        **budget,
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
    table = summarize(rows, store.scores(run_id), areas)
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
    run: str = typer.Option(..., "--run"),
    labels: Path = typer.Option(Path("spike/labels.csv")),
    db: Path = typer.Option(Path("examiner.db")),
    rubric: str = typer.Option("factual", help="Rubric the labels were made against."),
) -> None:
    """Compare the judge's verdicts on one rubric with your labels."""
    from examiner.calibration import agreement_report, read_labels

    store = Store(db)
    judge = {(r["sample_id"], r["epoch"]): r["passed"] for r in store.scores(run, rubric)}
    judge = {k: (None if v is None else bool(v)) for k, v in judge.items()}
    rep = agreement_report(judge, read_labels(labels))
    typer.echo(
        f"n={rep.n}  raw agreement={rep.raw_agreement:.2f}  kappa={rep.kappa:.2f}\n"
        f"                 human pass  human fail\n"
        f"judge pass       {rep.both_pass:>10}  {rep.judge_pass_human_fail:>10}\n"
        f"judge fail       {rep.judge_fail_human_pass:>10}  {rep.both_fail:>10}"
    )
    for sid, ep in rep.disagreements:
        typer.echo(f"disagree: {sid} (epoch {ep})")


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
