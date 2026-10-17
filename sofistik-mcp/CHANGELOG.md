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
- Third review round, safety: a `$(...)` substitution anywhere in a record's first word (`+S$(Y)`)
  refuses the run; UTF-16 / UTF-32 input files are read by their byte order mark, files with NUL bytes
  or an unknown mark are refused; `#define` values mentioning "system" are no longer refused;
  `APPL` and includes after a `;` are followed; `$(X)` counts as numeric only when `X` is defined
  earlier; `SYS` beyond character 255 of a line is refused; a stop or time-out ends the run's own
  Windows job object (taskkill as fallback); lock files carry the PC name and process start time (a
  lock from another PC is never removed automatically, a reused process number is recognised);
  install.bat checks the Python probe's printed marker and re-makes a `.venv` that fails it.
- Third review round, results: a missing "n errors and m warnings" line is a note, not "not finished";
  a non-zero sps.exe exit code with a clean protocol is a warning, not a status; group ranges with
  element code 0 and 101 count as beam groups; a beam whose GDIV group differs from its group range
  is listed in a warning; envelopes over MAXIMA superposition load cases carry a note. Self-test:
  compares the three group rules on the structural line model, prints sps.exe's exit code, the
  totals lines, the read times and the raw group codes; titles and signs are INFO lines.

## 1.0.0 - 2026-10-17

### Added
- Initial release: local stdio MCP server for SOFiSTiK 2027 with 22 tools: write and run `.dat`
  files with `sps.exe`, read errors and warnings from `.prt` / `.erg`, read nodes, reactions, beam,
  truss and cable forces and envelopes from the `.cdb` (in a separate worker process), search the
  manuals and shipped examples.
- `install.bat`, `selftest.bat` (two steel cantilevers checked against hand calculations),
  `uninstall.bat`.
