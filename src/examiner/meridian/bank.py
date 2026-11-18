"""Meridian Bank reference data (fictional)."""

import json
from functools import cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


@cache
def load_fee_schedule() -> dict:
    return json.loads((DATA_DIR / "fee_schedule.json").read_text())


@cache
def load_faq() -> str:
    return (DATA_DIR / "faq.md").read_text()
