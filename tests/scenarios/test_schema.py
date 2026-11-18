from pathlib import Path

import pytest
from pydantic import ValidationError

from examiner.scenarios.schema import Scenario, load_pack

SCENARIO_YAML = """\
id: {id}
area: fees
persona: retail customer
turns: ["What's your overdraft fee?"]
must_say: [{{id: od-34, any_of: ["$34"]}}]
must_not_say: []
citation: "Meridian fee schedule: overdraft"
source_note: Overdraft fee is $34 per item.
"""


def test_load_smoke_pack_has_5():
    pack = load_pack("smoke")
    assert len(pack) == 5
    assert {s.area for s in pack} == {"fees", "reg_e"}
    assert all(s.citation and s.source_note for s in pack)


def test_duplicate_ids_rejected(tmp_path: Path):
    (tmp_path / "dup").mkdir()
    for name in ("a.yaml", "b.yaml"):
        (tmp_path / "dup" / name).write_text(SCENARIO_YAML.format(id="same-id"))
    with pytest.raises(ValueError, match="same-id"):
        load_pack("dup", root=tmp_path)


def test_missing_pack_raises(tmp_path: Path):
    with pytest.raises(ValueError, match="nope"):
        load_pack("nope", root=tmp_path)


def test_scenario_requires_citation():
    with pytest.raises(ValidationError):
        Scenario(
            id="x",
            area="fees",
            persona="p",
            turns=["q"],
            must_say=[],
            must_not_say=[],
            citation="",
            source_note="n",
        )
