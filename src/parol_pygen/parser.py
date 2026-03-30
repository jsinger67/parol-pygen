from __future__ import annotations

from pathlib import Path
from typing import Any

from .lalr_engine import parse_text
from .loader import load_export_model, load_json_file
from .scanner_adapter import ScannerAdapter
from .table_compiler import compile_tables
from .validator import validate_against_schema, validate_export_model


class Parser:
    def __init__(self, export_model, actions: Any = None, prefer_scnr2: bool = True):
        self.model = export_model
        self.actions = actions
        self.prefer_scnr2 = prefer_scnr2
        validate_export_model(self.model)
        self.compiled = compile_tables(self.model)

    def parse(self, text: str):
        scanner = ScannerAdapter(self.model.scanner, prefer_scnr2=self.prefer_scnr2)
        scanner.feed(text)
        return parse_text(self.model, self.compiled, scanner, self.actions)


SCHEMA_PATH = (
    Path(__file__).resolve().parents[4]
    / "crates"
    / "parol"
    / "schemas"
    / "parser-export-model.v1.schema.json"
)


def parser_from_export_file(
    export_path: str | Path,
    actions: Any = None,
    prefer_scnr2: bool = True,
) -> Parser:
    raw = load_json_file(export_path)
    validate_against_schema(raw, SCHEMA_PATH)
    model = load_export_model(export_path)
    return Parser(model, actions=actions, prefer_scnr2=prefer_scnr2)
