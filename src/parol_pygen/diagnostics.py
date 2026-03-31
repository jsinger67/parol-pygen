from __future__ import annotations

from .model import ExportModel


def terminal_label(model: ExportModel, token_index: int) -> str:
    for terminal in model.scanner.terminals:
        if terminal.index == token_index:
            return terminal.pattern
    if token_index == 0:
        return "EOI"
    return f"index:{token_index}"


def terminal_labels(model: ExportModel, token_indices: list[int]) -> list[str]:
    return [terminal_label(model, idx) for idx in token_indices]