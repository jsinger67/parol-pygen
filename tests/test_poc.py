from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from parol_pygen.generator import generate_package
from parol_pygen.loader import load_json_file
from parol_pygen.model import ParseError
from parol_pygen.parser import SCHEMA_PATH, parser_from_export_file
from parol_pygen.validator import validate_against_schema


FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "crates"
    / "parol"
    / "tests"
    / "data"
    / "arg_tests"
    / "export_lalr1.expected.json"
)


class PocTests(unittest.TestCase):
    def test_fixture_validates_against_schema(self) -> None:
        raw = load_json_file(FIXTURE)
        validate_against_schema(raw, SCHEMA_PATH)

    def test_lalr_parser_accepts_valid_sample(self) -> None:
        parser = parser_from_export_file(FIXTURE)
        result = parser.parse("Var abc End")
        self.assertTrue(result.accepted)

    def test_lalr_parser_rejects_invalid_sample(self) -> None:
        parser = parser_from_export_file(FIXTURE)
        with self.assertRaises(ParseError) as ctx:
            parser.parse("Var abc")
        self.assertTrue(len(ctx.exception.expected_token_indices) > 0)

    def test_generate_package_outputs_importable_shape(self) -> None:
        with TemporaryDirectory() as tmp:
            out = generate_package(FIXTURE, tmp, "demo_parser")
            self.assertTrue((out / "__init__.py").exists())
            self.assertTrue((out / "actions.py").exists())
            self.assertTrue((out / "nodes.py").exists())
            self.assertTrue((out / "parser.py").exists())
            self.assertTrue((out / "user_actions.py").exists())
            self.assertTrue((out / "export.json").exists())

    def test_non_terminal_callback_actions_are_user_facing(self) -> None:
        class Actions:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def on_start_list(self, node: dict[str, object]) -> dict[str, object]:
                self.calls.append(str(node["non_terminal"]))
                return {"kind": "StartList", "children": node["children"]}

        actions = Actions()
        parser = parser_from_export_file(FIXTURE, actions=actions)
        result = parser.parse("Var abc End")

        self.assertTrue(result.accepted)
        self.assertIn("StartList", actions.calls)


if __name__ == "__main__":
    unittest.main()
