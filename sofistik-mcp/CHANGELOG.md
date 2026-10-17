# Changelog

All notable changes to the SOFiSTiK MCP server. Versions follow `VERSION` in
`sofistik_mcp/server.py`, which must equal `version` in `pyproject.toml` (CI checks this).

## 1.2.0 - 2026-10-17

### Added
- Live dashboard (`sofistik_mcp/dashboard.py`, `dashboard.html`): a read-only page at
  http://localhost:8765, served by the server while Claude is open and by `dashboard.bat` on its own.
  It shows the SOFiSTiK module running now, the calculation and its time, PC CPU/RAM, SOFiSTiK and
  Claude processes, checks with their key findings, the last 20 runs and today's Claude Code token
  use on the PC. `"dashboard_lan": true` opens it to phones on the same Wi-Fi; `"dashboard_port": 0`
  switches it off.
- Tools `report_check` (a checking session posts status, step, progress and findings) and
  `dashboard_status` (the dashboard's data, for answering "how is the run going?"). 24 tools.
- Status files in `<first work folder>\_dashboard\` (format in README).
- Dependency: psutil 7.1.3 (CPU, RAM, processes). Run install.bat again to get it.

### Fixed
- Self-test report printed "(? load cases)" instead of the count (cosmetic).

### Documentation
- README: SOFiSTiK 2027 conventions confirmed by the first PC acceptance run (units, reaction
  and rotation signs, titles, exit code, group codes). REVIEW-1.1.0.md records the run.

## 1.1.0 - 2026-10-17

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
