from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .generator import generate_package
from .loader import load_export_model, load_json_file
from .model import ParseError
from .parser import SCHEMA_PATH, parser_from_export_file
from .scaffold import scaffold_project
from .validator import ValidationError, validate_against_schema, validate_export_model


def _read_project_version() -> str:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    version_pattern = re.compile(r'^\s*version\s*=\s*"([^"]+)"\s*$')
    try:
        for line in pyproject.read_text(encoding="utf-8").splitlines():
            match = version_pattern.match(line)
            if match:
                return match.group(1)
    except OSError:
        pass
    return "0.0.0+unknown"


CLI_VERSION = _read_project_version()


def _read_project_description() -> str:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    description_pattern = re.compile(r'^\s*description\s*=\s*"([^"]+)"\s*$')
    try:
        for line in pyproject.read_text(encoding="utf-8").splitlines():
            match = description_pattern.match(line)
            if match:
                return match.group(1)
    except OSError:
        pass
    return ""


CLI_DESCRIPTION = _read_project_description()


def _cmd_validate(args: argparse.Namespace) -> int:
    raw = load_json_file(args.export)
    validate_against_schema(raw, SCHEMA_PATH)
    model = load_export_model(args.export)
    validate_export_model(model)
    print("Validation successful")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    parser = parser_from_export_file(args.export, prefer_scnr2=not args.no_scnr2)
    result = parser.parse(args.text)
    print(f"Accepted={result.accepted}; reductions={len(result.reductions)}")
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    out = generate_package(args.export, args.out, args.package)
    print(f"Generated parser package at {out}")
    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    out = scaffold_project(
        out_dir=args.out,
        project_name=args.project,
        package_name=args.package,
        export_file=args.export,
        force=args.force,
    )
    print(f"Scaffolded project at {out}")
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    payload = {
        "name": "parol-pygen",
        "version": CLI_VERSION,
        "description": CLI_DESCRIPTION,
        "contract_revision": 1,
        "supported_contract_revisions": [1],
        "compatibility_policy": {
            "unknown_contract_revision": "reject",
            "known_contract_revision": "accept",
        },
        "model_contract": "parser-export-model.v1",
        "schema_id": "parser-export-model.v1.schema.json",
        "supported_export_version": 1,
        "supported_algorithms": ["Lalr1", "Llk"],
        "commands": ["validate", "run", "generate", "init", "info"],
        "capabilities": [
            "cli.validate",
            "cli.run",
            "cli.generate",
            "cli.init",
            "cli.info",
            "errors.concise",
            "errors.verbose",
            "scanner.scnr2.optional",
            "actions.non_terminal_callbacks",
            "scaffold.project",
            "model.algorithm.llk",
        ],
        "error_exit_codes": {"success": 0, "user_error": 2, "internal_error": 1},
    }
    print(json.dumps(payload, indent=2))
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="parol-pygen")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {CLI_VERSION}",
    )
    parser.add_argument(
        "--verbose-errors",
        action="store_true",
        help="Include exception type names in error output",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_validate = sub.add_parser("validate", help="Validate export against schema and semantic checks")
    p_validate.add_argument("--export", required=True, type=Path)
    p_validate.set_defaults(func=_cmd_validate)

    p_run = sub.add_parser("run", help="Run LALR parser for given text")
    p_run.add_argument("--export", required=True, type=Path)
    p_run.add_argument("--text", required=True)
    p_run.add_argument(
        "--no-scnr2",
        action="store_true",
        help="Use fallback regex scanner adapter instead of scnr2 binding",
    )
    p_run.set_defaults(func=_cmd_run)

    p_generate = sub.add_parser("generate", help="Generate a standalone Python parser package")
    p_generate.add_argument("--export", required=True, type=Path)
    p_generate.add_argument("--out", required=True, type=Path)
    p_generate.add_argument("--package", required=True)
    p_generate.set_defaults(func=_cmd_generate)

    p_init = sub.add_parser("init", help="Scaffold a standalone parser project")
    p_init.add_argument("--out", required=True, type=Path)
    p_init.add_argument("--project", required=True)
    p_init.add_argument("--package", default="generated_parser")
    p_init.add_argument("--export", default="export.json")
    p_init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files in target directory",
    )
    p_init.set_defaults(func=_cmd_init)

    p_info = sub.add_parser("info", help="Print tool metadata and supported scope as JSON")
    p_info.set_defaults(func=_cmd_info)

    return parser


def _is_user_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            ValidationError,
            ParseError,
            FileNotFoundError,
            FileExistsError,
            ValueError,
            json.JSONDecodeError,
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        details = f"{type(exc).__name__}: {exc}" if args.verbose_errors else str(exc)
        if _is_user_error(exc):
            print(f"Error: {details}", file=sys.stderr)
            return 2
        print(f"Internal error: {details}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
