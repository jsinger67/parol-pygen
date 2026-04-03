param(
    [string]$ProjectPath,
    [string]$Version,
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

function Run-OrThrow {
    param([string]$Command, [string]$FailureMessage)
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

if (-not $ProjectPath) {
    $ProjectPath = (Resolve-Path (Join-Path $PSScriptRoot ".." )).Path
}

$pyprojectPath = Join-Path $ProjectPath "pyproject.toml"
if (-not (Test-Path $pyprojectPath)) {
    throw "pyproject.toml not found at: $pyprojectPath"
}

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    throw "uv is required but was not found in PATH."
}

$tmpSmokeDir = Join-Path $ProjectPath ".tmp-release-smoke"

Invoke-Step -Label "Release gate (version and changelog)" -Preview "Set-Location $ProjectPath ; ./scripts/check-changelog-entry.ps1 -Version $Version" -Action {
    Push-Location $ProjectPath
    try {
        if ([string]::IsNullOrWhiteSpace($Version)) {
            Run-OrThrow "./scripts/check-changelog-entry.ps1" "Changelog release gate failed."
        }
        else {
            Run-OrThrow "./scripts/check-changelog-entry.ps1 -Version $Version" "Changelog release gate failed."
        }
    }
    finally {
        Pop-Location
    }
}

Invoke-Step -Label "Install dependencies for build" -Preview "Set-Location $ProjectPath ; uv sync --extra dev" -Action {
    Push-Location $ProjectPath
    try {
        Run-OrThrow "uv sync --extra dev" "Dependency sync failed."
    }
    finally {
        Pop-Location
    }
}

Invoke-Step -Label "Build distribution artifacts" -Preview "Set-Location $ProjectPath ; uv run python -m build" -Action {
    Push-Location $ProjectPath
    try {
        Run-OrThrow "uv run python -m build" "Build failed."
    }
    finally {
        Pop-Location
    }
}

Invoke-Step -Label "Validate artifacts" -Preview "Set-Location $ProjectPath ; uv run python -m twine check dist/*" -Action {
    Push-Location $ProjectPath
    try {
        Run-OrThrow "uv run python -m twine check dist/*" "Twine artifact check failed."
    }
    finally {
        Pop-Location
    }
}

Invoke-Step -Label "Scaffold smoke validation" -Preview "Set-Location $ProjectPath ; uv run python -m parol_pygen.cli init --out ./.tmp-release-smoke --project release-smoke --package release_smoke_generated --force" -Action {
    Push-Location $ProjectPath
    try {
        if (Test-Path $tmpSmokeDir) {
            Remove-Item -Recurse -Force $tmpSmokeDir
        }

        Run-OrThrow "uv run python -m parol_pygen.cli init --out ./.tmp-release-smoke --project release-smoke --package release_smoke_generated --force" "Scaffold smoke command failed."

        $expected = @(
            ".tmp-release-smoke/README.md",
            ".tmp-release-smoke/pyproject.toml",
            ".tmp-release-smoke/scripts/bootstrap.ps1",
            ".tmp-release-smoke/scripts/generate-parser.ps1",
            ".tmp-release-smoke/scripts/run-proof.ps1",
            ".tmp-release-smoke/custom_actions.py",
            ".tmp-release-smoke/proof_runner.py"
        )

        foreach ($entry in $expected) {
            $full = Join-Path $ProjectPath $entry
            if (-not (Test-Path $full)) {
                throw "Missing scaffold smoke output: $entry"
            }
        }
    }
    finally {
        if (Test-Path $tmpSmokeDir) {
            Remove-Item -Recurse -Force $tmpSmokeDir
        }
        Pop-Location
    }
}

if (-not $Execute) {
    Write-Host ""
    Write-Host "Dry-run complete. Re-run with -Execute to perform release dry-run checks."
    Write-Host "Examples:"
    Write-Host "  ./scripts/release-dry-run.ps1 -Execute"
    Write-Host "  ./scripts/release-dry-run.ps1 -Version 0.1.0 -Execute"
}