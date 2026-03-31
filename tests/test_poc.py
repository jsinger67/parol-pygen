from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from parol_pygen.generator import generate_package
from parol_pygen.loader import load_export_model, load_json_file
from parol_pygen.model import ParseError
from parol_pygen.parser import SCHEMA_PATH, parser_from_export_file
from parol_pygen.validator import validate_against_schema, validate_export_model


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "export_lalr1.expected.json"
LLK_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "export_llk.expected.json"


class PocTests(unittest.TestCase):
    def _assert_parse_error_contract(
        self,
        exc: ParseError,
        *,
        found_token_index: int,
        expected_token_indices: list[int],
        message_fragments: list[str],
    ) -> None:
        self.assertEqual(exc.found_token_index, found_token_index)
        self.assertEqual(exc.expected_token_indices, expected_token_indices)
        message = str(exc)
        for fragment in message_fragments:
            self.assertIn(fragment, message)

    def test_fixture_validates_against_schema(self) -> None:
        raw = load_json_file(FIXTURE)
        validate_against_schema(raw, SCHEMA_PATH)

    def test_llk_fixture_validates_against_schema_and_model(self) -> None:
        raw = load_json_file(LLK_FIXTURE)
        validate_against_schema(raw, SCHEMA_PATH)
        model = load_export_model(LLK_FIXTURE)
        validate_export_model(model)

    def test_lalr_parser_accepts_valid_sample(self) -> None:
        parser = parser_from_export_file(FIXTURE)
        result = parser.parse("Var abc End")
        self.assertTrue(result.accepted)

    def test_lalr_parser_rejects_invalid_sample(self) -> None:
        parser = parser_from_export_file(FIXTURE)
        with self.assertRaises(ParseError) as ctx:
            parser.parse("Var abc")
        self.assertTrue(len(ctx.exception.expected_token_indices) > 0)

    def test_llk_parser_accepts_valid_sample(self) -> None:
        parser = parser_from_export_file(LLK_FIXTURE)
        result = parser.parse("Var abc End")
        self.assertTrue(result.accepted)

    def test_llk_parser_rejects_invalid_sample(self) -> None:
        parser = parser_from_export_file(LLK_FIXTURE)
        with self.assertRaises(ParseError) as ctx:
            parser.parse("Var abc")
        self.assertTrue(len(ctx.exception.expected_token_indices) > 0)

    def test_llk_parser_prediction_error_reports_expected_terminals(self) -> None:
        parser = parser_from_export_file(LLK_FIXTURE)
        with self.assertRaises(ParseError) as ctx:
            parser.parse("Var Var End")

        self._assert_parse_error_contract(
            ctx.exception,
            found_token_index=5,
            expected_token_indices=[6, 7],
            message_fragments=["expected token indices: [6, 7]"],
        )

    def test_lalr_error_message_contract(self) -> None:
        parser = parser_from_export_file(FIXTURE)
        with self.assertRaises(ParseError) as ctx:
            parser.parse("Var abc")

        self._assert_parse_error_contract(
            ctx.exception,
            found_token_index=0,
            expected_token_indices=[6, 7],
            message_fragments=[
                "expected token indices: [6, 7]",
                "expected terminal labels: ['End', '[a-z_][a-zA-Z0-9_]*']",
            ],
        )

    def test_llk_prediction_error_message_contract(self) -> None:
        parser = parser_from_export_file(LLK_FIXTURE)
        with self.assertRaises(ParseError) as ctx:
            parser.parse("Var Var End")

        self._assert_parse_error_contract(
            ctx.exception,
            found_token_index=5,
            expected_token_indices=[6, 7],
            message_fragments=[
                "predicting non-terminal 1 ('StartList')",
                "expected token indices: [6, 7]",
                "expected terminal labels: ['End', '[a-z_][a-zA-Z0-9_]*']",
            ],
        )

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

    def test_llk_non_terminal_callback_actions_are_user_facing(self) -> None:
        class Actions:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def on_start_list(self, node: dict[str, object]) -> dict[str, object]:
                self.calls.append(str(node["non_terminal"]))
                return {"kind": "StartList", "children": node["children"]}

        actions = Actions()
        parser = parser_from_export_file(LLK_FIXTURE, actions=actions)
        result = parser.parse("Var abc End")

        self.assertTrue(result.accepted)
        self.assertIn("StartList", actions.calls)

    def test_llk_generic_callback_fallback_is_used(self) -> None:
        class Actions:
            def __init__(self) -> None:
                self.generic_calls = 0

            def on_non_terminal(self, name: str, node: dict[str, object]) -> dict[str, object]:
                self.generic_calls += 1
                return node

        actions = Actions()
        parser = parser_from_export_file(LLK_FIXTURE, actions=actions)
        result = parser.parse("Var abc End")

        self.assertTrue(result.accepted)
        self.assertGreater(actions.generic_calls, 0)

    def test_callback_dispatch_parity_between_lalr_and_llk(self) -> None:
        class Actions:
            def __init__(self) -> None:
                self.named_calls = 0
                self.generic_calls = 0

            def on_start_list(self, node: dict[str, object]) -> dict[str, object]:
                self.named_calls += 1
                return node

            def on_non_terminal(self, name: str, node: dict[str, object]) -> dict[str, object]:
                self.generic_calls += 1
                return node

        lalr_actions = Actions()
        llk_actions = Actions()

        lalr_result = parser_from_export_file(FIXTURE, actions=lalr_actions).parse("Var abc End")
        llk_result = parser_from_export_file(LLK_FIXTURE, actions=llk_actions).parse("Var abc End")

        self.assertTrue(lalr_result.accepted)
        self.assertTrue(llk_result.accepted)
        self.assertGreaterEqual(lalr_actions.named_calls, 1)
        self.assertGreaterEqual(llk_actions.named_calls, 1)

    def test_on_production_parity_between_lalr_and_llk(self) -> None:
        class Actions:
            def __init__(self) -> None:
                self.calls: list[tuple[int, int]] = []

            def on_production(
                self,
                lhs_nt: int,
                prod_idx: int,
                rhs_values: list[object],
            ) -> dict[str, object]:
                self.calls.append((lhs_nt, prod_idx))
                return {
                    "lhs": lhs_nt,
                    "prod": prod_idx,
                    "arity": len(rhs_values),
                }

        lalr_actions = Actions()
        llk_actions = Actions()

        lalr_result = parser_from_export_file(FIXTURE, actions=lalr_actions).parse("Var abc End")
        llk_result = parser_from_export_file(LLK_FIXTURE, actions=llk_actions).parse("Var abc End")

        self.assertTrue(lalr_result.accepted)
        self.assertTrue(llk_result.accepted)
        self.assertGreater(len(lalr_actions.calls), 0)
        self.assertGreater(len(llk_actions.calls), 0)
        self.assertTrue(all(isinstance(lhs, int) and isinstance(prod, int) for lhs, prod in lalr_actions.calls))
        self.assertTrue(all(isinstance(lhs, int) and isinstance(prod, int) for lhs, prod in llk_actions.calls))


if __name__ == "__main__":
    unittest.main()
