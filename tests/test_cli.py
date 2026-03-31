from __future__ import annotations

import os
import json
import subprocess
import sys
import unittest
from json import dumps
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SRC = PROJECT_ROOT / "src"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "export_lalr1.expected.json"
LLK_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "export_llk.expected.json"


def _read_project_version() -> str:
    pyproject = PROJECT_ROOT / "pyproject.toml"
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("version = "):
            return line.split('"')[1]
    raise AssertionError("Version not found in pyproject.toml")


PROJECT_VERSION = _read_project_version()


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(PACKAGE_SRC) if not existing else f"{PACKAGE_SRC}{os.pathsep}{existing}"
    return subprocess.run(
        [sys.executable, "-m", "parol_pygen.cli", *args],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def _run_python_with_path(code: str, *pythonpath_entries: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    entries = [entry for entry in pythonpath_entries if entry]
    existing = env.get("PYTHONPATH", "")
    if existing:
        entries.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(entries)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


class CliTests(unittest.TestCase):
    def test_info_command_outputs_json_metadata(self) -> None:
        cp = _run_cli("info")
        self.assertEqual(cp.returncode, 0, cp.stderr)
        payload = json.loads(cp.stdout)

        self.assertEqual(payload["name"], "parol-pygen")
        self.assertEqual(payload["version"], PROJECT_VERSION)
        self.assertEqual(payload["contract_revision"], 1)
        self.assertEqual(payload["supported_contract_revisions"], [1])
        self.assertEqual(payload["compatibility_policy"]["unknown_contract_revision"], "reject")
        self.assertEqual(payload["compatibility_policy"]["known_contract_revision"], "accept")
        self.assertEqual(payload["model_contract"], "parser-export-model.v1")
        self.assertEqual(payload["schema_id"], "parser-export-model.v1.schema.json")
        self.assertEqual(payload["supported_export_version"], 1)
        self.assertIn("Lalr1", payload["supported_algorithms"])
        self.assertIn("Llk", payload["supported_algorithms"])
        self.assertIn("validate", payload["commands"])
        self.assertIn("run", payload["commands"])
        self.assertIn("generate", payload["commands"])
        self.assertIn("init", payload["commands"])
        self.assertIn("info", payload["commands"])
        self.assertIn("capabilities", payload)
        self.assertIn("cli.validate", payload["capabilities"])
        self.assertIn("cli.run", payload["capabilities"])
        self.assertIn("cli.generate", payload["capabilities"])
        self.assertIn("cli.init", payload["capabilities"])
        self.assertIn("cli.info", payload["capabilities"])
        self.assertIn("errors.concise", payload["capabilities"])
        self.assertIn("errors.verbose", payload["capabilities"])
        self.assertIn("scanner.scnr2.optional", payload["capabilities"])
        self.assertIn("actions.non_terminal_callbacks", payload["capabilities"])
        self.assertIn("scaffold.project", payload["capabilities"])
        self.assertIn("model.algorithm.llk", payload["capabilities"])
        self.assertEqual(payload["error_exit_codes"]["success"], 0)
        self.assertEqual(payload["error_exit_codes"]["user_error"], 2)
        self.assertEqual(payload["error_exit_codes"]["internal_error"], 1)

    def test_version_option(self) -> None:
        cp = _run_cli("--version")
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertIn(f"parol-pygen {PROJECT_VERSION}", cp.stdout)
        self.assertEqual(cp.stderr, "")

    def test_validate_command(self) -> None:
        cp = _run_cli("validate", "--export", str(FIXTURE))
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertIn("Validation successful", cp.stdout)

    def test_validate_command_accepts_llk_export(self) -> None:
        cp = _run_cli("validate", "--export", str(LLK_FIXTURE))
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertIn("Validation successful", cp.stdout)

    def test_run_command_with_and_without_scnr2(self) -> None:
        cp_default = _run_cli("run", "--export", str(FIXTURE), "--text", "Var abc End")
        self.assertEqual(cp_default.returncode, 0, cp_default.stderr)
        self.assertIn("Accepted=True", cp_default.stdout)

        cp_fallback = _run_cli(
            "run",
            "--export",
            str(FIXTURE),
            "--text",
            "Var abc End",
            "--no-scnr2",
        )
        self.assertEqual(cp_fallback.returncode, 0, cp_fallback.stderr)
        self.assertIn("Accepted=True", cp_fallback.stdout)

    def test_run_command_rejects_invalid_input(self) -> None:
        cp = _run_cli("run", "--export", str(FIXTURE), "--text", "Var abc")
        self.assertEqual(cp.returncode, 2)
        self.assertIn("Error:", cp.stderr)
        self.assertIn("Parse error at offset", cp.stderr)
        self.assertIn("expected token indices", cp.stderr)
        self.assertNotIn("Traceback", cp.stderr)

    def test_run_command_supports_llk(self) -> None:
        cp = _run_cli("run", "--export", str(LLK_FIXTURE), "--text", "Var abc End")
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertIn("Accepted=True", cp.stdout)

    def test_run_command_rejects_invalid_llk_input(self) -> None:
        cp = _run_cli("run", "--export", str(LLK_FIXTURE), "--text", "Var abc")
        self.assertEqual(cp.returncode, 2)
        self.assertIn("Error:", cp.stderr)
        self.assertIn("expected token indices", cp.stderr)

    def test_validate_command_rejects_invalid_export(self) -> None:
        with TemporaryDirectory() as tmp:
            invalid = Path(tmp) / "invalid_export.json"
            invalid.write_text(dumps({"version": 1}), encoding="utf-8")

            cp = _run_cli("validate", "--export", str(invalid))
            self.assertEqual(cp.returncode, 2)
            self.assertIn("Error:", cp.stderr)
            self.assertIn("Schema validation failed", cp.stderr)
            self.assertNotIn("Traceback", cp.stderr)

    def test_verbose_errors_include_exception_type_for_user_error(self) -> None:
        cp = _run_cli("--verbose-errors", "run", "--export", str(FIXTURE), "--text", "Var abc")
        self.assertEqual(cp.returncode, 2)
        self.assertIn("Error: ParseError:", cp.stderr)
        self.assertNotIn("Traceback", cp.stderr)

    def test_internal_error_returns_exit_code_1(self) -> None:
        cp = _run_python_with_path(
            "import sys; import parol_pygen.cli as c; "
            "c._cmd_validate = lambda args: (_ for _ in ()).throw(RuntimeError('boom')); "
            "sys.exit(c.main(['validate', '--export', 'dummy.json']))",
            str(PACKAGE_SRC),
        )
        self.assertEqual(cp.returncode, 1)
        self.assertIn("Internal error:", cp.stderr)
        self.assertNotIn("Traceback", cp.stderr)

    def test_verbose_errors_include_exception_type_for_internal_error(self) -> None:
        cp = _run_python_with_path(
            "import sys; import parol_pygen.cli as c; "
            "c._cmd_validate = lambda args: (_ for _ in ()).throw(RuntimeError('boom')); "
            "sys.exit(c.main(['--verbose-errors', 'validate', '--export', 'dummy.json']))",
            str(PACKAGE_SRC),
        )
        self.assertEqual(cp.returncode, 1)
        self.assertIn("Internal error: RuntimeError: boom", cp.stderr)
        self.assertNotIn("Traceback", cp.stderr)

    def test_generate_command(self) -> None:
        with TemporaryDirectory() as tmp:
            cp = _run_cli(
                "generate",
                "--export",
                str(FIXTURE),
                "--out",
                tmp,
                "--package",
                "demo_parser",
            )
            self.assertEqual(cp.returncode, 0, cp.stderr)
            generated = Path(tmp) / "demo_parser"
            self.assertTrue((generated / "__init__.py").exists())
            self.assertTrue((generated / "actions.py").exists())
            self.assertTrue((generated / "nodes.py").exists())
            self.assertTrue((generated / "parser.py").exists())
            self.assertTrue((generated / "user_actions.py").exists())
            self.assertTrue((generated / "export.json").exists())

    def test_generate_package_import_and_parse_in_subprocess(self) -> None:
        with TemporaryDirectory() as tmp:
            cp_generate = _run_cli(
                "generate",
                "--export",
                str(FIXTURE),
                "--out",
                tmp,
                "--package",
                "demo_parser",
            )
            self.assertEqual(cp_generate.returncode, 0, cp_generate.stderr)

            cp_run = _run_python_with_path(
                "from demo_parser import Parser; r = Parser().parse('Var abc End'); print(r.accepted)",
                str(PACKAGE_SRC),
                tmp,
            )
            self.assertEqual(cp_run.returncode, 0, cp_run.stderr)
            self.assertEqual(cp_run.stdout.strip(), "True")

    def test_generate_llk_package_import_and_parse_in_subprocess(self) -> None:
        with TemporaryDirectory() as tmp:
            cp_generate = _run_cli(
                "generate",
                "--export",
                str(LLK_FIXTURE),
                "--out",
                tmp,
                "--package",
                "demo_llk_parser",
            )
            self.assertEqual(cp_generate.returncode, 0, cp_generate.stderr)

            cp_run = _run_python_with_path(
                "from demo_llk_parser import Parser; r = Parser().parse('Var abc End'); print(r.accepted)",
                str(PACKAGE_SRC),
                tmp,
            )
            self.assertEqual(cp_run.returncode, 0, cp_run.stderr)
            self.assertEqual(cp_run.stdout.strip(), "True")

    def test_generate_llk_package_typed_callbacks_in_subprocess(self) -> None:
        with TemporaryDirectory() as tmp:
            cp_generate = _run_cli(
                "generate",
                "--export",
                str(LLK_FIXTURE),
                "--out",
                tmp,
                "--package",
                "demo_llk_parser",
            )
            self.assertEqual(cp_generate.returncode, 0, cp_generate.stderr)

            code = "\n".join(
                [
                    "from demo_llk_parser import Parser, UserActions",
                    "from demo_llk_parser.nodes import NonTerminalNode, StartListNode",
                    "",
                    "class A(UserActions):",
                    "    def __init__(self):",
                    "        super().__init__()",
                    "        self.typed = 0",
                    "        self.generic = 0",
                    "",
                    "    def on_start_list(self, node: StartListNode):",
                    "        self.typed += 1",
                    "        return node",
                    "",
                    "    def on_non_terminal(self, name: str, node: NonTerminalNode):",
                    "        self.generic += 1",
                    "        return node",
                    "",
                    "a = A()",
                    "r = Parser(actions=a).parse('Var abc End')",
                    "print(r.accepted, a.typed > 0)",
                ]
            )

            cp_run = _run_python_with_path(
                code,
                str(PACKAGE_SRC),
                tmp,
            )
            self.assertEqual(cp_run.returncode, 0, cp_run.stderr)
            self.assertEqual(cp_run.stdout.strip(), "True True")

    def test_generate_llk_package_generic_fallback_in_subprocess(self) -> None:
        with TemporaryDirectory() as tmp:
            cp_generate = _run_cli(
                "generate",
                "--export",
                str(LLK_FIXTURE),
                "--out",
                tmp,
                "--package",
                "demo_llk_parser",
            )
            self.assertEqual(cp_generate.returncode, 0, cp_generate.stderr)

            code = "\n".join(
                [
                    "from demo_llk_parser import Parser, UserActions",
                    "from demo_llk_parser.nodes import NonTerminalNode",
                    "",
                    "class A(UserActions):",
                    "    def __init__(self):",
                    "        super().__init__()",
                    "        self.generic = 0",
                    "",
                    "    def on_non_terminal(self, name: str, node: NonTerminalNode):",
                    "        self.generic += 1",
                    "        return node",
                    "",
                    "a = A()",
                    "r = Parser(actions=a).parse('Var abc End')",
                    "print(r.accepted, a.generic > 0)",
                ]
            )

            cp_run = _run_python_with_path(
                code,
                str(PACKAGE_SRC),
                tmp,
            )
            self.assertEqual(cp_run.returncode, 0, cp_run.stderr)
            self.assertEqual(cp_run.stdout.strip(), "True True")

    def test_generate_package_on_production_in_subprocess(self) -> None:
        with TemporaryDirectory() as tmp:
            cp_generate = _run_cli(
                "generate",
                "--export",
                str(FIXTURE),
                "--out",
                tmp,
                "--package",
                "demo_parser",
            )
            self.assertEqual(cp_generate.returncode, 0, cp_generate.stderr)

            code = "\n".join(
                [
                    "from demo_parser import Parser, UserActions",
                    "",
                    "class A(UserActions):",
                    "    def __init__(self):",
                    "        super().__init__()",
                    "        self.production_calls = 0",
                    "",
                    "    def on_production(self, lhs_nt, prod_idx, rhs_values):",
                    "        self.production_calls += 1",
                    "        return {'lhs_nt': lhs_nt, 'prod_idx': prod_idx, 'children': rhs_values}",
                    "",
                    "a = A()",
                    "r = Parser(actions=a).parse('Var abc End')",
                    "print(r.accepted, a.production_calls > 0)",
                ]
            )

            cp_run = _run_python_with_path(
                code,
                str(PACKAGE_SRC),
                tmp,
            )
            self.assertEqual(cp_run.returncode, 0, cp_run.stderr)
            self.assertEqual(cp_run.stdout.strip(), "True True")

    def test_generate_llk_package_on_production_in_subprocess(self) -> None:
        with TemporaryDirectory() as tmp:
            cp_generate = _run_cli(
                "generate",
                "--export",
                str(LLK_FIXTURE),
                "--out",
                tmp,
                "--package",
                "demo_llk_parser",
            )
            self.assertEqual(cp_generate.returncode, 0, cp_generate.stderr)

            code = "\n".join(
                [
                    "from demo_llk_parser import Parser, UserActions",
                    "",
                    "class A(UserActions):",
                    "    def __init__(self):",
                    "        super().__init__()",
                    "        self.production_calls = 0",
                    "",
                    "    def on_production(self, lhs_nt, prod_idx, rhs_values):",
                    "        self.production_calls += 1",
                    "        return {'lhs_nt': lhs_nt, 'prod_idx': prod_idx, 'children': rhs_values}",
                    "",
                    "a = A()",
                    "r = Parser(actions=a).parse('Var abc End')",
                    "print(r.accepted, a.production_calls > 0)",
                ]
            )

            cp_run = _run_python_with_path(
                code,
                str(PACKAGE_SRC),
                tmp,
            )
            self.assertEqual(cp_run.returncode, 0, cp_run.stderr)
            self.assertEqual(cp_run.stdout.strip(), "True True")

    def test_generate_package_on_reduce_backward_compatibility_in_subprocess(self) -> None:
        with TemporaryDirectory() as tmp:
            cp_generate = _run_cli(
                "generate",
                "--export",
                str(FIXTURE),
                "--out",
                tmp,
                "--package",
                "demo_parser",
            )
            self.assertEqual(cp_generate.returncode, 0, cp_generate.stderr)

            code = "\n".join(
                [
                    "from demo_parser import Parser, UserActions",
                    "",
                    "class A(UserActions):",
                    "    def __init__(self):",
                    "        super().__init__()",
                    "        self.reduce_calls = 0",
                    "",
                    "    def on_reduce(self, lhs_nt, prod_idx, rhs_values):",
                    "        self.reduce_calls += 1",
                    "        return {'lhs_nt': lhs_nt, 'prod_idx': prod_idx, 'children': rhs_values}",
                    "",
                    "a = A()",
                    "r = Parser(actions=a).parse('Var abc End')",
                    "print(r.accepted, a.reduce_calls > 0)",
                ]
            )

            cp_run = _run_python_with_path(
                code,
                str(PACKAGE_SRC),
                tmp,
            )
            self.assertEqual(cp_run.returncode, 0, cp_run.stderr)
            self.assertEqual(cp_run.stdout.strip(), "True True")

    def test_run_command_reports_llk_prediction_expectations(self) -> None:
        cp = _run_cli("run", "--export", str(LLK_FIXTURE), "--text", "Var Var End")
        self.assertEqual(cp.returncode, 2)
        self.assertIn("while predicting non-terminal", cp.stderr)
        self.assertIn("expected token indices: [6, 7]", cp.stderr)

    def test_init_command_creates_scaffold_project(self) -> None:
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "demo-proof"
            cp = _run_cli(
                "init",
                "--out",
                str(out_dir),
                "--project",
                "Demo Proof",
                "--package",
                "demo_generated",
                "--export",
                "demo_export.json",
            )
            self.assertEqual(cp.returncode, 0, cp.stderr)
            self.assertTrue((out_dir / "README.md").exists())
            self.assertTrue((out_dir / "pyproject.toml").exists())
            self.assertTrue((out_dir / "proof_runner.py").exists())
            self.assertTrue((out_dir / "custom_actions.py").exists())
            self.assertTrue((out_dir / "sample.txt").exists())
            self.assertTrue((out_dir / "scripts" / "bootstrap.ps1").exists())
            self.assertTrue((out_dir / "scripts" / "generate-parser.ps1").exists())
            self.assertTrue((out_dir / "scripts" / "run-proof.ps1").exists())

            readme = (out_dir / "README.md").read_text(encoding="utf-8")
            self.assertIn("demo_generated", readme)
            self.assertIn("demo_export.json", readme)

    def test_init_command_rejects_non_empty_target_without_force(self) -> None:
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "demo-proof"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "sentinel.txt").write_text("keep", encoding="utf-8")

            cp = _run_cli(
                "init",
                "--out",
                str(out_dir),
                "--project",
                "Demo Proof",
            )
            self.assertEqual(cp.returncode, 2)
            self.assertIn("Target directory is not empty", cp.stderr)

    def test_init_command_allows_non_empty_target_with_force(self) -> None:
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "demo-proof"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "sentinel.txt").write_text("keep", encoding="utf-8")

            cp = _run_cli(
                "init",
                "--out",
                str(out_dir),
                "--project",
                "Demo Proof",
                "--force",
            )
            self.assertEqual(cp.returncode, 0, cp.stderr)
            self.assertTrue((out_dir / "README.md").exists())
            self.assertTrue((out_dir / "sentinel.txt").exists())


if __name__ == "__main__":
    unittest.main()
