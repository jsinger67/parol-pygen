from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .model import ParseToken, ScannerModel

EOF_TOKEN_INDEX = 0


@dataclass(frozen=True)
class _CompiledTerminal:
    index: int
    regex: re.Pattern[str]
    scanner_states: set[int]


class ScannerAdapter:
    """
    Minimal scanner adapter for PoC.

    This implementation compiles regexes from export scanner terminals and emits
    terminal indices as used by the parse table.
    """

    def __init__(self, scanner_model: ScannerModel, prefer_scnr2: bool = True) -> None:
        self._scanner_model = scanner_model
        self._text = ""
        self._offset = 0
        self._compiled: list[_CompiledTerminal] = []
        self._state_by_name: dict[str, int] = {
            s.scanner_name: s.scanner_state for s in scanner_model.scanner_states
        }
        self._scanner_states: dict[int, Any] = {
            s.scanner_state: s for s in scanner_model.scanner_states
        }
        self._initial_state = self._state_by_name.get(
            "INITIAL",
            scanner_model.scanner_states[0].scanner_state if scanner_model.scanner_states else 0,
        )
        self._state_stack: list[int] = [self._initial_state]
        self._prefer_scnr2 = prefer_scnr2
        self._scnr2_scanner: Any | None = None
        self._scnr2_matches: list[Any] = []
        self._scnr2_match_index = 0
        self._buffer: list[ParseToken] = []

        if prefer_scnr2:
            self._try_init_scnr2(scanner_model)

        # Compile Python regex terminals only when fallback scanner is needed.
        if self._scnr2_scanner is None:
            self._compiled = self._compile_terminals(scanner_model)

    def _try_init_scnr2(self, scanner_model: ScannerModel) -> None:
        try:
            import scnr2  # type: ignore

            definition = self._build_scnr2_definition(scanner_model)
            self._scnr2_scanner = scnr2.Scanner(definition)
        except Exception:
            # Fall back to regex scanner if scnr2 is unavailable or definition is not accepted.
            self._scnr2_scanner = None

    def _dsl_regex(self, pattern: str) -> str:
        return 'r"' + pattern.replace('"', '\\"') + '"'

    def _build_scnr2_definition(self, scanner_model: ScannerModel) -> str:
        state_name = {
            s.scanner_state: s.scanner_name for s in scanner_model.scanner_states
        }
        terms_by_state: dict[int, list[Any]] = {s.scanner_state: [] for s in scanner_model.scanner_states}
        for t in scanner_model.terminals:
            for st in t.scanner_states:
                terms_by_state.setdefault(st, []).append(t)

        lines: list[str] = ["ParolExportScanner {"]
        for s in scanner_model.scanner_states:
            lines.append(f"    mode {s.scanner_name} {{")
            for t in sorted(terms_by_state.get(s.scanner_state, []), key=lambda x: x.index):
                pattern = t.expanded_pattern if t.kind == "Raw" else t.pattern
                lookahead = getattr(t, "lookahead", None)
                if lookahead is None:
                    lines.append(f"        token {self._dsl_regex(pattern)} => {t.index};")
                else:
                    la_pat = self._dsl_regex(getattr(lookahead, "pattern"))
                    if getattr(lookahead, "is_positive"):
                        lines.append(
                            f"        token {self._dsl_regex(pattern)} followed by {la_pat} => {t.index};"
                        )
                    else:
                        lines.append(
                            f"        token {self._dsl_regex(pattern)} not followed by {la_pat} => {t.index};"
                        )

            for tr in s.transitions:
                if tr.kind == "Enter":
                    target = tr.target_scanner_name or state_name.get(tr.target_scanner_state, "INITIAL")
                    lines.append(f"        on {tr.terminal_index} enter {target};")
                elif tr.kind == "Push":
                    target = tr.target_scanner_name or state_name.get(tr.target_scanner_state, "INITIAL")
                    lines.append(f"        on {tr.terminal_index} push {target};")
                elif tr.kind == "Pop":
                    lines.append(f"        on {tr.terminal_index} pop;")
            lines.append("    }")
        lines.append("}")
        return "\n".join(lines)

    def _compile_terminals(self, scanner_model: ScannerModel) -> list[_CompiledTerminal]:
        terminals = []
        # Sort by token index to keep deterministic behavior aligned with exported order.
        for t in sorted(scanner_model.terminals, key=lambda x: x.index):
            pattern = t.expanded_pattern if t.kind == "Raw" else t.pattern
            terminals.append(
                _CompiledTerminal(t.index, re.compile(pattern), set(t.scanner_states))
            )
        return terminals

    def _current_state(self) -> int:
        return self._state_stack[-1] if self._state_stack else self._initial_state

    def _skip_tokens_for_state(self, state: int) -> set[int]:
        scanner_state = self._scanner_states.get(state)
        if scanner_state is None:
            return set()
        return set(scanner_state.skip_tokens)

    def _transition_target(self, transition: Any) -> int:
        if transition.target_scanner_state is not None:
            return transition.target_scanner_state
        if transition.target_scanner_name is not None:
            return self._state_by_name.get(transition.target_scanner_name, self._initial_state)
        return self._initial_state

    def _apply_transition(self, token_index: int) -> None:
        current = self._current_state()
        scanner_state = self._scanner_states.get(current)
        if scanner_state is None:
            return

        transition = next(
            (t for t in scanner_state.transitions if t.terminal_index == token_index),
            None,
        )
        if transition is None:
            return

        if transition.kind == "Enter":
            self._state_stack[-1] = self._transition_target(transition)
        elif transition.kind == "Push":
            self._state_stack.append(self._transition_target(transition))
        elif transition.kind == "Pop":
            if len(self._state_stack) > 1:
                self._state_stack.pop()

    def _prepare_text_for_scnr2(self, text: str) -> str:
        # PoC alignment: emulate scanner-level ignored comments configured on INITIAL state.
        if not self._scanner_model.scanner_states:
            return text

        initial = next(
            (s for s in self._scanner_model.scanner_states if s.scanner_name == "INITIAL"),
            self._scanner_model.scanner_states[0],
        )

        prepared = text
        for start_pat, end_pat in initial.block_comments:
            prepared = re.sub(
                start_pat + r".*?" + end_pat,
                " ",
                prepared,
                flags=re.DOTALL,
            )
        for line_pat in initial.line_comments:
            prepared = re.sub(
                line_pat + r".*$",
                " ",
                prepared,
                flags=re.MULTILINE,
            )
        return prepared

    def feed(self, text: str) -> None:
        self._text = text
        self._offset = 0
        self._buffer = []
        self._state_stack = [self._initial_state]
        if self._scnr2_scanner is not None:
            prepared = self._prepare_text_for_scnr2(text)
            self._scnr2_matches = list(self._scnr2_scanner.find_matches_with_position(prepared))
            self._scnr2_match_index = 0

    def _skip_ws(self) -> None:
        # PoC: whitespace skipping aligned with default INITIAL scanner behavior.
        while self._offset < len(self._text) and self._text[self._offset].isspace():
            self._offset += 1

    def _read_next_raw_token(self) -> ParseToken:
        if self._scnr2_scanner is not None:
            while True:
                if self._scnr2_match_index >= len(self._scnr2_matches):
                    return ParseToken(index=EOF_TOKEN_INDEX, lexeme="", offset=len(self._text))
                m = self._scnr2_matches[self._scnr2_match_index]
                self._scnr2_match_index += 1
                token = ParseToken(index=int(m.token_type), lexeme=str(m.text), offset=int(m.start))
                skip_tokens = self._skip_tokens_for_state(self._current_state())
                self._apply_transition(token.index)
                if token.index in skip_tokens:
                    continue
                return token

        while True:
            self._skip_ws()
            if self._offset >= len(self._text):
                return ParseToken(index=EOF_TOKEN_INDEX, lexeme="", offset=self._offset)

            # Longest-match then lowest token index to improve determinism.
            best_index = -1
            best_lexeme = ""
            state = self._current_state()

            for term in self._compiled:
                if state not in term.scanner_states:
                    continue
                match = term.regex.match(self._text, self._offset)
                if not match:
                    continue
                lexeme = match.group(0)
                if not lexeme:
                    continue
                if len(lexeme) > len(best_lexeme) or (
                    len(lexeme) == len(best_lexeme)
                    and (best_index == -1 or term.index < best_index)
                ):
                    best_index = term.index
                    best_lexeme = lexeme

            if best_index == -1:
                bad = self._text[self._offset : self._offset + 1]
                raise ValueError(f"Lexing failed at offset {self._offset}: '{bad}'")

            token = ParseToken(index=best_index, lexeme=best_lexeme, offset=self._offset)
            self._offset += len(best_lexeme)

            skip_tokens = self._skip_tokens_for_state(state)
            self._apply_transition(token.index)
            if token.index in skip_tokens:
                continue
            return token

    def peek_token(self, lookahead: int = 0) -> ParseToken:
        if lookahead < 0:
            raise ValueError("lookahead must be >= 0")

        while len(self._buffer) <= lookahead:
            self._buffer.append(self._read_next_raw_token())

        return self._buffer[lookahead]

    def consume_token(self) -> ParseToken:
        self.peek_token(0)
        return self._buffer.pop(0)

    def next_token(self) -> ParseToken:
        return self.consume_token()
