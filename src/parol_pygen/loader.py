from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model import ExportModel, parse_export_model


def load_json_file(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_export_model(path: str | Path) -> ExportModel:
    raw = load_json_file(path)
    return parse_export_model(raw)
