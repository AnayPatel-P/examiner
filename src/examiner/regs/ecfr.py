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
_MARK = re.compile(rf"\(({_TOKEN})\)")
_NEXT = rf"(?=\((?:{_TOKEN})\))"
# "Heading—(1)" and "Heading. (i)": a short heading, then the next marker.
_DASH_HEADING = re.compile(rf"\s*([^()]{{0,200}}?)\s*—\s*{_NEXT}")
_DOT_HEADING = re.compile(rf"\s*([^().]{{1,200}})\.\s+{_NEXT}")
_ROMAN = re.compile(r"^(x{0,3})(ix|iv|v?i{0,3})$")
LEVELS = 6  # a, 1, i, A, italic 1, italic i


def _is_roman(tok: str) -> bool:
    return bool(tok) and bool(_ROMAN.match(tok))


def _level(tok: str, stack: list[str | None], next_tok: str | None, italic: bool) -> int:
    if italic:
        return 5 if tok.isdigit() else 6
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
    """Leading (token, own_text) pairs, e.g. "(a)(1) x", "(c) H—(1) H—(i) x"."""
    out: list[tuple[str, str]] = []
    rest = text
    while True:
        m = _MARK.match(rest)
        if not m:
            break
        tok, rest = m.group(1), rest[m.end():]
        if _MARK.match(rest):  # adjacent: "(a)(1)"
            out.append((tok, ""))
            continue
        h = _DASH_HEADING.match(rest) or _DOT_HEADING.match(rest)
        if h:
            out.append((tok, h.group(1).strip()))
            rest = rest[h.end():]
            continue
        out.append((tok, rest.strip()))
        return out
    return out


def _italic_flags(p: ET.Element, marks: list[tuple[str, str]]) -> list[bool]:
    """eCFR writes level-5/6 markers as "(<I>1</I>)"; find which leading markers are italic."""
    raw = ET.tostring(p, encoding="unicode")
    flags, cursor = [], 0
    for tok, _ in marks:
        plain = raw.find(f"({tok})", cursor)
        ital = raw.find(f"(<I>{tok}</I>)", cursor)
        is_ital = ital != -1 and (plain == -1 or ital < plain)
        pos = ital if is_ital else plain
        flags.append(is_ital)
        cursor = pos + 1 if pos != -1 else cursor
    return flags


def parse_part(xml: bytes, strict: bool = False) -> dict[str, str]:
    root = ET.fromstring(xml)
    out: dict[str, str] = {}
    dupes: list[str] = []
    for sec in root.iter():
        if sec.get("TYPE") != "SECTION":
            continue
        sid = sec.get("N") or ""
        ps = [p for p in sec if p.tag == "P"]
        texts = [" ".join("".join(p.itertext()).split()) for p in ps]
        firsts = [(_markers(t) or [(None, "")])[0][0] for t in texts]
        stack: list[str | None] = [None] * LEVELS
        current = sid
        for idx, text in enumerate(texts):
            marks = _markers(text)
            if not marks:
                out[current] = (out.get(current, "") + " " + text).strip()
                continue
            italic = _italic_flags(ps[idx], marks)
            for j, (tok, own) in enumerate(marks):
                nxt = marks[j + 1][0] if j + 1 < len(marks) else (
                    firsts[idx + 1] if idx + 1 < len(firsts) else None
                )
                lvl = _level(tok, stack, nxt, italic[j])
                stack[lvl - 1] = tok
                for k in range(lvl, LEVELS):
                    stack[k] = None
                current = sid + "".join(f"({t})" for t in stack if t)
                if current in out:
                    dupes.append(current)
                out[current] = own
    if strict and dupes:
        raise ValueError(f"duplicate paragraph ids: {', '.join(sorted(set(dupes))[:20])}")
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
    paras = parse_part(fetch_part(date), strict=True)
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
