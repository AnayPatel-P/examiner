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


@app.command()
def run(
    target: str = typer.Option("http://localhost:8001", help="Base URL of the chat target."),
    pack: str = typer.Option("smoke", help="Scenario pack under packs/."),
    variant: str = typer.Option("naive", help="Target variant to request."),
    epochs: int = typer.Option(1, min=1),
    max_cost_per_sample: float = typer.Option(
        0.25,
        help="Per-sample judge spend cap in USD (Inspect cost_limit is per sample). "
        "A run-level cap comes in roadmap 2.6.",
    ),
    judge_model: str = typer.Option(JUDGE_MODEL),
    db: Path = typer.Option(Path("examiner.db")),
) -> None:
    """Run a scenario pack against a chat target and store the results."""
    try:
        task = examiner_task(pack=pack, target=target, variant=variant)
    except ValueError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(2) from e
    budget = cost_options(judge_model, max_cost_per_sample)
    # The solver never calls the task model; using the judge here keeps every model priced.
    [log] = inspect_eval(
        task,
        model=judge_model,
        model_roles={"grader": judge_model},
        epochs=epochs,
        **budget,
        log_dir="logs",
        fail_on_error=False,
        max_samples=8,
        display="none",
    )
    store = Store(db)
    run_id = store.index_log(log, target=target, variant=variant)
    rows = store.results(run_id)
    width = max(len(r["sample_id"]) for r in rows) if rows else 10
    typer.echo(f"{'scenario':<{width}}  ep  fact  judge  citation")
    for r in rows:
        status = f"ERROR {r['error'][:60]}" if r["error"] else r["citation"]
        typer.echo(
            f"{r['sample_id']:<{width}}  {r['epoch']:>2}  {_mark(r['fact_pass']):<4}  "
            f"{_mark(r['judge_pass']):<5}  {status}"
        )
    n = len(rows)
    fact = sum(r["fact_pass"] or 0 for r in rows)
    judge = sum(r["judge_pass"] or 0 for r in rows)
    run_row = store.run(run_id)
    cost = run_row["cost_usd"] if run_row else None
    cost_s = f"${cost:.4f} (judge only)" if cost is not None else "n/a"
    typer.echo(f"\nrun {run_id} · fact {fact}/{n} · judge {judge}/{n} · cost {cost_s}")


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
) -> None:
    """Compare the judge's verdicts with your labels."""
    from examiner.calibration import agreement_report, read_labels

    store = Store(db)
    judge = {(r["sample_id"], r["epoch"]): r["judge_pass"] for r in store.results(run)}
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
