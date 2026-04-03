param(
    [string]$ProjectPath = "D:/Source/parol-pygen",
    [switch]$Execute
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [string]$Label,
        [scriptblock]$Action,
        [string]$Preview
    )

    Write-Host ""
    Write-Host "==> $Label"
    if (-not $Execute) {
        Write-Host "[dry-run] $Preview"
        return
    }
    & $Action
}

function Ensure-Path {
    param([string]$PathToCheck, [string]$Description)
    if (-not (Test-Path $PathToCheck)) {
        throw "$Description not found: $PathToCheck"
    }
}

function Ensure-File {
    param([string]$FilePath, [string]$Description)
    if (-not (Test-Path $FilePath)) {
        throw "$Description missing: $FilePath"
    }
}

function Run-OrThrow {
    param([string]$Command, [string]$FailureMessage)
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

Ensure-Path $ProjectPath "Project path"
Ensure-File (Join-Path $ProjectPath "pyproject.toml") "Project metadata"

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    throw "uv is required but was not found in PATH."
}

$tmpDir = Join-Path $ProjectPath ".tmp-smoke"

Invoke-Step -Label "Install project dependencies" -Preview "Set-Location $ProjectPath ; uv sync --extra dev" -Action {
    Push-Location $ProjectPath
    try {
        Run-OrThrow "uv sync --extra dev" "Dependency sync failed."
    }
    finally {
        Pop-Location
    }
}

Invoke-Step -Label "Run unit tests" -Preview "Set-Location $ProjectPath ; uv run python -m unittest discover -s tests -p 'test_*.py'" -Action {
    Push-Location $ProjectPath
    try {
        Run-OrThrow "uv run python -m unittest discover -s tests -p 'test_*.py'" "Unit tests failed."
    }
    finally {
        Pop-Location
    }
}

Invoke-Step -Label "Run CLI metadata smoke check" -Preview "Set-Location $ProjectPath ; uv run python -m parol_pygen.cli info" -Action {
    Push-Location $ProjectPath
    try {
        Run-OrThrow "uv run python -m parol_pygen.cli info" "CLI info command failed."
    }
    finally {
        Pop-Location
    }
}

Invoke-Step -Label "Run scaffold smoke check" -Preview "Set-Location $ProjectPath ; uv run python -m parol_pygen.cli init --out ./.tmp-smoke --project smoke-demo --force" -Action {
    Push-Location $ProjectPath
    try {
        if (Test-Path $tmpDir) {
            Remove-Item -Recurse -Force $tmpDir
        }

        Run-OrThrow "uv run python -m parol_pygen.cli init --out ./.tmp-smoke --project smoke-demo --force" "Scaffold init command failed."

        $expected = @(
            ".tmp-smoke/README.md",
            ".tmp-smoke/pyproject.toml",
            ".tmp-smoke/scripts/bootstrap.ps1",
            ".tmp-smoke/scripts/generate-parser.ps1",
            ".tmp-smoke/scripts/run-proof.ps1",
            ".tmp-smoke/custom_actions.py",
            ".tmp-smoke/proof_runner.py"
        )

        foreach ($entry in $expected) {
            Ensure-File (Join-Path $ProjectPath $entry) "Scaffold output file"
        }
    }
    finally {
        if (Test-Path $tmpDir) {
            Remove-Item -Recurse -Force $tmpDir
        }
        Pop-Location
    }
}

if (-not $Execute) {
    Write-Host ""
    Write-Host "Dry-run complete. Re-run with -Execute to perform post-split verification."
    Write-Host "Example:"
    Write-Host "  ./scripts/verify-split.ps1 -Execute"
}