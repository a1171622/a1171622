# SOFiSTiK MCP server

Lets Claude work with SOFiSTiK 2027 on your PC: write a `.dat` input file, run it in SOFiSTiK
(batch mode, no window), read the errors and warnings, and read results straight from the `.cdb`.
It can also search the SOFiSTiK manuals and the ~1,200 shipped example files for the right syntax.

It runs on your PC only. Claude Desktop (and Claude Code, if you have it) start it in the background
when they open.

## Install (once, about 5 minutes)

1. Copy this folder to `C:\Sofistik workflow\sofistik-mcp` (it is already there if Claude put it there).
2. Fully quit Claude (right-click the Claude icon next to the clock, **Quit**).
3. Double-click **`install.bat`**. It:
   - checks Python (64-bit, 3.10 or newer; yours is fine),
   - makes a private Python environment in `.venv` and installs the MCP package (needs internet),
   - creates `settings.json`,
   - registers the server with Claude Desktop (and Claude Code if installed); your existing Claude
     settings are backed up first and nothing else in them is changed,
   - runs the **self-test** (below).
4. Open Claude again.
5. Ask Claude: *"Use the sofistik tools and show me the status."*
6. Open the live dashboard: http://localhost:8765 (or double-click `dashboard.bat`).

## The self-test

`selftest.bat` (also run by the installer) makes SOFiSTiK solve two steel cantilevers through the
server's own code and compares what the server reads from the `.cdb` with a hand calculation:
HEA 200, 6 m, first with nodes and beams (SOFiMSHA, 1 kN and 2 kN at the tip in load cases 1 and 2),
then as structural lines 7 (group 3, 1 kN/m) and 8 (group 4, 2 kN/m) (SOFiMSHC).

| Check | Expected |
| --- | --- |
| Section A, Iy read from the .cdb | 53.8 cm², 3692 cm⁴ (HEA 200 table) |
| E modulus | 210 000 N/mm² |
| Tip deflection | P L³ / 3EIy (+ shear part) ≈ 9.3 mm |
| Tip rotation | P L² / 2EIy ≈ 2.32 mrad |
| Forces that must be zero | N, Vy, Mt, Mz ≈ 0 |
| Envelope over load cases 1-2 | governed by LC 2, twice the LC 1 values |
| Support reaction, moment | 1 kN, 6 kNm |
| Max beam moment, shear | 6 kNm, 1 kN, and 0 at the free end |
| SOFiSTiK's own stored reaction sum | 1 kN |
| Structural line model: SLN 7 / group 3 and SLN 8 / group 4 | each gives only its own 6 beams |
| Structural line model: moment, deflection, reaction sum | 18 and 36 kNm, w L⁴ / 8EIy ≈ 20.9 mm, 18 kN |
| Structural line model: each beam's group by GDIV, by its structural line and by the group ranges | the three agree (a rule the `.cdb` gives no answer for is an INFO line) |
| The server starts and answers like it will for Claude | 24 tools |

