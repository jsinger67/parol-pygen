from __future__ import annotations

import unittest

from parol_pygen.model import ScannerModel, ScannerState, ScannerTerminal, ScannerTransition
from parol_pygen.scanner_adapter import ScannerAdapter


class ScannerDefinitionTests(unittest.TestCase):
    def test_scnr2_definition_contains_transition_statements(self) -> None:
        model = ScannerModel(
            terminals=[
                ScannerTerminal(
                    index=10,
                    pattern='"',
                    expanded_pattern='"',
                    kind="Legacy",
                    scanner_states=[0],
                ),
                ScannerTerminal(
                    index=11,
                    pattern='[^"]+',
                    expanded_pattern='[^"]+',
                    kind="Regex",
                    scanner_states=[1],
                ),
                ScannerTerminal(
                    index=12,
                    pattern='"',
                    expanded_pattern='"',
                    kind="Legacy",
                    scanner_states=[1],
                ),
            ],
            scanner_states=[
                ScannerState(
                    scanner_state=0,
                    scanner_name="INITIAL",
                    line_comments=[],
                    block_comments=[],
                    auto_newline=True,
                    auto_ws=True,
                    allow_unmatched=False,
                    skip_tokens=[],
                    transitions=[
                        ScannerTransition(
                            terminal_index=10,
                            kind="Push",
                            target_scanner_state=1,
                            target_scanner_name=None,
                        )
                    ],
                ),
                ScannerState(
                    scanner_state=1,
                    scanner_name="STRING",
                    line_comments=[],
                    block_comments=[],
                    auto_newline=True,
                    auto_ws=False,
                    allow_unmatched=False,
                    skip_tokens=[],
                    transitions=[
                        ScannerTransition(
                            terminal_index=12,
                            kind="Pop",
                            target_scanner_state=None,
                            target_scanner_name=None,
                        ),
                        ScannerTransition(
                            terminal_index=11,
                            kind="Enter",
                            target_scanner_state=1,
                            target_scanner_name="STRING",
                        ),
                    ],
                ),
            ],
        )

        adapter = ScannerAdapter(model, prefer_scnr2=False)
        definition = adapter._build_scnr2_definition(model)

        self.assertIn("mode INITIAL", definition)
        self.assertIn("mode STRING", definition)
        self.assertIn("on 10 push STRING;", definition)
        self.assertIn("on 12 pop;", definition)
        self.assertIn("on 11 enter STRING;", definition)


if __name__ == "__main__":
    unittest.main()
