"""Shared filesystem helpers for Case Monitor scripts."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

DEFAULT_STATE_PATH = Path(os.getenv("NGT_STATE_FILE", ".state/last_hash.txt"))
DEFAULT_REPORT_PATH = Path(os.getenv("NGT_REPORT_FILE", "result.json"))


def read_last_hash(state_path: Path = DEFAULT_STATE_PATH) -> str:
    try:
        return state_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def write_last_hash(hash_value: str, state_path: Path = DEFAULT_STATE_PATH) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(hash_value, encoding="utf-8")


def write_report(data: Dict[str, Any], report_path: Path = DEFAULT_REPORT_PATH) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