Lines marked **INFO** are recorded but never fail the test: the load case titles read back (ASE may
replace SOFiLOAD's titles), the signs SOFiSTiK uses (tip direction, reaction sign), sps.exe's exit code
and whether each program printed its "n errors and m warnings" line, how long the `.cdb` overview and
load case list take to read, and the raw group codes in the `.cdb`. They settle facts that could not be
checked without SOFiSTiK. The window ends with **ALL CHECKS PASSED** or lists what failed. The same text is saved in
`selftest\selftest_report.txt`; if anything fails, send that file to Claude.

### Confirmed on SOFiSTiK 2027 (first PC run, 17 Oct 2026: ALL CHECKS PASSED)

- **Units** read from the `.cdb`: lengths m, forces kN, moments kNm, E in kN/m² (the tools convert
  to mm, cm², cm⁴ where they say so). Tip deflection, rotation, reactions, moments and shears match
  the hand calculation exactly.
- **Support reactions** are the force the support puts on the structure: a load of +1 kN in global
  +Z gives `pz = -1 kN` at the support. SOFiSTiK's stored reaction sum (`CLC_CTRL m_rz`) has the
  same sign as the node reactions.
- **Rotations** follow the right-hand rule (`ury` negative for a +Z deflection of a beam along +X).
  A cantilever's support moment `My` comes out negative (hogging).
- **Load case titles** written in SOFiLOAD are kept by ASE.
- `sps.exe` returns exit code 0 on a clean run, and AQUA, SOFiMSHA/C, SOFiLOAD and ASE print **no**
  "n errors and m warnings" line on a clean run (the server counts the messages itself).
- Beam groups: the `.cdb` group codes are `m_typ` 0 and 100. Group by GDIV is what SOFiSTiK models
  use; the structural line `m_nog` is empty, and the group range rule agrees with GDIV.

## What Claude can do with it

| Tool | What it does |
| --- | --- |
| `sofistik_status` | Shows where SOFiSTiK is and which folders the server may use |
| `write_dat_file` | Writes a `.dat` (never overwrites without asking; keeps a `.bak` copy) |
| `run_calculation` | Runs the `.dat` with `sps.exe`; returns status, every error and warning with the input line before it, programs run, output files |
| `get_job_result`, `stop_calculation` | A run (or a big `.cdb` read) longer than about 40 s answers "running"; Claude then waits for it with `get_job_result`, or stops it |
| `read_calculation_messages` | Errors and warnings of an earlier run (`.prt` / `.erg`) |
| `read_text_file`, `list_folder` | Read `.dat`, `.prt`, `.erg` files; find models |
| `cdb_overview`, `cdb_load_cases` | Project, element counts, materials, sections, groups, load cases (titles, reaction sums, eigenfrequencies) |
| `cdb_nodes` | Node numbers and coordinates (m) |
| `cdb_node_results`, `cdb_support_reactions` | Displacements (mm), rotations (mrad), reactions (kN, kNm) and their sum |
| `cdb_beam_forces` | N, Vy, Vz, Mt, My, Mz by beam, group or structural line, with extremes |
| `cdb_truss_cable_forces` | Axial forces of trusses and cables |
| `cdb_envelope` | Max and min over many load cases (e.g. 101-118) with the governing load case |
| `cdb_read_key` | Advanced: any record in the database |
| `search_manuals`, `read_manual_page`, `list_manuals`, `index_manual` | Search the English manuals |
| `search_examples` | Search the shipped example `.dat` files |
| `report_check` | A checking session puts its progress and key findings on the live dashboard |
| `dashboard_status` | What the dashboard shows right now, as data (for "how is the run going?") |

Units returned: mm, mrad, kN, kNm, m. The `.cdb` is read with SOFiSTiK's own DLL and record layouts.

## Live dashboard

While Claude is open, the server also serves a live page on this PC: **http://localhost:8765**.
Bookmark it, or double-click **`dashboard.bat`** (it also works when Claude is closed). The page
refreshes every 3 seconds and shows:

| Panel | What it shows | Where it comes from |
| --- | --- | --- |
| Now running | The SOFiSTiK module working now (AQUA, SOFIMSHA, SOFILOAD, ASE, BDK, MAXIMA ...) and the calculation with its running time | The programs running from the SOFiSTiK folder, and the server's own job |
| PC resources | CPU and RAM of the PC, with the last 10 minutes | Windows, via psutil |
| Checks and key findings | Each check's status (running, passed, failed, attention, waiting, done), its current step and its findings, newest first | `report_check` calls from the checking session |
| Processes | Every SOFiSTiK program and Claude process with its CPU and RAM | Windows, via psutil |
| Claude token usage today | Output, new input and cache tokens, per session | The usage Claude Code records on this PC |
| Recent calculations | Last 20 runs: status, errors, warnings, time, first error | The server's run results |

What it cannot show: token use of Claude Desktop chats and of claude.ai / cloud sessions (they record
nothing on this PC), and how much of the plan's usage limit is left (claude.ai shows that under
Settings > Usage).

**From your phone.** On the same Wi-Fi: set `"dashboard_lan": true` in `settings.json`, restart Claude,
allow Python when Windows asks, then open `http://<PC name>:8765` on the phone (the PC name is shown at
the top of the page). Anyone on that network can then read the page (file names, check findings, process list, token
counts; no password), so use it on your own or the office network only. Nothing on it can change
anything.
Away from the PC's network: ask Claude in your claude.ai project "show the SOFiSTiK dashboard". This
works only while the Claude app is open on the PC with Remote Control switched on: Claude then starts a
session on the PC, which calls `dashboard_status` and shows the answer as a snapshot (not live).

