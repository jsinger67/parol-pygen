from __future__ import annotations

from pathlib import Path
from typing import Any

from .model import ExportModel


class ValidationError(Exception):
    pass


def _load_json_schema_validator():
    try:
        import jsonschema  # type: ignore
    except Exception as exc:  # pragma: no cover - import error path
        raise ValidationError(
            "jsonschema is required. Install with `pip install jsonschema`."
        ) from exc
    return jsonschema


def validate_against_schema(raw_export: dict[str, Any], schema_path: str | Path) -> None:
    jsonschema = _load_json_schema_validator()
    import json

    with Path(schema_path).open("r", encoding="utf-8") as f:
        schema = json.load(f)

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(raw_export), key=lambda e: e.path)
    if errors:
        first = errors[0]
        path = "/".join(str(x) for x in first.path)
        raise ValidationError(f"Schema validation failed at '{path}': {first.message}")


def validate_export_model(model: ExportModel) -> None:
    if model.version != 1:
        raise ValidationError(f"Unsupported export version: {model.version}")

    if model.algorithm != "Lalr1":
        raise ValidationError(
            f"PoC currently supports Lalr1 only. Found: {model.algorithm}"
        )

    if model.lalr_parse_table is None:
        raise ValidationError("lalr_parse_table is required for Lalr1")

    if model.lookahead_automata:
        raise ValidationError("lookahead_automata must be empty for Lalr1")

    if not model.non_terminal_names:
        raise ValidationError("non_terminal_names must not be empty")

    if model.start_symbol_index >= len(model.non_terminal_names):
        raise ValidationError("start_symbol_index out of range")

    if not model.productions:
        raise ValidationError("productions must not be empty")

    if not model.scanner.scanner_states:
        raise ValidationError("scanner.scanner_states must not be empty")

    if len(model.production_datatypes) != len(model.productions):
        raise ValidationError("production_datatypes length must match productions")
