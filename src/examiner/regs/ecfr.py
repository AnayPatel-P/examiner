"""Parse a CFR part from the eCFR XML into paragraph ids -> text."""

import gzip
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from functools import cache
from pathlib import Path

SNAPSHOT = Path(__file__).parent / "reg_e.json"
ECFR_URL = "https://www.ecfr.gov/api/versioner/v1/full/{date}/title-12.xml?part=1005"

_TOKEN = r"[a-z]+|\d+|[A-Z]+"
_ONE = re.compile(rf"^\(({_TOKEN})\)\s*(.*)$", re.S)
# "(c) Heading—(1) text": a short heading, an em dash, then a second marker.
_TWO = re.compile(rf"^\(({_TOKEN})\)\s*([^()]{{0,150}}?)\s*—\s*\(({_TOKEN})\)\s*(.*)$", re.S)
# "(5) Heading. (i) text": a short heading ending in a period, then a second marker.
_TWO_DOT = re.compile(rf"^\(({_TOKEN})\)\s*([^().]{{1,80}})\.\s+\(({_TOKEN})\)\s*(.*)$", re.S)
_ROMAN = re.compile(r"^(x{0,3})(ix|iv|v?i{0,3})$")


def _is_roman(tok: str) -> bool:
    return bool(tok) and bool(_ROMAN.match(tok))


def _level(tok: str, stack: list[str | None], next_tok: str | None) -> int:
    if tok.isdigit():
        return 2
    if tok.isupper():
        return 4
    if len(tok) > 1:
        return 3 if _is_roman(tok) else 1
    if tok not in ("i", "v", "x"):
        return 1
    letter, roman = stack[0], stack[2]
    if tok == "i":
        if next_tok == "ii":
            return 3
        if letter == "h":
            return 1
    if tok == "v" and roman == "iv":
        return 3
    if tok == "x" and roman == "ix":
        return 3
    if letter and ord(tok) == ord(letter) + 1:
        return 1
    return 3 if any(stack[1:]) else 1


def _markers(text: str) -> list[tuple[str, str]]:
    """Leading (token, own_text) pairs: one or two."""
    m = _TWO.match(text) or _TWO_DOT.match(text)
    if m:
        return [(m.group(1), m.group(2).strip()), (m.group(3), m.group(4).strip())]
    m = _ONE.match(text)
    return [(m.group(1), m.group(2).strip())] if m else []


def parse_part(xml: bytes) -> dict[str, str]:
    root = ET.fromstring(xml)
    out: dict[str, str] = {}
    for sec in root.iter():
        if sec.get("TYPE") != "SECTION":
            continue
        sid = sec.get("N") or ""
        texts = [" ".join("".join(p.itertext()).split()) for p in sec if p.tag == "P"]
        firsts = [(_markers(t) or [(None, "")])[0][0] for t in texts]
        stack: list[str | None] = [None, None, None, None]
        current = sid
        for idx, text in enumerate(texts):
            marks = _markers(text)
            if not marks:
                out[current] = (out.get(current, "") + " " + text).strip()
                continue
            for j, (tok, own) in enumerate(marks):
                nxt = (
                    marks[j + 1][0]
                    if j + 1 < len(marks)
                    else (firsts[idx + 1] if idx + 1 < len(firsts) else None)
                )
                lvl = _level(tok, stack, nxt)
                stack[lvl - 1] = tok
                for k in range(lvl, 4):
                    stack[k] = None
                current = sid + "".join(f"({t})" for t in stack if t)
                out[current] = own
    return out


def fetch_part(date: str) -> bytes:
    req = urllib.request.Request(
        ECFR_URL.format(date=date),
        headers={"Accept-Encoding": "gzip", "User-Agent": "examiner-eval/0.1"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
    return data


def write_snapshot(date: str, path: Path = SNAPSHOT) -> int:
    paras = parse_part(fetch_part(date))
    path.write_text(
        json.dumps(
            {"source": ECFR_URL.format(date=date), "date": date, "paragraphs": paras},
            indent=1,
            ensure_ascii=False,
        )
    )
    load_reg_e.cache_clear()
    return len(paras)


@cache
def load_reg_e() -> dict:
    return json.loads(SNAPSHOT.read_text())


def reg_text(cite: str) -> str | None:
    key = cite.removeprefix("12 CFR").strip()
    return load_reg_e()["paragraphs"].get(key)
