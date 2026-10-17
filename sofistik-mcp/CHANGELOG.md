# Changelog

All notable changes to the SOFiSTiK MCP server. Versions follow `VERSION` in
`sofistik_mcp/server.py`, which must equal `version` in `pyproject.toml` (CI checks this).

## Unreleased

### Added
- Build and quality pipeline: `pyproject.toml` (ruff, mypy, pytest, coverage settings),
  `requirements-dev.txt`, GitHub Actions CI on Windows and Linux (Python 3.10 and 3.13),
  `.bat` line-ending and ASCII check, `RELEASE.md` checklist, this changelog.

### Changed
- Lint and type-check clean-ups only (type annotations, wrapped long lines); no behaviour change.

## 1.0.0 - 2026-10-17

### Added
- Initial release: local stdio MCP server for SOFiSTiK 2027 with 22 tools: write and run `.dat`
  files with `sps.exe`, read errors and warnings from `.prt` / `.erg`, read nodes, reactions, beam,
  truss and cable forces and envelopes from the `.cdb` (in a separate worker process), search the
  manuals and shipped examples.
- `install.bat`, `selftest.bat` (two steel cantilevers checked against hand calculations),
  `uninstall.bat`.
