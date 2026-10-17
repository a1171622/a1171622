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

## The self-test

`selftest.bat` (also run by the installer) makes SOFiSTiK solve two steel cantilevers through the
server's own code and compares what the server reads from the `.cdb` with a hand calculation:
HEA 200, 6 m, first with nodes and beams (SOFiMSHA, 1 kN at the tip), then as structural line 7 in
group 3 (SOFiMSHC, 1 kN/m).

| Check | Expected |
| --- | --- |
| Section A, Iy read from the .cdb | 53.8 cm², 3692 cm⁴ (HEA 200 table) |
| E modulus | 210 000 N/mm² |
| Tip deflection | P L³ / 3EIy (+ shear part) ≈ 9.3 mm |
| Support reaction, moment | 1 kN, 6 kNm |
| Max beam moment, shear | 6 kNm, 1 kN, and 0 at the free end |
| SOFiSTiK's own stored reaction sum | 1 kN |
| Structural line model: beams found by SLN 7 and by group 3 | all 6 beams |
| Structural line model: reaction, moment, deflection | 6 kN, 18 kNm, w L⁴ / 8EIy ≈ 20.9 mm |
| The server starts and answers like it will for Claude | 22 tools |

The window ends with **ALL CHECKS PASSED** or lists what failed. The same text is saved in
`selftest\selftest_report.txt`; if anything fails, send that file to Claude.

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
| `cdb_node_results`, `cdb_support_reactions` | Displacements (mm), rotations (mrad), reactions (kN, kNm) and their sum |
| `cdb_beam_forces` | N, Vy, Vz, Mt, My, Mz by beam, group or structural line, with extremes |
| `cdb_truss_cable_forces` | Axial forces of trusses and cables |
| `cdb_envelope` | Max and min over many load cases (e.g. 101-118) with the governing load case |
| `cdb_read_key` | Advanced: any record in the database |
| `search_manuals`, `read_manual_page`, `list_manuals`, `index_manual` | Search the English manuals |
| `search_examples` | Search the shipped example `.dat` files |

Units returned: mm, mrad, kN, kNm, m. The `.cdb` is read with SOFiSTiK's own DLL and record layouts.

## Safety rules (settings.json)

Open `settings.json` in Notepad to change them, then restart Claude. Use double backslashes in paths.

- **work_folders**: the only places Claude may write `.dat` files and run calculations. Default:
  `C:\Sofistik workflow`. Add your project folders, for example
  `"work_folders": ["C:\\Sofistik workflow", "D:\\26016 HPC Kier BAM JV"]`.
- **read_folders**: extra folders Claude may read but never change.
- **allow_sys_commands**: `false` (default) refuses any `.dat` containing `+SYS`, because `+SYS`
  makes SOFiSTiK run Windows commands.
- **run_timeout_minutes**: a calculation is stopped after this long (default 60).
- One calculation runs at a time, and its `.cdb` is not read while it runs. If the project is open in
  SSD, Teddy or WinGRAF the `.cdb` may be locked: close it there first.
- A run replaces that model's earlier `.cdb` / `.prt` / `.erg`, as running it in Teddy does.
- Claude cannot change files in the server's own folder.
- `#INCLUDE` / `+APPLY` files must be findable next to the `.dat` (or by full path), so they can be
  checked for `+SYS` too; otherwise the run is refused.

## Limits

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
