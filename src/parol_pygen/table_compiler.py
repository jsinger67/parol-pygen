from __future__ import annotations

from dataclasses import dataclass

from .model import ExportModel, LalrAction


@dataclass(frozen=True)
class CompiledTables:
    action_pool: list[LalrAction]
    action_table: list[dict[int, int]]
    goto_table: list[dict[int, int]]
    production_rhs_len: list[int]
    production_lhs_index: list[int]


def compile_tables(model: ExportModel) -> CompiledTables:
    assert model.lalr_parse_table is not None

    action_pool = model.lalr_parse_table.actions
    action_table: list[dict[int, int]] = []
    goto_table: list[dict[int, int]] = []

    for state in model.lalr_parse_table.states:
        action_table.append({terminal: action_ref for terminal, action_ref in state.actions})
        goto_table.append({non_terminal: goto for non_terminal, goto in state.gotos})

    production_rhs_len = [len(p.rhs) for p in model.productions]
    production_lhs_index = [p.lhs_index for p in model.productions]

    return CompiledTables(
        action_pool=action_pool,
        action_table=action_table,
        goto_table=goto_table,
        production_rhs_len=production_rhs_len,
        production_lhs_index=production_lhs_index,
    )


def expected_terminals(compiled: CompiledTables, state: int) -> list[int]:
    return sorted(compiled.action_table[state].keys())
