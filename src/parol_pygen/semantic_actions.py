from __future__ import annotations

from typing import Any

from .model import ExportModel


def to_snake_case(name: str) -> str:
    out: list[str] = []
    for idx, ch in enumerate(name):
        if ch.isupper() and idx > 0:
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def dispatch_non_terminal_payload(
    actions: Any,
    non_terminal_name: str,
    payload: Any,
    *,
    snake_case_name: str | None = None,
) -> Any:
    snake_name = snake_case_name or to_snake_case(non_terminal_name)

    for method_name in (f"on_{snake_name}", snake_name, non_terminal_name):
        method = getattr(actions, method_name, None)
        if callable(method):
            return method(payload)

    generic = getattr(actions, "on_non_terminal", None)
    if callable(generic):
        return generic(non_terminal_name, payload)

    return payload


def apply_semantic_action(
    actions: Any,
    model: ExportModel,
    lhs_nt: int,
    prod_idx: int,
    rhs_values: list[Any],
) -> Any:
    producer = getattr(actions, "on_production", None)
    if callable(producer):
        return producer(lhs_nt, prod_idx, rhs_values)

    reducer = getattr(actions, "on_reduce", None)
    if callable(reducer):
        return reducer(lhs_nt, prod_idx, rhs_values)

    non_terminal_name = model.non_terminal_names[lhs_nt]
    snake_name = to_snake_case(non_terminal_name)
    payload = {
        "non_terminal": non_terminal_name,
        "non_terminal_index": lhs_nt,
        "production_index": prod_idx,
        "production_text": model.productions[prod_idx].text,
        "children": rhs_values,
    }

    return dispatch_non_terminal_payload(
        actions,
        non_terminal_name,
        payload,
        snake_case_name=snake_name,
    )
