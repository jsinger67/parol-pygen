# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

- Added side-by-side export schema support for ParserExportModel v1 and v2.
- Added `parser-export-model.v2.schema.json` with `version = 2` and kept `parser-export-model.v1.schema.json` for backward compatibility.
- Validation now selects schema by export model version, keeping strict v1 and v2 contract checks.
- Added support for scanner-state `skip_tokens` from v2 exports in runtime model/scanner handling.
- Updated tests and fixtures to cover v1 and v2 compatibility behavior.

## 0.1.0 - 2026-04-03

- Initial extraction-prep baseline with Lalr1 and Llk runtime support.
- Added project scaffolding command and uv-first CI/release workflows.
- Added release preflight scripts.
