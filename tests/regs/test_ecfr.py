from pathlib import Path

from examiner.regs.ecfr import load_reg_e, parse_part, reg_text

FIXTURE = (Path(__file__).parent / "fixture_part.xml").read_bytes()


def test_parse_letter_i_at_top_level():
    paras = parse_part(FIXTURE)
    assert paras["9999.2(i)"].startswith("Financial institution")
    assert "9999.2(j)" in paras


def test_parse_nested_roman_and_capital():
    paras = parse_part(FIXTURE)
    assert "10 business days" in paras["9999.11(c)(1)"]
    assert paras["9999.11(c)(2)(i)(A)"].startswith("No written confirmation")
    assert "two business days" in paras["9999.11(c)(2)(ii)"]
    assert paras["9999.11(c)(2)(v)"] == "Fifth item."
    assert paras["9999.11(d)"].startswith("Next")


def test_parent_text_excludes_children():
    paras = parse_part(FIXTURE)
    assert "Provisionally" not in paras["9999.11(c)(2)"]


def test_snapshot_real_paragraphs():
    reg = load_reg_e()
    assert reg["date"] == "2026-11-17"
    p = reg["paragraphs"]
    assert "90 days" in p["1005.11(c)(3)(ii)"]
    assert "60 days" in p["1005.6(b)(3)"]
    assert p["1005.2(i)"].lstrip("“").startswith("Financial institution")
    assert "1005.11(c)(3)(iii)" not in p


def test_reg_text_accepts_cfr_prefix():
    assert reg_text("12 CFR 1005.6(b)(3)") == load_reg_e()["paragraphs"]["1005.6(b)(3)"]
    assert reg_text("12 CFR 1005.99(z)") is None


def test_parse_period_heading_with_inline_child():
    paras = parse_part(FIXTURE)
    assert paras["9999.11(e)"] == "Notice"
    assert paras["9999.11(e)(1)"].startswith("Notice is given")
    assert "9999.11(e)(2)" in paras


def test_snapshot_1005_6_b_5_i():
    assert load_reg_e()["paragraphs"]["1005.6(b)(5)(i)"].startswith("Notice to a financial")


def test_regs_fetch_cli_writes_snapshot(monkeypatch, tmp_path):
    from typer.testing import CliRunner

    import examiner.regs.ecfr as ecfr
    from examiner.cli import app

    monkeypatch.setattr(ecfr, "fetch_part", lambda date: FIXTURE)
    out = tmp_path / "snap.json"
    res = CliRunner().invoke(app, ["regs-fetch", "--date", "2026-01-01", "--out", str(out)])
    assert res.exit_code == 0, res.output
    assert '"9999.11(c)(2)(i)(A)"' in out.read_text()


def test_parse_adjacent_markers():
    paras = parse_part(FIXTURE)
    assert paras["9999.3(a)(1)"].startswith("“Access device”")
    assert paras["9999.3(a)"] == ""
    assert "9999.3(a)(2)(i)" in paras


def test_parse_italic_level_five_does_not_overwrite_digits():
    paras = parse_part(FIXTURE)
    assert paras["9999.3(b)(2)"] == "Excludes trust accounts."
    assert paras["9999.3(b)(3)(i)(D)(1)"].startswith("That is issued")
    assert "9999.3(b)(3)(i)(D)(2)" in paras


def test_parse_three_chained_markers():
    paras = parse_part(FIXTURE)
    assert paras["9999.3(c)"] == "Permanent exceptions"
    assert paras["9999.3(c)(1)"] == "Transfers to certain countries"
    assert paras["9999.3(c)(1)(i)"].startswith("General.")
    assert paras["9999.3(c)(1)(i)(A)"].startswith("The laws")


def test_parse_strict_rejects_duplicate_ids():
    import pytest

    dup = FIXTURE.replace(b"<P>(j) <I>Person</I>", b"<P>(h) <I>Person</I>")
    with pytest.raises(ValueError, match="9999.2"):
        parse_part(dup, strict=True)


def _parent(pid: str) -> str:
    return pid[: pid.rindex("(")]


def test_snapshot_sanity():
    import re

    p = load_reg_e()["paragraphs"]
    firsts = {"ii": "i", "B": "A", "2": "1"}
    missing = []
    for pid in p:
        m = re.search(r"\(([^()]+)\)$", pid)
        if m and m.group(1) in firsts:
            sib = _parent(pid) + f"({firsts[m.group(1)]})"
            if sib not in p:
                missing.append(pid)
    assert missing == []
    cap_under_digit = [k for k in p if re.search(r"\(\d+\)\([A-Z]+\)$", k)]
    assert cap_under_digit == []
    starts_with_marker = [k for k, v in p.items() if re.match(r"\((?:[a-z]+|\d+|[A-Z]+)\)", v)]
    assert starts_with_marker == []
    assert "bona fide trust" in p["1005.2(b)(2)"]
    assert p["1005.2(a)(1)"].startswith("“Access device”")
