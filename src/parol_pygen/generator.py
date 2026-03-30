from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .loader import load_json_file
from .model import ExportModel, parse_export_model
from .parser import SCHEMA_PATH
from .validator import validate_against_schema


def _normalize_package_name(name: str) -> str:
    return name.replace("-", "_")


def _to_snake_case(name: str) -> str:
    out: list[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0:
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def _to_type_name(non_terminal_name: str) -> str:
    return f"{non_terminal_name}Node"


def _render_nodes_module(model: ExportModel) -> str:
    lines: list[str] = [
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass",
        "from typing import Any",
        "",
        "",
        "@dataclass",
        "class NonTerminalNode:",
        "    non_terminal: str",
        "    non_terminal_index: int",
        "    production_index: int",
        "    production_text: str",
        "    children: list[Any]",
        "",
        "",
        "@dataclass",
        "class GenericNode(NonTerminalNode):",
        "    pass",
    ]

    for nt in model.non_terminal_names:
        lines.extend(
            [
                "",
                "",
                "@dataclass",
                f"class {_to_type_name(nt)}(NonTerminalNode):",
                "    pass",
            ]
        )

    lines.extend(["", "", "NODE_CLASS_BY_NAME = {"])
    for nt in model.non_terminal_names:
        lines.append(f"    \"{nt}\": {_to_type_name(nt)},")
    lines.append("}")

    return "\n".join(lines) + "\n"


def _render_actions_module(model: ExportModel) -> str:
    lines: list[str] = [
        "from __future__ import annotations",
        "",
        "from typing import Any, Protocol",
        "from .nodes import GenericNode, NonTerminalNode",
        "",
        "class ActionsProtocol(Protocol):",
    ]

    if not model.non_terminal_names:
        lines.append("    pass")
    else:
        for nt in model.non_terminal_names:
            method_name = f"on_{_to_snake_case(nt)}"
            lines.append(f"    def {method_name}(self, node: {_to_type_name(nt)}) -> Any: ...")

    lines.extend(
        [
            "",
            "",
            "class BaseActions:",
            "    \"\"\"Convenience base class implementing generic non-terminal dispatch hook.\"\"\"",
            "",
            "    def on_non_terminal(self, name: str, node: NonTerminalNode) -> Any:",
            "        return node",
        ]
    )

    if model.non_terminal_names:
        lines.insert(4, "from .nodes import " + ", ".join(_to_type_name(nt) for nt in model.non_terminal_names))

    return "\n".join(lines) + "\n"


def _render_user_actions_module(model: ExportModel) -> str:
    lines: list[str] = [
        "from __future__ import annotations",
        "",
        "from .actions import BaseActions",
        "from .nodes import NonTerminalNode",
        "",
        "",
        "class UserActions(BaseActions):",
        "    \"\"\"Edit this class and override on_<non_terminal> methods as needed.\"\"\"",
    ]

    if model.non_terminal_names:
        first_nt = model.non_terminal_names[0]
        first_type = _to_type_name(first_nt)
        lines.insert(4, f"from .nodes import {first_type}")
        lines.extend(
            [
                "",
                f"    def on_{_to_snake_case(first_nt)}(self, node: {first_type}):",
                "        return node",
            ]
        )
    else:
        lines.extend(["", "    pass"])

    lines.extend(
        [
            "",
            "    def on_non_terminal(self, name: str, node: NonTerminalNode):",
            "        return super().on_non_terminal(name, node)",
        ]
    )

    return "\n".join(lines) + "\n"


def _render_parser_module(model: ExportModel) -> str:
    type_names = ", ".join(_to_type_name(nt) for nt in model.non_terminal_names)
    imports = [
        "from __future__ import annotations",
        "",
        "from pathlib import Path",
        "from typing import Any",
        "",
        "from .actions import ActionsProtocol, BaseActions",
    ]
    if type_names:
        imports.append(f"from .nodes import GenericNode, NODE_CLASS_BY_NAME, NonTerminalNode, {type_names}")
    else:
        imports.append("from .nodes import GenericNode, NODE_CLASS_BY_NAME, NonTerminalNode")
    imports.extend(["from parol_pygen.parser import parser_from_export_file", ""])

    lines: list[str] = imports + [
        "",
        "def _to_snake_case(name: str) -> str:",
        "    out: list[str] = []",
        "    for idx, ch in enumerate(name):",
        "        if ch.isupper() and idx > 0:",
        "            out.append('_')",
        "        out.append(ch.lower())",
        "    return ''.join(out)",
        "",
        "",
        "class _RuntimeActionAdapter:",
        "    def __init__(self, user_actions: BaseActions | ActionsProtocol | None):",
        "        self._user_actions = user_actions",
        "",
        "    def _to_node(self, payload: dict[str, Any]) -> NonTerminalNode:",
        "        non_terminal = str(payload.get('non_terminal', ''))",
        "        cls = NODE_CLASS_BY_NAME.get(non_terminal, GenericNode)",
        "        return cls(",
        "            non_terminal=non_terminal,",
        "            non_terminal_index=int(payload.get('non_terminal_index', -1)),",
        "            production_index=int(payload.get('production_index', -1)),",
        "            production_text=str(payload.get('production_text', '')),",
        "            children=list(payload.get('children', [])),",
        "        )",
        "",
        "    def on_non_terminal(self, name: str, payload: dict[str, Any]) -> Any:",
        "        node = self._to_node(payload)",
        "        if self._user_actions is None:",
        "            return node",
        "        generic = getattr(self._user_actions, 'on_non_terminal', None)",
        "        if callable(generic):",
        "            return generic(name, node)",
        "        return node",
    ]

    for nt in model.non_terminal_names:
        method_name = f"on_{_to_snake_case(nt)}"
        lines.extend(
            [
                "",
                f"    def {method_name}(self, payload: dict[str, Any]) -> Any:",
                "        node = self._to_node(payload)",
                "        if self._user_actions is None:",
                "            return node",
                f"        method = getattr(self._user_actions, '{method_name}', None)",
                "        if callable(method):",
                "            return method(node)",
                f"        return self.on_non_terminal('{nt}', payload)",
            ]
        )

    lines.extend(
        [
            "",
            "",
            "class Parser:",
            "    def __init__(self, actions: BaseActions | ActionsProtocol | None = None):",
            "        export_path = Path(__file__).with_name('export.json')",
            "        self._adapter = _RuntimeActionAdapter(actions)",
            "        self._impl = parser_from_export_file(export_path, actions=self._adapter)",
            "",
            "    def parse(self, text: str) -> Any:",
            "        return self._impl.parse(text)",
        ]
    )

    return "\n".join(lines) + "\n"


def generate_package(export_path: str | Path, out_dir: str | Path, package_name: str) -> Path:
    raw = load_json_file(export_path)
    validate_against_schema(raw, SCHEMA_PATH)
    model = parse_export_model(raw)

    pkg_name = _normalize_package_name(package_name)
    target = Path(out_dir) / pkg_name
    target.mkdir(parents=True, exist_ok=True)

    export_target = target / "export.json"
    export_target.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    (target / "__init__.py").write_text(
        "from .actions import ActionsProtocol, BaseActions\n"
        "from .nodes import GenericNode, NonTerminalNode\n"
        "from .parser import Parser\n"
        "from .user_actions import UserActions\n\n"
        "__all__ = ['Parser', 'ActionsProtocol', 'BaseActions', 'UserActions', 'NonTerminalNode', 'GenericNode']\n",
        encoding="utf-8",
    )

    (target / "nodes.py").write_text(
        _render_nodes_module(model),
        encoding="utf-8",
    )

    (target / "actions.py").write_text(
        _render_actions_module(model),
        encoding="utf-8",
    )

    (target / "user_actions.py").write_text(
        _render_user_actions_module(model),
        encoding="utf-8",
    )

    (target / "parser.py").write_text(_render_parser_module(model), encoding="utf-8")

    return target
