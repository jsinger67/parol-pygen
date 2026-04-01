# Extraction Checklist

This checklist helps move `tools/parol-pygen` into a standalone repository with history and keep it releasable on PyPI.

## 1. Preconditions

- Ensure `tools/parol-pygen` tests are green in the monorepo.
- Ensure there is a clean checkpoint commit on the working branch.
- Decide target repository name (recommended: `parol-pygen`).

## 2. Create split branch with subtree history

From the monorepo root:

```powershell
git subtree split --prefix tools/parol-pygen -b split/parol-pygen
```

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
python -m pip install -e .
python -m unittest discover -s tests -p "test_*.py"

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
python -m pip install -e .
python -m unittest discover -s tests -p "test_*.py"
python -m parol_pygen.cli --version
python -m parol_pygen.cli info
```

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
python -m pip install build
python -m build
```

- Test local install from wheel/sdist.

## 8. TestPyPI and PyPI

```powershell
python -m pip install twine
python -m twine upload --repository testpypi dist/*
# smoke test from TestPyPI in a clean venv
python -m twine upload dist/*
```

Recommended sequence:

1. Publish to TestPyPI first.
2. Run install and CLI smoke checks in a clean virtual environment.
3. Publish to PyPI only after TestPyPI smoke checks are green.

## 8a. Release version and tag gates

Before starting publish workflows:

1. Update version in `pyproject.toml`.
2. Add release notes entry in `CHANGELOG.md`.
3. Ensure CI and local tests are green.
4. Create an annotated release tag in the standalone repository.

Suggested command order:

```powershell
# 1) Bump version and commit
git add pyproject.toml CHANGELOG.md
git commit -m "chore(release): cut vX.Y.Z"

# 2) Tag release candidate or final release
git tag -a vX.Y.Z -m "parol-pygen vX.Y.Z"
git push origin main
git push origin vX.Y.Z
```

Publish workflow gates:

1. Run `publish.yml` with `repository=testpypi`.
2. Run `testpypi-smoke.yml` with `version=X.Y.Z`.
3. Publish to PyPI only if smoke workflow is green.
4. Run `pypi-smoke.yml` with `version=X.Y.Z` after PyPI publish.
5. Create GitHub release notes for tag `vX.Y.Z` only after PyPI smoke is green.

## 9. Post-extraction updates in monorepo

- Replace `tools/parol-pygen` with a pointer note or submodule strategy.
- Update monorepo docs to reference the new repository.
- Keep export contract references aligned with `parol` release notes.

## 10. Optional safety checks

- Tag extraction baseline in both repos.
- Open a tracking issue for follow-up tasks (CI badges, release cadence, docs links).
