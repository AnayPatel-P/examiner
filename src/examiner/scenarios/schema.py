"""Scenario schema and pack loading."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

RUBRIC_NAMES = ("factual", "disclosure", "commitments")
Rubric = Literal["factual", "disclosure", "commitments"]

PACKS_DIR = Path(__file__).resolve().parents[3] / "packs"


def display_citation(cite: str) -> str:
    """`fee:overdraft` -> `Meridian fee schedule: overdraft`; reg cites unchanged."""
    if cite.startswith("fee:"):
        return "Meridian fee schedule: " + cite.removeprefix("fee:")
    return cite


class Fact(BaseModel):
    id: str
    any_of: list[str] = Field(min_length=1)
    note: str = ""


class Scenario(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    area: Literal["reg_e", "fees"]
    persona: str
    turns: list[str] = Field(min_length=1)
    must_say: list[Fact]
    must_not_say: list[Fact]
    rubrics: list[Rubric] = Field(default_factory=lambda: ["factual"])
    citations: list[str] = Field(min_length=1)
    source_note: str
    seed_id: str | None = None

    @property
    def citation_display(self) -> str:
        return "; ".join(display_citation(c) for c in self.citations)


def load_pack(name: str, root: Path = PACKS_DIR) -> list[Scenario]:
    pack_dir = root / name
    files = sorted(pack_dir.rglob("*.yaml"))
    if not files:
        raise ValueError(f"pack {name!r} not found or empty at {pack_dir}")
    scenarios = [Scenario.model_validate(yaml.safe_load(f.read_text())) for f in files]
    seen: set[str] = set()
    for s in scenarios:
        if s.id in seen:
            raise ValueError(f"duplicate scenario id {s.id!r} in pack {name!r}")
        seen.add(s.id)
    return scenarios
