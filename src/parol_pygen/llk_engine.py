from __future__ import annotations

from typing import Any

from .diagnostics import terminal_labels
from .model import ExportModel, ParseError, ParseResult
from .scanner_adapter import ScannerAdapter
from .semantic_actions import apply_semantic_action


def _lookahead_indices(scanner: ScannerAdapter, width: int) -> list[int]:
    if width <= 0:
        return []
    return [scanner.peek_token(i).index for i in range(width)]


def _select_production(model: ExportModel, scanner: ScannerAdapter, non_terminal: int) -> int:
    non_terminal_name = model.non_terminal_names[non_terminal]
    automaton = next(
        (a for a in model.lookahead_automata if a.non_terminal_index == non_terminal),
        None,
    )
    if automaton is None:
        found = scanner.peek_token(0)
        raise ParseError(
            message=(
                f"Missing lookahead automaton for non-terminal {non_terminal} "
                f"('{non_terminal_name}')"
            ),
            found_token_index=found.index,
            found_lexeme=found.lexeme,
            offset=found.offset,
            expected_token_indices=[],
        )

    state = 0
    prod_num = automaton.prod0
    last_prod_num = prod_num if prod_num >= 0 else -1

    for i in range(automaton.k):
        lookahead_token_index = scanner.peek_token(i).index
        transition = next(
            (
                t
                for t in automaton.transitions
                if t.from_state == state and t.term == lookahead_token_index
            ),
            None,
        )
        if transition is None:
            break

        state = transition.to_state
        prod_num = transition.prod_num
        if prod_num >= 0:
            last_prod_num = prod_num

    if prod_num >= 0:
        return prod_num
    if last_prod_num >= 0:
        return last_prod_num

    expected = sorted({t.term for t in automaton.transitions if t.from_state == state})
    found = scanner.peek_token(0)
    lookahead = _lookahead_indices(scanner, max(automaton.k, 1))
    expected_labels = terminal_labels(model, expected)
    lookahead_labels = terminal_labels(model, lookahead)
    raise ParseError(
        message=(
            f"Parse error at offset {found.offset}: token index {found.index} "
            f"('{found.lexeme}') not expected while predicting non-terminal "
            f"{non_terminal} ('{non_terminal_name}') at lookahead DFA state {state}; "
            f"lookahead token indices: {lookahead}; "
            f"lookahead terminal labels: {lookahead_labels}; "
            f"expected token indices: {expected}; "
            f"expected terminal labels: {expected_labels}"
        ),
        found_token_index=found.index,
        found_lexeme=found.lexeme,
        offset=found.offset,
        expected_token_indices=expected,
    )


def parse_text(model: ExportModel, scanner: ScannerAdapter, actions: Any = None) -> ParseResult:
    reductions: list[tuple[int, int]] = []

    def parse_non_terminal(non_terminal: int) -> Any:
        prod_idx = _select_production(model, scanner, non_terminal)
        production = model.productions[prod_idx]

        rhs_values: list[Any] = []
        for sym in production.rhs:
            if sym.kind == "Terminal":
                assert sym.terminal_index is not None
                lookahead = scanner.peek_token(0)
                if lookahead.index != sym.terminal_index:
                    expected_labels = terminal_labels(model, [sym.terminal_index])
                    lhs_nt = production.lhs_index
                    raise ParseError(
                        message=(
                            f"Parse error at offset {lookahead.offset}: token index {lookahead.index} "
                            f"('{lookahead.lexeme}') not expected in production {prod_idx} "
                            f"for non-terminal {lhs_nt}; "
                            f"expected token indices: [{sym.terminal_index}]; "
                            f"expected terminal labels: {expected_labels}"
                        ),
                        found_token_index=lookahead.index,
                        found_lexeme=lookahead.lexeme,
                        offset=lookahead.offset,
                        expected_token_indices=[sym.terminal_index],
                    )
                rhs_values.append(scanner.consume_token())
            else:
                assert sym.non_terminal_index is not None
                rhs_values.append(parse_non_terminal(sym.non_terminal_index))

        lhs_nt = production.lhs_index
        reductions.append((lhs_nt, prod_idx))

        if actions is not None:
            return apply_semantic_action(actions, model, lhs_nt, prod_idx, rhs_values)

        return {
            "non_terminal": model.non_terminal_names[lhs_nt],
            "non_terminal_index": lhs_nt,
            "production_index": prod_idx,
            "production_text": production.text,
            "children": rhs_values,
        }

    value = parse_non_terminal(model.start_symbol_index)

    tail = scanner.peek_token(0)
    if tail.index != 0:
        expected_labels = terminal_labels(model, [0])
        raise ParseError(
            message=(
                f"Parse error at offset {tail.offset}: unprocessed token index {tail.index} "
                f"('{tail.lexeme}') after parse completion; expected token indices: [0]; "
                f"expected terminal labels: {expected_labels}"
            ),
            found_token_index=tail.index,
            found_lexeme=tail.lexeme,
            offset=tail.offset,
            expected_token_indices=[0],
        )

    return ParseResult(accepted=True, reductions=reductions, value=value)
