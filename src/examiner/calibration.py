"""Judge-vs-human agreement: Cohen's kappa and confusion counts."""

import csv
from dataclasses import dataclass, field
from pathlib import Path

Key = tuple[str, int]

YES = {"y", "yes", "1", "true", "pass", "p"}
NO = {"n", "no", "0", "false", "fail", "f"}


def cohen_kappa(a: list[bool], b: list[bool]) -> float:
    if len(a) != len(b):
        raise ValueError("rater lists differ in length")
    n = len(a)
    if n == 0:
        return 0.0
    p_o = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pa, pb = sum(a) / n, sum(b) / n
    p_e = pa * pb + (1 - pa) * (1 - pb)
    if p_e == 1:
        return 1.0 if p_o == 1 else 0.0
    return (p_o - p_e) / (1 - p_e)


def read_labels(path: Path) -> dict[Key, bool]:
    labels: dict[Key, bool] = {}
    with Path(path).open(newline="") as f:
        for row in csv.DictReader(f):
            raw = (row.get("human_pass") or "").strip().lower()
            if not raw:
                continue
            if raw not in YES | NO:
                raise ValueError(f"bad human_pass {raw!r} for {row['sample_id']}: use y or n")
            labels[(row["sample_id"], int(row["epoch"]))] = raw in YES
    return labels


@dataclass
class AgreementReport:
    n: int
    raw_agreement: float
    kappa: float
    both_pass: int
    judge_pass_human_fail: int
    judge_fail_human_pass: int
    both_fail: int
    disagreements: list[Key] = field(default_factory=list)


def agreement_report(judge: dict[Key, bool | None], human: dict[Key, bool]) -> AgreementReport:
    keys = sorted(k for k in human if judge.get(k) is not None)
    j = [bool(judge[k]) for k in keys]
    h = [human[k] for k in keys]
    pairs = list(zip(j, h, strict=True))
    n = len(keys)
    return AgreementReport(
        n=n,
        raw_agreement=(sum(x == y for x, y in pairs) / n) if n else 0.0,
        kappa=cohen_kappa(j, h),
        both_pass=pairs.count((True, True)),
        judge_pass_human_fail=pairs.count((True, False)),
        judge_fail_human_pass=pairs.count((False, True)),
        both_fail=pairs.count((False, False)),
        disagreements=[k for k, (x, y) in zip(keys, pairs, strict=True) if x != y],
    )


def calibration_by_rubric(rows_by_rubric: dict[str, list]) -> dict[str, dict]:
    """{rubric: report dict} from label rows joined to judge verdicts.

    Keys combine run and sample so labels from several runs can be pooled.
    """
    out = {}
    for rubric, rows in rows_by_rubric.items():
        if not rows:
            continue
        judge: dict[Key, bool | None] = {}
        human: dict[Key, bool] = {}
        for r in rows:
            key = (f"{r['run_id']}\t{r['sample_id']}", r["epoch"])
            judge[key] = None if r["judge_pass"] is None else bool(r["judge_pass"])
            human[key] = bool(r["human_pass"])
        rep = agreement_report(judge, human)
        d = rep.__dict__.copy()
        d["disagreements"] = [
            {"run_id": k.split("\t")[0], "sample_id": k.split("\t")[1], "epoch": ep}
            for k, ep in rep.disagreements
        ]
        out[rubric] = d
    return out
