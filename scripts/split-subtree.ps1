param(
    [string]$MonorepoPath = "D:/Source/parol",
    [string]$DestinationPath = "D:/Source/parol-pygen",
    [string]$Prefix = "tools/parol-pygen",
    [string]$SplitBranch = "split/parol-pygen",
    [switch]$Execute,
    [switch]$ResetDestination
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

Ensure-Path $MonorepoPath "Monorepo path"

Invoke-Step -Label "Verify monorepo git status" -Preview "git -C $MonorepoPath status --short" -Action {
    $status = git -C $MonorepoPath status --short
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to read git status at $MonorepoPath"
    }
    if ($status) {
        throw "Working tree is not clean at $MonorepoPath. Commit or stash changes before running extraction."
    }
    Write-Host "Working tree is clean."
}

Invoke-Step -Label "Recreate split branch" -Preview "git -C $MonorepoPath branch -D $SplitBranch ; git -C $MonorepoPath subtree split --prefix $Prefix -b $SplitBranch" -Action {
    git -C $MonorepoPath branch -D $SplitBranch 2>$null | Out-Null
    git -C $MonorepoPath subtree split --prefix $Prefix -b $SplitBranch
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create split branch '$SplitBranch'."
    }
}

Invoke-Step -Label "Prepare destination repository directory" -Preview "reset=$ResetDestination ; mkdir $DestinationPath ; git init" -Action {
    if (Test-Path $DestinationPath) {
        if (-not $ResetDestination) {
            throw "Destination already exists: $DestinationPath. Use -ResetDestination to remove it."
        }
        Remove-Item -Recurse -Force $DestinationPath
    }
    New-Item -ItemType Directory -Path $DestinationPath | Out-Null
    git -C $DestinationPath init
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to initialize git repository at $DestinationPath"
    }
}

Invoke-Step -Label "Pull split branch into destination" -Preview "git -C $DestinationPath pull $MonorepoPath $SplitBranch" -Action {
    git -C $DestinationPath pull $MonorepoPath $SplitBranch
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to pull split branch into destination repository."
    }
}

Invoke-Step -Label "Display next verification commands" -Preview "uv sync ; uv run python -m unittest discover -s tests -p test_*.py" -Action {
    Write-Host "Run next in destination repository:"
    Write-Host "  uv sync"
    Write-Host "  uv run python -m unittest discover -s tests -p \"test_*.py\""
    Write-Host "  uv run python -m parol_pygen.cli info"
}

if (-not $Execute) {
    Write-Host ""
    Write-Host "Dry-run complete. Re-run with -Execute to perform the split."
    Write-Host "Example:"
    Write-Host "  ./scripts/split-subtree.ps1 -Execute -ResetDestination"
}
