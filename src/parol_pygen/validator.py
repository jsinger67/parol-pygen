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
                "jsonschema is required. Install with `uv pip install jsonschema` (or `pip install jsonschema`)."
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

    if model.algorithm == "Lalr1":
        _validate_lalr1_model(model)
    elif model.algorithm == "Llk":
        _validate_llk_model(model)
    else:
        raise ValidationError(f"Unsupported parser algorithm: {model.algorithm}")

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


def _validate_lalr1_model(model: ExportModel) -> None:
    if model.lalr_parse_table is None:
        raise ValidationError("lalr_parse_table is required for Lalr1")

    if model.lookahead_automata:
        raise ValidationError("lookahead_automata must be empty for Lalr1")


def _validate_llk_model(model: ExportModel) -> None:
    if model.lalr_parse_table is not None:
        raise ValidationError("lalr_parse_table must be null for Llk")

    if not model.lookahead_automata:
        raise ValidationError("lookahead_automata must not be empty for Llk")

    max_nt_index = len(model.non_terminal_names) - 1
    max_prod_index = len(model.productions) - 1

    for automaton in model.lookahead_automata:
        if automaton.non_terminal_index < 0 or automaton.non_terminal_index > max_nt_index:
            raise ValidationError("lookahead_automata contains non_terminal_index out of range")
        if automaton.k < 0:
            raise ValidationError("lookahead_automata contains negative k")
        if automaton.prod0 != -1 and (automaton.prod0 < 0 or automaton.prod0 > max_prod_index):
            raise ValidationError("lookahead_automata contains prod0 out of range")

        expected_nt_name = model.non_terminal_names[automaton.non_terminal_index]
        if automaton.non_terminal_name != expected_nt_name:
            raise ValidationError(
                "lookahead_automata non_terminal_name does not match non_terminal_index"
            )

        for tr in automaton.transitions:
            if tr.from_state < 0 or tr.to_state < 0:
                raise ValidationError("lookahead_automata transition states must be >= 0")
            if tr.term < 0:
                raise ValidationError("lookahead_automata transition term must be >= 0")
            if tr.prod_num != -1 and (tr.prod_num < 0 or tr.prod_num > max_prod_index):
                raise ValidationError("lookahead_automata transition prod_num out of range")
