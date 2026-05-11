param(
    [string]$ProjectPath,
    [string]$Version,
    [string]$ChangelogPath
)

$ErrorActionPreference = "Stop"

function Get-ProjectVersion {
    param([string]$PyprojectPath)

    $versionLine = Get-Content $PyprojectPath | Where-Object { $_ -match '^version\s*=\s*"([^"]+)"\s*$' } | Select-Object -First 1
    if (-not $versionLine) {
        throw "Failed to detect project version from pyproject.toml"
    }
    return [regex]::Match($versionLine, '^version\s*=\s*"([^"]+)"\s*$').Groups[1].Value
}

function Normalize-Version {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $Value
    }

    # Accept workflow/tag style inputs like v0.2.0 and compare canonical values.
    return ($Value.Trim() -replace '^[vV]', '')
}

if (-not $ProjectPath) {
    $ProjectPath = (Resolve-Path (Join-Path $PSScriptRoot ".." )).Path
}

$pyprojectPath = Join-Path $ProjectPath "pyproject.toml"
if (-not (Test-Path $pyprojectPath)) {
    throw "pyproject.toml not found at: $pyprojectPath"
}

$projectVersion = Get-ProjectVersion -PyprojectPath $pyprojectPath
if (-not $Version) {
    $Version = $projectVersion
}

$Version = Normalize-Version -Value $Version
$projectVersion = Normalize-Version -Value $projectVersion

if ($Version -ne $projectVersion) {
    throw "Version mismatch: requested '$Version' but pyproject.toml contains '$projectVersion'"
}

if (-not $ChangelogPath) {
    $ChangelogPath = Join-Path $ProjectPath "CHANGELOG.md"
}

if (-not (Test-Path $ChangelogPath)) {
    throw "CHANGELOG.md not found at: $ChangelogPath"
}

$changelog = Get-Content $ChangelogPath -Raw
if (-not $changelog.Contains($Version)) {
    throw "No CHANGELOG entry found for version '$Version' in $ChangelogPath"
}

Write-Host "Release gate passed."
Write-Host "Version: $Version"
Write-Host "CHANGELOG: $ChangelogPath"