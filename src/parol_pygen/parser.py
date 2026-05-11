from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

from .lalr_engine import parse_text
from .llk_engine import parse_text as parse_text_llk
from .loader import load_export_model, load_json_file
from .scanner_adapter import ScannerAdapter
from .table_compiler import compile_tables
from .validator import ValidationError, validate_against_schema, validate_export_model


class Parser:
    def __init__(self, export_model, actions: Any = None, prefer_scnr2: bool = True):
        self.model = export_model
        self.actions = actions
        self.prefer_scnr2 = prefer_scnr2
        validate_export_model(self.model)
        self.compiled = compile_tables(self.model) if self.model.algorithm == "Lalr1" else None

    def parse(self, text: str):
        scanner = ScannerAdapter(self.model.scanner, prefer_scnr2=self.prefer_scnr2)
        scanner.feed(text)
        if self.model.algorithm == "Lalr1":
            assert self.compiled is not None
            return parse_text(self.model, self.compiled, scanner, self.actions)
        if self.model.algorithm == "Llk":
            return parse_text_llk(self.model, scanner, self.actions)
        raise ValidationError(f"Unsupported parser algorithm: {self.model.algorithm}")


SCHEMA_V1_PATH = Path(files("parol_pygen.schemas").joinpath("parser-export-model.v1.schema.json"))
SCHEMA_V2_PATH = Path(files("parol_pygen.schemas").joinpath("parser-export-model.v2.schema.json"))
# Default schema path kept for compatibility with existing imports.
SCHEMA_PATH = SCHEMA_V2_PATH


def schema_path_for_export(raw_export: dict[str, Any]) -> Path:
    version = raw_export.get("version")
    if version == 1:
        return SCHEMA_V1_PATH
    if version == 2:
        return SCHEMA_V2_PATH
    raise ValidationError(f"Unsupported export version: {version}")


def parser_from_export_file(
    export_path: str | Path,
    actions: Any = None,
    prefer_scnr2: bool = True,
) -> Parser:
    raw = load_json_file(export_path)
    validate_against_schema(raw, schema_path_for_export(raw))
    model = load_export_model(export_path)
    return Parser(model, actions=actions, prefer_scnr2=prefer_scnr2)
