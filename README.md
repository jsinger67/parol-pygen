# parol-pygen

![ParolPyLogo](https://raw.githubusercontent.com/jsinger67/parol-pygen/main/logo/ParolPy.png)

Python parser runtime/generator consuming `parol export` JSON.

## Scope

- Supports `ParserExportModel` version `1`
- Supports export model validation for `algorithm = "Lalr1" | "Llk"`
- Runtime parsing supports `Lalr1` and `Llk`
- Uses `scnr2` Python binding as default scanner backend
- Supports regex fallback scanner via `--no-scnr2`
- Runs LALR shift/reduce and LLK predictive parse loops

## Quick start

Export parser metadata JSON from a grammar file (example):

```bash
parol export --grammar ./my-grammar.par --output-file ./export.json
```

Then run `parol-pygen` commands against `./export.json`:

```bash
python -m parol_pygen.cli --version
python -m parol_pygen.cli info
python -m parol_pygen.cli validate --export ./export.json
python -m parol_pygen.cli generate --export ./export.json --out . --package arg_generated
python -c "from arg_generated import Parser, UserActions; print(Parser(actions=UserActions()).parse('Var abc End').accepted)"
```

For a ready-to-run proof/project scaffold (scripts + runner + action skeleton):

```bash
python -m parol_pygen.cli init --out ./demo-proof --project "Demo Proof" --package demo_generated --export demo_export.json
```

This creates a standalone project skeleton in `./demo-proof` with:

- `scripts/bootstrap.ps1`
- `scripts/generate-parser.ps1`
- `scripts/run-proof.ps1`
- `proof_runner.py`
- `custom_actions.py`
- `sample.txt`

Note: these are generated files inside the scaffold output directory (for example `./demo-proof/scripts/...`),
not maintainer scripts in this repository root.

The recommended flow is generation-first:

1. Validate export JSON (`validate`)
2. Generate a Python package (`generate`)
3. Import the generated `Parser`/`UserActions` from that package and parse input

Alternative: use `init` first when you want a full project scaffold instead of only a generated package.

The direct runtime command still exists for low-level diagnostics:

```bash
python -m parol_pygen.cli run --export ./export.json --text "Var abc End"
```

Replace `./export.json` with any export file produced by your `parol export` workflow.

`run` supports both `Lalr1` and `Llk` exports.

The `info` command prints JSON metadata (version, contract revision, model contract identifier,
schema id, capabilities, supported algorithm/export model, commands,
and error exit code conventions),
which is useful for tooling integration and diagnostics.

Compatibility rule for tooling consumers:

- If `contract_revision` is unknown and not listed in `supported_contract_revisions`,
  treat the payload as potentially incompatible and reject by default.

Example integration check (fail closed by default):

```python
import json
import subprocess
import sys


cp = subprocess.run(
    [sys.executable, "-m", "parol_pygen.cli", "info"],
    text=True,
    capture_output=True,
    check=True,
)

info = json.loads(cp.stdout)
revision = int(info["contract_revision"])
supported = {int(x) for x in info["supported_contract_revisions"]}

if revision not in supported:
    raise RuntimeError(
        f"Unsupported parol-pygen info contract revision {revision}; "
        f"supported revisions: {sorted(supported)}"
    )

print("Compatible info contract detected")
```

PowerShell variant (Windows):

```powershell
$raw = python -m parol_pygen.cli info
$info = $raw | ConvertFrom-Json

$revision = [int]$info.contract_revision
$supported = @($info.supported_contract_revisions | ForEach-Object { [int]$_ })

if ($supported -notcontains $revision) {
    throw "Unsupported parol-pygen info contract revision $revision; supported revisions: $($supported -join ', ')"
}

Write-Output "Compatible info contract detected"
```

cmd.exe variant (Windows):

```bat
for /f "delims=" %I in ('python -m parol_pygen.cli info') do @set PAROL_INFO=%I
python -c "import json,os,sys; i=json.loads(os.environ['PAROL_INFO']); r=int(i['contract_revision']); s={int(x) for x in i['supported_contract_revisions']}; sys.exit(0 if r in s else 1)"
if errorlevel 1 (
    echo Unsupported parol-pygen info contract revision
    exit /b 1
) else (
    echo Compatible info contract detected
)
```

Invalid input returns a non-zero exit code and prints parse diagnostics to stderr:

```bash
python -m parol_pygen.cli run --export ./export.json --text "Var abc"
echo $?
```

Exit code conventions used by the CLI:

- `0`: success
- `2`: user/input/data errors (invalid input text, invalid export JSON/schema, missing files)
- `1`: internal/unexpected failures

Use `--verbose-errors` to include exception type names in stderr output:

```bash
python -m parol_pygen.cli --verbose-errors run --export ./export.json --text "Var abc"
```

## Development with uv

For local development and CI parity, prefer `uv` as package/environment manager.

Initial setup:

```bash
uv venv
uv sync
```

Run CLI commands in the managed environment:

```bash
uv run python -m parol_pygen.cli --version
uv run python -m parol_pygen.cli info
```

Run tests:

```bash
uv run python -m unittest discover -s tests -p "test_*.py"
```

Build artifacts:

```bash
uv sync --extra dev
uv run python -m build
uv run python -m twine check dist/*
```

Release preflight:

```bash
uv run pwsh ./scripts/check-changelog-entry.ps1
# optional explicit target version
uv run pwsh ./scripts/check-changelog-entry.ps1 -Version 0.1.0

# one-command local release dry-run (gate + build + artifact check + scaffold smoke)
uv run pwsh ./scripts/release-dry-run.ps1 -Version 0.1.0 -Execute
```

This verifies that the current `pyproject.toml` version has a matching entry in `CHANGELOG.md`
before publish workflows are started.

## Release checklist (maintainers)

Suggested command order for cutting a release `X.Y.Z`:

```powershell
./scripts/check-changelog-entry.ps1 -Version X.Y.Z
./scripts/release-dry-run.ps1 -Version X.Y.Z -Execute
git add pyproject.toml CHANGELOG.md
git commit -m "chore(release): cut vX.Y.Z"
git tag -a vX.Y.Z -m "parol-pygen vX.Y.Z"
git push origin main
git push origin vX.Y.Z
```

Recommended publish flow:

1. Publish to TestPyPI first.
2. Run smoke/install checks from a clean environment.
3. Publish to PyPI only after TestPyPI checks are green.

### Trusted Publishing setup (PyPI/TestPyPI)

This repository uses GitHub OIDC Trusted Publishing in
`.github/workflows/publish.yml` (`id-token: write` + `pypa/gh-action-pypi-publish`).
No API token secrets are required for publish jobs.

Configure publishers in both package indexes:

1. In TestPyPI project settings, add a Trusted Publisher:
    - owner/repo: `jsinger67/parol-pygen`
    - workflow file: `.github/workflows/publish.yml`
    - environment: `testpypi`
2. In PyPI project settings, add a Trusted Publisher:
    - owner/repo: `jsinger67/parol-pygen`
    - workflow file: `.github/workflows/publish.yml`
    - environment: `pypi`

Recommended first verification:

1. Run workflow dispatch with `repository=testpypi` and `version=X.Y.Z`.
2. Confirm successful TestPyPI publish.
3. Run with `repository=pypi` from the commit tagged `vX.Y.Z`.

## Semantic actions (parol-style)

```python
from arg_generated import Parser, UserActions
from arg_generated.nodes import NonTerminalNode, StartListNode


class Actions(UserActions):
    def on_start_list(self, node: StartListNode):
        # Typed callback for reduced non-terminal StartList.
        return {"kind": "StartList", "children": node.children}

    def on_non_terminal(self, name: str, node: NonTerminalNode):
        # Optional generic hook for all non-terminals.
        return node


parser = Parser(actions=Actions())
result = parser.parse("Var abc End")
print(result.accepted)
print(result.value)
```

This mirrors the standalone Pascal proof setup:

- generate package once (for example `pascal_generated`)
- subclass generated `UserActions`
- override typed `on_<non_terminal>` methods
- parse through generated `Parser`

Callback dispatch remains name-based (`on_<non_terminal_in_snake_case>`), and callback
return values are pushed as reduced semantic values.

Note: depending on parse table shape (augmented start handling), the start symbol itself may
not always appear as a user-visible callback.

Advanced: a low-level `on_production(lhs_nt, prod_idx, rhs_values)` hook is available for
algorithm-neutral internal experiments. `on_reduce(...)` remains supported as a
backward-compatible alias; see `MIGRATION.md` for upgrade guidance.

## Generated API Architecture

`parol-pygen generate` now provides a C#-style generated API surface for Python consumers.
The generated package is intended to be edited/extended by user code, while parser internals
remain in the reusable runtime.

Generated files:

- `parser.py`
    - Generated parser facade
    - Adapts runtime reduction payloads to generated typed node classes
    - Dispatches typed semantic action callbacks
- `nodes.py`
    - Generated concrete node classes (`<NonTerminal>Node`) using `@dataclass`
    - Shared base types for generic and non-terminal nodes
- `actions.py`
    - Generated action protocol with typed method signatures per non-terminal
    - Base class with generic `on_non_terminal(name, node)` fallback hook
- `user_actions.py`
    - Editable starter implementation intended for user semantic logic
- `export.json`
    - Embedded parser export model used by the generated parser facade

Semantic action contract:

- Preferred method shape: `on_<non_terminal_in_snake_case>(node: <GeneratedNodeType>) -> Any`
- Generic fallback: `on_non_terminal(name: str, node: NonTerminalNode) -> Any`

Compatibility contract for tooling remains machine-readable through `parol-pygen info`
(`contract_revision`, `supported_contract_revisions`, `model_contract`, `schema_id`,
`capabilities`). Consumers should continue to fail closed on unknown revisions.
