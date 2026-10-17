# Release checklist

The lead follows this, in order, before telling the engineer a version is ready. Do not skip a
step; if one fails, fix it and start again from step 1. Tick each box in the release note.

## 1. Code is ready

- [ ] All changes for this version are merged to the release branch; nothing uncommitted.
- [ ] Version bumped in **both** `sofistik_mcp/server.py` (`VERSION`) and `pyproject.toml`
      (`version`), using semantic versioning (bug fix: 1.0.x, new tool or option: 1.x.0).
- [ ] `CHANGELOG.md`: the "Unreleased" entries moved under `## <version> - <date>`, written so the
      engineer can understand them; a new empty "Unreleased" section on top.
- [ ] If the tool list, units, settings or install steps changed: `README.md` updated (the tool
      count in the self-test table, too).

## 2. CI is green

- [ ] The `sofistik-mcp CI` workflow passed for the release commit on **all four** jobs:
      windows-latest and ubuntu-latest, Python 3.10 and 3.13. A skipped or cancelled job is not a pass.
- [ ] In the test log: no unexpected skips (`-rs` lists them), and coverage at or above the
      `fail_under` in `pyproject.toml`.

Same checks locally (from `sofistik-mcp/`, dev tools from `requirements-dev.txt`):

    ruff check .
    mypy sofistik_mcp run_server.py
    python -m compileall -q sofistik_mcp run_server.py
    python -m pytest -rs --cov=sofistik_mcp --cov-report=term-missing

## 3. Independent reviews

- [ ] At least one review by someone (or an agent) who did not write the change: correctness of
      results and units, the safety rules (work folders, `+SYS`, server folder), Windows paths.
- [ ] Every finding triaged in writing: fixed (commit named), or accepted with a reason, or moved to
      a tracked issue. No finding left unanswered.

## 4. Files on the engineer's PC

- [ ] Copy the `sofistik-mcp` folder to `C:\Sofistik workflow\sofistik-mcp` (keep the existing
      `settings.json` and `.venv`; do not copy `.git`, `__pycache__`, `.pytest_cache` or `selftest\run\`).
- [ ] Sizes verified: for every copied file, the size on the PC equals the size in the release
      commit (for example `Get-ChildItem -Recurse | Select FullName, Length` against
      `git ls-files -s` / `ls -l`). A size mismatch means a broken copy or changed line endings:
      copy again.
- [ ] The `.bat` files on the PC are still CRLF (Notepad shows them as one command per line).

## 5. On-PC acceptance

- [ ] Fully quit Claude. If `requirements.txt` changed, run `install.bat`; otherwise run
      `selftest.bat`.
- [ ] The self-test window ends with **ALL CHECKS PASSED**.
- [ ] `selftest\selftest_report.txt` from that run is attached to the release note.
- [ ] Claude restarted; in a new chat, ask "use the sofistik tools and show me the status".
      `sofistik_status` answers with the SOFiSTiK folder and the work folders from `settings.json`.

## 6. Tell the engineer

- [ ] Message: the version number, the CHANGELOG entry in plain words, anything they must do
      (usually nothing), and how to go back (the previous folder copy).
- [ ] Tag the release commit `sofistik-mcp-v<version>`.
