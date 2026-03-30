from __future__ import annotations

from typing import Any

from .model import ExportModel, ParseError, ParseResult
from .scanner_adapter import ScannerAdapter
from .table_compiler import CompiledTables, expected_terminals


def _to_snake_case(name: str) -> str:
    out: list[str] = []
    for idx, ch in enumerate(name):
        if ch.isupper() and idx > 0:
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def _apply_semantic_action(
    actions: Any,
    model: ExportModel,
    lhs_nt: int,
    prod_idx: int,
    rhs_values: list[Any],
) -> Any:
    if hasattr(actions, "on_reduce"):
        return actions.on_reduce(lhs_nt, prod_idx, rhs_values)

    non_terminal_name = model.non_terminal_names[lhs_nt]
    snake_name = _to_snake_case(non_terminal_name)
    payload = {
        "non_terminal": non_terminal_name,
        "non_terminal_index": lhs_nt,
        "production_index": prod_idx,
        "production_text": model.productions[prod_idx].text,
        "children": rhs_values,
    }

    for method_name in (f"on_{snake_name}", snake_name, non_terminal_name):
        method = getattr(actions, method_name, None)
        if callable(method):
            return method(payload)

    generic = getattr(actions, "on_non_terminal", None)
    if callable(generic):
        return generic(non_terminal_name, payload)

    return payload


def parse_text(
    model: ExportModel,
    compiled: CompiledTables,
    scanner: ScannerAdapter,
    actions: Any = None,
) -> ParseResult:
    state_stack: list[int] = [0]
    value_stack: list[Any] = []
    reductions: list[tuple[int, int]] = []

    lookahead = scanner.next_token()

    while True:
        state = state_stack[-1]
        action_ref = compiled.action_table[state].get(lookahead.index)

        if action_ref is None:
            expected = expected_terminals(compiled, state)
            raise ParseError(
                message=(
                    f"Parse error at offset {lookahead.offset}: token index {lookahead.index} "
                    f"('{lookahead.lexeme}') not expected; "
                    f"expected token indices: {expected}"
                ),
                found_token_index=lookahead.index,
                found_lexeme=lookahead.lexeme,
                offset=lookahead.offset,
                expected_token_indices=expected,
            )

        action = compiled.action_pool[action_ref]

        if action.kind == "Shift":
            assert action.shift_state is not None
            state_stack.append(action.shift_state)
            value_stack.append(lookahead)
            lookahead = scanner.next_token()
            continue

        if action.kind == "Reduce":
            assert action.reduce_non_terminal is not None
            assert action.reduce_production is not None

            prod_idx = action.reduce_production
            lhs_nt = action.reduce_non_terminal
            rhs_len = compiled.production_rhs_len[prod_idx]

            rhs_values: list[Any] = []
            if rhs_len > 0:
                rhs_values = value_stack[-rhs_len:]
                del value_stack[-rhs_len:]
                del state_stack[-rhs_len:]

            if actions is not None:
                reduced_value = _apply_semantic_action(actions, model, lhs_nt, prod_idx, rhs_values)
            else:
                reduced_value = {
                    "non_terminal": model.non_terminal_names[lhs_nt],
                    "non_terminal_index": lhs_nt,
                    "production_index": prod_idx,
                    "production_text": model.productions[prod_idx].text,
                    "children": rhs_values,
                }

            goto_state = compiled.goto_table[state_stack[-1]].get(lhs_nt)
            if goto_state is None:
                raise ParseError(
                    message=(
                        f"Missing goto for state {state_stack[-1]} and non-terminal {lhs_nt}"
                    ),
                    found_token_index=lookahead.index,
                    found_lexeme=lookahead.lexeme,
                    offset=lookahead.offset,
                    expected_token_indices=[],
                )

            state_stack.append(goto_state)
            value_stack.append(reduced_value)
            reductions.append((lhs_nt, prod_idx))
            continue

        # Accept
        return ParseResult(
            accepted=True,
            reductions=reductions,
            value=value_stack[-1] if value_stack else None,
        )
