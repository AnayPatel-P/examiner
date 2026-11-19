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
    max_cost: float = typer.Option(1.0, help="Abort when judge spend passes this (USD)."),
    judge_model: str = typer.Option(JUDGE_MODEL),
    db: Path = typer.Option(Path("examiner.db")),
) -> None:
    """Run a scenario pack against a chat target and store the results."""
    try:
        task = examiner_task(pack=pack, target=target, variant=variant)
    except ValueError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(2) from e
    budget = cost_options(judge_model, max_cost)
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
