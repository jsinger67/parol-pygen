from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProductionSymbol:
    kind: str  # "NonTerminal" | "Terminal"
    non_terminal_index: int | None = None
    terminal_index: int | None = None
    clipped: bool = False


@dataclass(frozen=True)
class Production:
    production_index: int
    lhs_index: int
    rhs: list[ProductionSymbol]
    text: str


@dataclass(frozen=True)
class LalrAction:
    kind: str  # "Shift" | "Reduce" | "Accept"
    shift_state: int | None = None
    reduce_non_terminal: int | None = None
    reduce_production: int | None = None


@dataclass(frozen=True)
class LalrState:
    actions: list[tuple[int, int]]
    gotos: list[tuple[int, int]]


@dataclass(frozen=True)
class LalrParseTable:
    actions: list[LalrAction]
    states: list[LalrState]


@dataclass(frozen=True)
class ScannerTerminal:
    index: int
    pattern: str
    expanded_pattern: str
    kind: str
    scanner_states: list[int]


@dataclass(frozen=True)
class ScannerTransition:
    terminal_index: int
    kind: str
    target_scanner_state: int | None
    target_scanner_name: str | None = None


@dataclass(frozen=True)
class ScannerState:
    scanner_state: int
    scanner_name: str
    line_comments: list[str]
    block_comments: list[tuple[str, str]]
    auto_newline: bool
    auto_ws: bool
    allow_unmatched: bool
    transitions: list[ScannerTransition]


@dataclass(frozen=True)
class ScannerModel:
    terminals: list[ScannerTerminal]
    scanner_states: list[ScannerState]


@dataclass(frozen=True)
class LookaheadTransition:
    from_state: int
    term: int
    to_state: int
    prod_num: int


@dataclass(frozen=True)
class LookaheadAutomaton:
    non_terminal_index: int
    non_terminal_name: str
    prod0: int
    k: int
    transitions: list[LookaheadTransition]


@dataclass(frozen=True)
class ProductionDatatype:
    production_index: int


@dataclass(frozen=True)
class ExportModel:
    version: int
    algorithm: str
    non_terminal_names: list[str]
    start_symbol_index: int
    productions: list[Production]
    lookahead_automata: list[LookaheadAutomaton]
    lalr_parse_table: LalrParseTable | None
    scanner: ScannerModel
    production_datatypes: list[ProductionDatatype]


@dataclass(frozen=True)
class ParseToken:
    index: int
    lexeme: str
    offset: int


@dataclass
class ParseResult:
    accepted: bool
    reductions: list[tuple[int, int]]
    value: Any = None


class ParseError(Exception):
    def __init__(
        self,
        message: str,
        found_token_index: int,
        found_lexeme: str,
        offset: int,
        expected_token_indices: list[int],
    ) -> None:
        super().__init__(message)
        self.found_token_index = found_token_index
        self.found_lexeme = found_lexeme
        self.offset = offset
        self.expected_token_indices = expected_token_indices


def _parse_symbol(item: dict[str, Any]) -> ProductionSymbol:
    if "NonTerminal" in item:
        return ProductionSymbol(kind="NonTerminal", non_terminal_index=int(item["NonTerminal"]))
    terminal = item["Terminal"]
    return ProductionSymbol(
        kind="Terminal",
        terminal_index=int(terminal["index"]),
        clipped=bool(terminal["clipped"]),
    )


def _parse_action(item: Any) -> LalrAction:
    if isinstance(item, str):
        if item != "Accept":
            raise ValueError(f"Unsupported LALR action string: {item}")
        return LalrAction(kind="Accept")
    if "Shift" in item:
        return LalrAction(kind="Shift", shift_state=int(item["Shift"]))
    if "Reduce" in item:
        nt, prod = item["Reduce"]
        return LalrAction(
            kind="Reduce",
            reduce_non_terminal=int(nt),
            reduce_production=int(prod),
        )
    raise ValueError(f"Unsupported LALR action payload: {item}")


def parse_export_model(raw: dict[str, Any]) -> ExportModel:
    productions = [
        Production(
            production_index=int(p["production_index"]),
            lhs_index=int(p["lhs_index"]),
            rhs=[_parse_symbol(s) for s in p["rhs"]],
            text=str(p["text"]),
        )
        for p in raw["productions"]
    ]

    lalr = None
    if raw["lalr_parse_table"] is not None:
        table = raw["lalr_parse_table"]
        lalr = LalrParseTable(
            actions=[_parse_action(a) for a in table["actions"]],
            states=[
                LalrState(
                    actions=[(int(x[0]), int(x[1])) for x in s["actions"]],
                    gotos=[(int(x[0]), int(x[1])) for x in s["gotos"]],
                )
                for s in table["states"]
            ],
        )

    scanner = ScannerModel(
        terminals=[
            ScannerTerminal(
                index=int(t["index"]),
                pattern=str(t["pattern"]),
                expanded_pattern=str(t["expanded_pattern"]),
                kind=str(t["kind"]),
                scanner_states=[int(s) for s in t["scanner_states"]],
            )
            for t in raw["scanner"]["terminals"]
        ],
        scanner_states=[
            ScannerState(
                scanner_state=int(s["scanner_state"]),
                scanner_name=str(s["scanner_name"]),
                line_comments=[str(c) for c in s.get("line_comments", [])],
                block_comments=[
                    (str(c[0]), str(c[1]))
                    for c in s.get("block_comments", [])
                    if isinstance(c, list) and len(c) == 2
                ],
                auto_newline=bool(s["auto_newline"]),
                auto_ws=bool(s["auto_ws"]),
                allow_unmatched=bool(s["allow_unmatched"]),
                transitions=[
                    ScannerTransition(
                        terminal_index=int(tr["terminal_index"]),
                        kind=str(tr["kind"]),
                        target_scanner_state=(
                            None
                            if tr["target_scanner_state"] is None
                            else int(tr["target_scanner_state"])
                        ),
                        target_scanner_name=(
                            None
                            if tr.get("target_scanner_name") is None
                            else str(tr.get("target_scanner_name"))
                        ),
                    )
                    for tr in s["transitions"]
                ],
            )
            for s in raw["scanner"]["scanner_states"]
        ],
    )

    lookahead_automata = [
        LookaheadAutomaton(
            non_terminal_index=int(a["non_terminal_index"]),
            non_terminal_name=str(a["non_terminal_name"]),
            prod0=int(a["prod0"]),
            k=int(a["k"]),
            transitions=[
                LookaheadTransition(
                    from_state=int(t["from_state"]),
                    term=int(t["term"]),
                    to_state=int(t["to_state"]),
                    prod_num=int(t["prod_num"]),
                )
                for t in a["transitions"]
            ],
        )
        for a in raw["lookahead_automata"]
    ]

    production_datatypes = [
        ProductionDatatype(production_index=int(d["production_index"]))
        for d in raw["production_datatypes"]
    ]

    return ExportModel(
        version=int(raw["version"]),
        algorithm=str(raw["algorithm"]),
        non_terminal_names=[str(n) for n in raw["non_terminal_names"]],
        start_symbol_index=int(raw["start_symbol_index"]),
        productions=productions,
        lookahead_automata=lookahead_automata,
        lalr_parse_table=lalr,
        scanner=scanner,
        production_datatypes=production_datatypes,
    )
