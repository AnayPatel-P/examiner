import asyncio
import shutil
from pathlib import Path

from examiner.scenarios.schema import PACKS_DIR, load_pack
from examiner.scenarios.variants import (
    PERSONAS,
    generate_variants,
    is_duplicate,
    make_variant,
    persona_for,
    render_index,
)

SEED = next(s for s in load_pack("v1") if s.id == "rege-019")


def test_variant_copies_ground_truth():
    v = make_variant(SEED, 1, "a retiree", ["new turn one", "new turn two"])
    assert v.must_say == SEED.must_say and v.must_not_say == SEED.must_not_say
    assert v.citations == SEED.citations and v.rubrics == SEED.rubrics
    assert v.source_note == SEED.source_note and v.area == SEED.area
    assert v.turns == ["new turn one", "new turn two"] and v.persona == "a retiree"


def test_variant_id_scheme():
    v = make_variant(SEED, 2, "p", ["a", "b"])
    assert v.id == "rege-019--v2" and v.seed_id == "rege-019"


def test_duplicate_detected():
    assert is_duplicate(["How much is a stop payment?"], ["how much is a stop payment"])
    assert not is_duplicate(
        ["How much is a stop payment?"], ["what do you charge to cancel a check"]
    )


def test_persona_is_deterministic():
    assert persona_for("fees-001") == persona_for("fees-001")
    assert persona_for("fees-001") in PERSONAS


def make_root(tmp_path: Path) -> Path:
    root = tmp_path / "packs"
    (root / "mini" / "seeds").mkdir(parents=True)
    for sid in ("fees-001", "rege-019"):
        shutil.copy(PACKS_DIR / "v1" / "seeds" / f"{sid}.yaml", root / "mini" / "seeds")
    return root


class FakeParaphraser:
    def __init__(self, outputs=None):
        self.calls = 0
        self.outputs = outputs

    async def __call__(self, turns: list[str], persona: str) -> list[str]:
        self.calls += 1
        if self.outputs:
            return self.outputs.pop(0)
        return [f"so um, {t.lower()} asking for real, thanks ({self.calls})" for t in turns]


def test_variants_written_and_loadable(tmp_path: Path):
    root = make_root(tmp_path)
    report = asyncio.run(generate_variants("mini", FakeParaphraser(), root=root))
    assert report.written == 2
    pack = {s.id: s for s in load_pack("mini", root=root)}
    assert set(pack) == {"fees-001", "rege-019", "fees-001--v1", "rege-019--v1"}
    assert len(pack["rege-019--v1"].turns) == 2


def test_variants_skip_existing(tmp_path: Path):
    root = make_root(tmp_path)
    asyncio.run(generate_variants("mini", FakeParaphraser(), root=root))
    fake = FakeParaphraser()
    report = asyncio.run(generate_variants("mini", fake, root=root))
    assert report.written == 0 and report.skipped == 2 and fake.calls == 0


def test_duplicate_paraphrase_retried_then_dropped(tmp_path: Path):
    root = make_root(tmp_path)
    same = ["What's your overdraft fee?"]
    fake = FakeParaphraser(outputs=[same, same, ["a", "b"], ["c", "d"]])
    report = asyncio.run(generate_variants("mini", fake, root=root))
    assert "fees-001" in report.failed
    assert report.written == 1


def test_wrong_turn_count_rejected(tmp_path: Path):
    root = make_root(tmp_path)
    fake = FakeParaphraser(outputs=[["only one"], ["still one"], ["x"], ["y"]])
    report = asyncio.run(generate_variants("mini", fake, root=root))
    assert "rege-019" in report.failed


def test_render_index_lists_seeds_and_citations():
    md = render_index("v1")
    assert "| rege-019 |" in md and "12 CFR 1005.11(d)(1)" in md
    assert "Meridian fee schedule: overdraft" in md


def test_retry_uses_a_different_persona(tmp_path: Path):
    root = make_root(tmp_path)
    seen: list[str] = []

    async def lazy_for_first_persona(turns: list[str], persona: str) -> list[str]:
        seen.append(persona)
        if len(seen) % 2 == 1:
            return [t.lower() for t in turns]  # near-duplicate
        return [f"rewritten by someone else: {i}" for i, _ in enumerate(turns)]

    report = asyncio.run(generate_variants("mini", lazy_for_first_persona, root=root))
    assert report.written == 2 and report.failed == []
    assert seen[0] != seen[1]
    pack = {s.id: s for s in load_pack("mini", root=root)}
    assert pack["fees-001--v1"].persona == seen[1]