**Status files** (in `<first work folder>\_dashboard\`, e.g. `C:\Sofistik workflow\_dashboard\`):
`server-<number>.json` is written by each running server (one closed for a day is removed), and
`checks\<check name>-<code>.json` by `report_check`. A session without the SOFiSTiK tools can write a
check file itself (any `.json` name in `checks\`) in this format:

```json
{
  "check": "26016 member checks",
  "status": "running",
  "step": "ASE: ULS combinations 101-154",
  "progress": "3 of 7",
  "updated": "2026-10-17T23:20:00",
  "findings": [
    {"time": "2026-10-17T23:18:00", "level": "fail", "text": "B81 UB 457x191x89: LTB ratio 1.12 (LC 118)"}
  ]
}
```

`status` is one of running, passed, failed, attention, waiting, done; `level` one of info, pass,
warn, fail. `"dashboard_port": 0` in `settings.json` switches the page off.

## Safety rules (settings.json)

Open `settings.json` in Notepad to change them, then restart Claude. Use double backslashes in paths.

- **work_folders**: the only places Claude may write `.dat` files and run calculations. Default:
  `C:\Sofistik workflow`. Add your project folders, for example
  `"work_folders": ["C:\\Sofistik workflow", "D:\\26016 HPC Kier BAM JV"]`.
- **read_folders**: extra folders Claude may read but never change.
- **allow_sys_commands**: `false` (default) refuses any `.dat` that could make SOFiSTiK run a
  Windows command: `+SYS` and `*SYS` lines (also a bare `SYS` word at the start of a line, and after
  a `;`), a record whose first word is built with a `$(...)` substitution (`$(X) ...`, `+S$(Y) ...`;
  only numbers defined earlier in the file, with no letters next to them, are allowed), a `#define`
  value that starts with `SYS` or contains `;`, `SYS` beyond character 255 of a line (CADINP's line
  limit), and a file that cannot be read for certain (NUL bytes, an unknown byte order mark; UTF-16
  and UTF-32 files with a byte order mark are read). The rule is deliberately broad; if a model
  really needs such a line, set it to `true` and restart Claude.
  `write_dat_file` refuses to write such content too, so it cannot be left for you to run by hand.
- **run_timeout_minutes**: a calculation is stopped after this long (default 60).
- Every folder in `settings.json` must be a full path with the drive (e.g. `D:\\26016 HPC`);
  a relative path is refused because it would depend on where Claude was started.
- One calculation runs at a time. While it runs, `write_dat_file` refuses to write anything (SOFiSTiK
  reads `#INCLUDE` / `+APPLY` files during the run), and its `.cdb` is not read. If an input file
  changes during the run anyway, the result says so (status `check: input changed during run`).
  If the project is open in SSD, Teddy or WinGRAF the `.cdb` may be locked: close it there first.
- A run writes `<name>.mcp-running` next to the `.dat` while it runs, so a second Claude window
  cannot start a calculation in the same folder. If Claude or the server is closed during a run,
  SOFiSTiK is stopped too, and so is everything it started (each run has its own Windows job object,
  which a stop or time-out ends as a whole). The lock file names the PC and the process (number and
  start time); one left by a crash on this PC is removed automatically, one written by another PC
  (a shared network folder) never is: the message names that PC, and you delete the file by hand once
  nothing runs there.
- A run replaces that model's earlier `.cdb` / `.prt` / `.erg`, as running it in Teddy does.
- Claude cannot change files in the server's own folder. File names with `:` after the drive,
  a trailing dot or space, a device name (`CON`, `NUL`, `COM1` ...) or a leading `-` are refused.
- `#INCLUDE` / `+APPLY` files (also written `#INCL`, `APPL`, or after a `;`) are checked for `+SYS` too: every file SOFiSTiK could open is
  checked (`name` and `name.dat`, next to the including file and next to the main `.dat`;
  `$(NAME)` is the `.dat`'s name). A file that cannot be found or checked refuses the run, and so
  does one outside the folders the server may read (SOFiSTiK copies included text into the `.erg`).
- A status other than `ok` / `ok with warnings` means the results are not valid yet: `errors`,
  `not finished` (a program has no `*** Stop` line, or the calculation no end line), `timed out`,
  `stopped`. A non-zero sps.exe exit code with a clean protocol does not change the status (SOFiSTiK
  does not document sps.exe's exit codes); it is shown as a warning, and the self-test report prints
  the exit code of its runs. Results read from a `.cdb` that is
  older than its `.prt` / `.dat`, or whose last run here was not clean, carry a
  `stale_results_warning`.

## Limits

- A file that SOFiSTiK itself writes during the run and then reads with `+APPLY` (for example
  CSM's `+APPLY "$(NAME)_csm.dat"`) cannot be checked before the run: the run is refused while the
  file does not exist, and reported as `check: input changed during run` when CSM rewrites it.

- If the self-test's structural line check fails, do not rely on filtering beams by SLN number
  (groups and beam numbers still work).
- Results are read for nodes, beams, trusses and cables. Shell (quad) results are reachable only
  through `cdb_read_key` for now.
- Claude still has to get the CADINP right. The server shows SOFiSTiK's errors so Claude can fix
  them, but an input that runs without errors can still be wrong engineering: check the reaction sums
  and the key numbers as you would for any model.
- The manual search covers the English manuals that were in `C:\Sofistik workflow` on 17 Oct 2026;
  a new PDF can be added with `index_manual`.

## Remove

Double-click `uninstall.bat`, restart Claude, then delete the folder.

## For developers

Python package `sofistik_mcp/` (MCP Python SDK 1.30, stdio). The `.cdb` is read in a separate
worker process (`cdb_worker.py`) so SOFiSTiK's DLL can never write into the MCP channel or crash
the server. Tests without SOFiSTiK: `python -m pytest tests` (uses a fake `.cdb` built from
SOFiSTiK's record layouts and real `.prt` / `.erg` files).
