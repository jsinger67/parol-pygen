# parol-pygen (PoC)

Proof-of-concept Python parser runtime/generator consuming `parol export` JSON.

## Scope

- Supports `ParserExportModel` version `1`
- Supports `algorithm = "Lalr1"`
- Uses `scnr2` Python binding as default scanner backend
- Supports regex fallback scanner via `--no-scnr2`
- Runs LALR shift/reduce/accept parse loop

## Quick start

```bash
python -m parol_pygen.cli --version
python -m parol_pygen.cli info
python -m parol_pygen.cli validate --export ../../crates/parol/tests/data/arg_tests/export_lalr1.expected.json
python -m parol_pygen.cli run --export ../../crates/parol/tests/data/arg_tests/export_lalr1.expected.json --text "Var abc End"
```

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
python -m parol_pygen.cli run --export ../../crates/parol/tests/data/arg_tests/export_lalr1.expected.json --text "Var abc"
echo $?
```

Exit code conventions used by this PoC CLI:

- `0`: success
- `2`: user/input/data errors (invalid input text, invalid export JSON/schema, missing files)
- `1`: internal/unexpected failures

Use `--verbose-errors` to include exception type names in stderr output:

```bash
python -m parol_pygen.cli --verbose-errors run --export ../../crates/parol/tests/data/arg_tests/export_lalr1.expected.json --text "Var abc"
```

## Semantic actions (parol-style)

```python
from pathlib import Path

from parol_pygen.parser import parser_from_export_file


class Actions:
    def on_start_list(self, node: dict[str, object]) -> dict[str, object]:
        # Called when non-terminal StartList is fully reduced.
        return {"kind": "StartList", "children": node["children"]}


fixture = (
    Path(__file__).resolve().parents[2]
    / "crates"
    / "parol"
    / "tests"
    / "data"
    / "arg_tests"
    / "export_lalr1.expected.json"
)

parser = parser_from_export_file(fixture, actions=Actions())
result = parser.parse("Var abc End")
print(result.accepted)
print(result.value)
```

The parser dispatches semantic callbacks by non-terminal name (`on_<non_terminal_in_snake_case>`).
The callback return value is pushed as the reduced semantic value.

Note: depending on parse table shape (augmented start handling), the start symbol itself may
not always appear as a user-visible reduce callback in this PoC.

Advanced: a low-level `on_reduce(lhs_nt, prod_idx, rhs_values)` hook is still supported for
internal experiments, but normal user code should prefer the non-terminal callbacks above.

## Path To C#-Style Generated API

Yes, this can be done similarly to the C# generated LALR parser, and it does not need to stay
inside this PoC package.

Recommended direction (separate package/repo is fine):

1. Generator output split:
    - `parser.py`: generated LALR facade and parse entry points
    - `nodes.py`: generated typed node classes from `production_datatypes`
    - `actions.py`: generated action interface/protocol with one method per non-terminal
    - `scanner.py`: generated scanner tables/metadata facade

2. User-facing actions contract:
    - Method naming: `on_<non_terminal_in_snake_case>(node: <GeneratedType>) -> Any`
    - Dispatcher calls these methods after non-terminal reduction
    - Keep `on_non_terminal(name, node)` as generic fallback

3. Typed node generation:
    - Use Python `@dataclass` for struct-like nodes
    - Use sum-type style for alternations (base class + variant classes, or tagged dataclass)
    - Preserve production index and source span metadata for diagnostics

4. Runtime/generator boundary:
    - Keep runtime small and stable (parse engine, scanner runtime, diagnostics)
    - Keep language-specific codegen in templates driven by exported model JSON

5. Compatibility/versioning:
    - Continue using `info` contract fields (`contract_revision`, `model_contract`, `schema_id`)
    - Fail closed on unknown contract revisions in generated integration code

Practical next milestone:

- Implement `nodes.py` + `actions.py` generation first, while reusing the current parser runtime.
  This gives a C#-like user API without requiring a full runtime rewrite.

Current generator output (`parol-pygen generate`) now includes user-editable Python source files:

- `actions.py`: generated action interface/protocol (`on_<non_terminal>` methods)
- `nodes.py`: generated concrete node classes (`<NonTerminal>Node`) for typed action arguments
- `user_actions.py`: editable skeleton class to implement semantic actions
- `parser.py`: generated parser facade loading embedded `export.json`
- `export.json`: embedded parser export model
