# Extraction Checklist

This checklist helps move `tools/parol-pygen` into a standalone repository with history and keep it releasable on PyPI.

## 1. Preconditions

- Ensure `tools/parol-pygen` tests are green in the monorepo.
- Ensure there is a clean checkpoint commit on the working branch.
- Decide target repository name (recommended: `parol-pygen`).
- Ensure `uv` is installed and available on PATH.

## 2. Create split branch with subtree history

From the monorepo root:

```powershell
git subtree split --prefix tools/parol-pygen -b split/parol-pygen
```

Recommended automated flow (dry-run first):

```powershell
Set-Location D:/Source/parol/tools/parol-pygen
./scripts/split-subtree.ps1
./scripts/split-subtree.ps1 -Execute -ResetDestination
```

Notes:

- The script defaults to dry-run and prints planned steps.
- `-Execute` performs the extraction.
- `-ResetDestination` removes an existing destination folder before recreating it.
- If you prefer full manual control, use section 2a below.

## 2a. Split day playbook (recommended command order)

Run these in order to minimize mistakes and make rollback easy:

```powershell
# 1) Ensure clean state in monorepo
Set-Location D:/Source/parol
git status

# 2) Create fresh split branch from current branch tip
git branch -D split/parol-pygen 2>$null
git subtree split --prefix tools/parol-pygen -b split/parol-pygen

# 3) Create/refresh destination repo locally
Set-Location D:/Source
if (Test-Path ./parol-pygen) { Remove-Item -Recurse -Force ./parol-pygen }
mkdir parol-pygen | Out-Null
Set-Location ./parol-pygen
git init
git pull D:/Source/parol split/parol-pygen

# 4) Smoke verify
uv sync
uv run python -m unittest discover -s tests -p "test_*.py"

# 5) First commit/tag in new repo (optional but recommended)
git tag split-baseline
```

## 2b. Rollback procedure

If anything goes wrong during extraction:

```powershell
# Cleanly abandon destination repo directory
Set-Location D:/Source
if (Test-Path ./parol-pygen) { Remove-Item -Recurse -Force ./parol-pygen }

# Remove split branch in monorepo and start over
Set-Location D:/Source/parol
git branch -D split/parol-pygen

# Recreate split branch from the desired source commit/branch
git subtree split --prefix tools/parol-pygen -b split/parol-pygen
```

Rollback safety note:

- Do not delete or rewrite your checkpoint commits on `python-poc`.
- Re-running `git subtree split` is deterministic for the same source commit.

## 3. Initialize the new repository

```powershell
Set-Location D:/Source
mkdir parol-pygen
Set-Location parol-pygen
git init
git pull D:/Source/parol split/parol-pygen
```

Alternative with explicit remote:

```powershell
git init
git remote add monorepo D:/Source/parol
git fetch monorepo split/parol-pygen
git checkout -b main FETCH_HEAD
```

## 4. Verify project health in new repository

From the new repository root:

```powershell
uv sync
uv run python -m unittest discover -s tests -p "test_*.py"
uv run parol-pygen --version
uv run python -m parol_pygen.cli info
```

Recommended automated flow (dry-run first):

```powershell
Set-Location D:/Source/parol-pygen
./scripts/verify-split.ps1
./scripts/verify-split.ps1 -Execute
```

Notes:

- The script defaults to dry-run and prints planned checks.
- `-Execute` runs sync, tests, CLI info, and scaffold smoke validation.

## 5. Prepare GitHub repository and push

```powershell
git remote add origin <NEW_REPO_URL>
git push -u origin main
```

## 6. Enable CI

- Confirm `.github/workflows/python-ci.yml` exists in the new repo.
- Verify CI runs for push and pull_request on `main`.

## 7. Publish readiness pass

- Confirm `pyproject.toml` metadata is correct for standalone ownership.
- Build artifacts:

```powershell
uv sync --extra dev
uv run python -m build
```

- Test local install from wheel/sdist.

## 8. TestPyPI and PyPI

```powershell
uv sync --extra dev
uv run python -m twine upload --repository testpypi dist/*
# smoke test from TestPyPI in a clean venv
uv run python -m twine upload dist/*
```

Recommended sequence:

1. Publish to TestPyPI first.
2. Run install and CLI smoke checks in a clean virtual environment.
3. Publish to PyPI only after TestPyPI smoke checks are green.

## 8a. Release version and tag gates

Before starting publish workflows:

1. Update version in `pyproject.toml`.
2. Ensure a release entry for the version exists in `CHANGELOG.md`.
3. Ensure CI and local tests are green.
4. Create an annotated release tag in the standalone repository.

Suggested command order:

```powershell
# 1) Bump version and commit
./scripts/check-changelog-entry.ps1
git add pyproject.toml CHANGELOG.md
git commit -m "chore(release): cut vX.Y.Z"

# 2) Tag release candidate or final release
git tag -a vX.Y.Z -m "parol-pygen vX.Y.Z"
git push origin main
git push origin vX.Y.Z
```

Publish workflow gates:

1. Run `publish.yml` with `repository=testpypi` and `version=X.Y.Z`.
2. Run `testpypi-smoke.yml` with `version=X.Y.Z`.
3. Publish to PyPI only if smoke workflow is green and the current commit is tagged `vX.Y.Z`.
4. Run `pypi-smoke.yml` with `version=X.Y.Z` after PyPI publish.
5. Create GitHub release notes for tag `vX.Y.Z` only after PyPI smoke is green.

Notes:

- PyPI publish job requires explicit `version` input.
- PyPI publish job validates that tag `v<version>` exists and points to the current commit.

## 9. Post-extraction updates in monorepo

- Replace `tools/parol-pygen` with a pointer note or submodule strategy.
- Update monorepo docs to reference the new repository.
- Keep export contract references aligned with `parol` release notes.

## 10. Optional safety checks

- Tag extraction baseline in both repos.
- Open a tracking issue for follow-up tasks (CI badges, release cadence, docs links).
- Keep `scripts/split-subtree.ps1` and `scripts/verify-split.ps1` in sync with your extraction runbook.
