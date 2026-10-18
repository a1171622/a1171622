# 01 Failure catalogue: every recorded failure, gotcha and wrong assumption (for the Haiku executor)

Author: failure-mode archaeologist (skill-design team), 2026-10-18. Offline evidence work only; no runs started.

Each item says what went wrong (or would go wrong), how a Haiku executor would notice it, and the rule that stops it
happening again. The rules are written as commands, so they can be pasted into a SKILL.md.

## 0. How to read this

**Stages:** `AUTH` author CADINP · `PRE` pre-run · `RUN` run · `MON` monitor · `ERR` errors · `RES` results
· `MEM` member check · `REP` report · `ENV` environment / remote / PC.

**Evidence keys** (line numbers are `cat -n` lines as of 2026-10-18 01:45Z):

| Key | File |
|---|---|
| MEM | /tmp/claude/memory/team/silo/MEMORY.md |
| LONG | memory sofistik-long-runs.md |
| MCPm | memory project-sofistik-mcp.md |
| BENm | memory project-sofistik-benchmarks.md |
| BDKm | memory sofistik-bdk-cadinp-facts.md |
| AUDm | memory project-26016-load-audit.md |
| LTBm | memory project-26016-ltb-check.md |
| MSHm | memory project-structured-meshing.md |
| WINDm | memory wind-beam-loads-tool.md |
| IDEAm | memory idea-iom-import-lessons.md + idea-statica-integration.md |
| RUNLOG | /mnt/project-files/26016/member-check/RUN_LOG.md |
| CHG | /mnt/project-files/sofistik-mcp/CHANGELOG.md |
| RDM | /mnt/project-files/sofistik-mcp/README.md |
| REV | /mnt/project-files/sofistik-mcp/REVIEW-1.1.0.md |
| SRV / SOL / MSG / LCK | sofistik-mcp/sofistik_mcp/server.py / solver.py / messages.py / cdblock.py (v1.3.0 source) |
| SRV11 | server.py inside /mnt/project-files/sofistik-mcp-1.1.0.zip |
| AUD | /mnt/project-files/26016/audit/26016_load_audit.md |
| UNI | /mnt/project-files/26016/audit/26016_loads_unified.dat |
| BALL | /mnt/project-files/26016/ltb/26016_buckling_all_members.md |
| LTBS | /mnt/project-files/26016/ltb/26016_loads_and_LTB_summary.md |
| CHK2 | /mnt/project-files/26016/member-check/run/26016_check_v2.dat |
| BEN | /mnt/project-files/sofistik-benchmarks/BENCHMARK_RESULTS.md |
| AQBN | /mnt/project-files/reports/sofistik_report/sofistik/AQB_NOTES.md |
| REPR | /mnt/project-files/reports/sofistik_report/README.md |
| LEAD | /mnt/project-files/reports/sofistik_report/reviews/LEAD_DECISIONS.md |
| NATF | /mnt/project-files/reports/sofistik_native/FINDINGS.md |
| TPL | /mnt/project-files/sofistik-templates/EN1990_combinations_buildings.dat |
| STAIR | /mnt/project-files/26016/stairs/26016_stairs_model_check.md |
| MESHR | /mnt/project-files/meshing/research/03_review.md |

**Evidence grades:** **V** = recorded as having happened, or read in source or manual text. **I** = inferred by
me from code or documents and never seen on the PC. Every item carries one grade.

**Test types:** `RX` = a regex on the .dat (run it with grep -P / Python before writing the file to the PC).
`TOOL` = an MCP tool call and the field to check. `HUMAN` = needs Wing or the lead; Haiku must stop and ask.

---

## 1. State of the system that the rules depend on (read first)

| Fact | Value at 2026-10-18 01:42Z | Evidence |
|---|---|---|
| MCP server loaded on NguyenPC3 | **v1.2.0**. v1.3.0 is built, but installing it waits for Wing's typed OK and a Claude app restart after the live run. | MEM 19-20; MCPm 19 |
| Tools in v1.2.0 | 24: no `check_cdb_lock`, `clear_cdb_lock` or `clone_cdb`, and **one calculation at a time** | MEM 19; CHG 40-50; MCPm 19 |
| Tools in v1.3.0 | 27 (the README self-test row says 27) | RDM 46; SRV `@mcp.tool` count |
| Default time limit | v1.1/v1.2: **60 min**. v1.3: 0 = no limit. **But install.bat keeps an existing settings.json** (`if not exist settings.json copy ...`), so a PC upgraded from 1.1 may still have 60 in it. | SRV11 config default 60; install.bat 47; CHG 27 |
| `timeout_minutes` semantics | v1.1 **and** v1.3: `min(timeout_minutes, settings limit)`. It can only **shorten** a limit set in settings.json, never lengthen it. With settings 0 (no limit), it sets the limit. | SRV11 282-284; SRV 330-332 (V, code) |
| Live run | 26016_check_v2 (model + loads + BDK + alpha_cr + AQB), started 00:06Z, still in BDK at 01:42Z, ~4 GB RAM free | RUNLOG 12-15; MEM 30 |
| Tool names from the cloud | `mcp__remote-devices__sofistik__*` (desktop app route, works without Remote Control) | MCPm 17 |

---

## 2. The catalogue

### AUTH: writing the CADINP (.dat)

**A01 · Comma list longer than about 25 values** (V, found by review before any run)
- Symptom: CADINP error or silently truncated LC list, so BDK checks fewer combinations. The real 43-47 number list in the v1 BDK file would have failed.
- Root cause: a CADINP comma list holds only about 25 values (exact limit unverified). `$$` continuation is not allowed for lists.
- Rule: **Write load-case ranges as generation instructions `LC (101 130 1)`, one record per contiguous range. Never write more than 20 comma-separated values in one record. Never continue a list with `$$`.**
- Test RX: `^\s*\w+\s+[^$!\n]*?(\d+\s*,\s*){20,}` must have 0 hits. (All four 26016 run files give 0 today.)
- Evidence: BDKm 7; LTBS §6 ¶"Independent review" (line 175); CHK2 71300-71303 (the generation form in use).

**A02 · Line longer than 255 characters** (V, manual fact)
- Symptom: the input is cut off at character 255, so items are dropped without an error. The MCP server also refuses `SYS` beyond column 255.
- Rule: **Keep every line ≤ 255 characters, comments included.**
- Test RX: `awk 'length($0)>255'` must return nothing.
- Evidence: BDKm 7; RDM 159; CHG (1.1.0) 80.

**A03 · Variable names that contain a CADINP operator (DIV, SIN, COS, SQR …)** (V, review fix)
- Symptom: `#NDIV` is parsed as `#N DIV …`, which gives a wrong value or a syntax error.
- Rule: **Never use a variable name containing DIV, SIN, COS, TAN, SQR, ABS, EXP, LOG, MOD, MIN or MAX. Use NPART, NSEG and similar.** (The operator list beyond DIV/SIN/COS/SQR is inferred.)
- Test RX: `(?i)(STO|LET|DEL|RCL)#\w*(DIV|SIN|COS|TAN|SQR|ABS|EXP|LOG|MOD|MIN|MAX)\w*` must have 0 hits.
- Evidence: BDKm 11; LTBm 13 (NDIV renamed NPART); BALL §5.

**A04 · An expression or IIF inside COPY NO / FACT** (V, manual + review)
- Symptom: the factor is read as a literal text. The combination gets a wrong factor, or the COPY record fails.
- Root cause: COPY NO and FACT accept literals, so anything other than a plain `#name` or a number can be read as text.
- Rule: **Precompute every factor with `STO#F …` or `LET#F …` and write `COPY NO #N FACT #F`. For array items, use `LET#N #A(#K)` first.**
- Test RX: `(?i)^\s*COPY\b.*\b(NO|FACT)\s+(?!#\w+\b|[-+]?\d)` → 0 hits, and `(?i)^\s*COPY\b.*FACT\s+#\w+\s*[-+*/(]` → 0 hits.
- Evidence: AUDm 46; AUD 207, 235; UNI 6055-6064 (the LET#N pattern).

**A05 · LC TYPE 'IMP' used in ASE linear or MAXIMA** (V, review HIGH)
- Rule: **Never give a load case TYPE 'IMP' when it goes into a linear ASE or MAXIMA. Give imperfection (EHF) cases their own action `EHF`.**
- Test RX: `(?i)\bTYPE\s+'?IMP` → 0 hits.
- Evidence: AUDm 47; AUD 200.

**A06 · QUAD temperature written as TYPE DT** (V, review HIGH)
- Symptom: a gradient is applied instead of a uniform temperature.
- Rule: **Uniform temperature on QUAD/area elements is `DTXY`. `DT` is a gradient.**
- Test RX: `(?i)\bQUAD\b.*\bTYPE\s+DT\b` → 0 hits.
- Evidence: AUDm 48; AUD 201.

**A07 · A MAXIMA ACT record without its factors** (V, found in Wing's old stairs file)
- Symptom: wind ψ0 silently becomes 0.6 (the EN default) instead of the UK NA 0.5.
- Root cause: an ACT record in MAXIMA resets that action to the INI/code defaults.
- Rule: **Every ACT record in MAXIMA must restate GAMU and PSI0/PSI1/PSI2 as parameters.**
- Test RX: inside a `+PROG MAXIMA` block, every `^\s*ACT\b` line must contain both `GAMU` and `PSI0`.
- Evidence: AUDm 49; AUD 47, 204; UNI 7553-7716.

**A08 · Expecting LC FACT to scale temperature** (V, manual)
- Rule: **Never rely on LC FACT or COPY FACT to scale temperature loads. Write the temperature directly in each combination.**
- Evidence: AUDm 50; AUD 208.

**A09 · MAXIMA `LC NO -1`, or action-based selection** (V, found in Wing's stairs file)
- Symptom: an envelope that adds the stair wind twice, mixes wind directions, or puts a full deck together with a pattern.
- Rule: **In MAXIMA, list every load case explicitly. Never use `LC NO -1`. Give building-block cases TYPE '-' (no action) so automatic superposition cannot add them twice.**
- Test RX: `(?i)\bLC\s+NO\s+-1\b` outside comments → 0 hits.
- Evidence: AUD 45, 54; UNI 17-20.

**A10 · Result numbers that clash** (V, found by the audit)
- Symptom: MAXIMA results at 2101-2182 overwrote the eigenmodes at 2101-2110, or the other way round. "Whichever ran last overwrote the other."
- Rule: **Before choosing BASE, LCST, EIGE or LC numbers, list the database's load cases (`cdb_load_cases`) and pick a free block. 26016 reserved blocks: 1-99 basic cases, 101-154 ULS, 201-223 SLS, 301-458 patterns, 501-512 EHF, 2001-2110 eigen, 4101-4499 MAXIMA, 9100 BDK envelope, 9201-9320 buckling modes.** The EN1990 template's BASE 2100-3300 clashes with this project's eigen numbers (see conflict K07).
- Test TOOL: `cdb_load_cases(cdb)` → none of the new numbers is already in `rows`.
- Evidence: AUDm 32; AUD 46; TPL header lines 17-25; CHK2 77300-77310.

**A11 · A load counted twice in a combination** (V: Wing's wish; V: proven by script for the current file)
- Rule: **Define the groups once (#GL, #QL, #HL). Every combination loops over them. Self-weight only via FACD, and never COPY LC 1. One wind direction with one factor per combination. Never superpose QF (full decks) with QB (patterns).** After generating, run an independent decomposition script: every basic LC appears at most once per combination, no combination has two wind directions, LC 1 is never copied.
- Test: an offline Python expander (as in `audit/generator/check_v2.py`) → 0 duplicates. RX smoke check per combination block: no LC number appears twice in the `COPY NO` records between two `LC 1xx` headers.
- Evidence: MEM 6; AUD 37-64; AUDm 11; UNI 11-22.

**A12 · Changing the meaning of an existing load-case number** (V, review HIGH)
- Symptom: re-running an old SSD task brings back the old meaning and doubles the uplift. It also breaks other tools (the sliding check).
- Rule: **Never give an existing load-case number a new meaning. Add new numbers instead. If a meaning must change, say so in the file header and in the report.**
- Evidence: AUD 202; AUDm 31 ("202-205 now mean G+W+psiQ"); AUD 80 (an exception that is documented).

**A13 · Wind uplift locked to lateral wind (gravity relief in every wind combination)** (V, finding F1 HIGH)
- Rule: **Every wind direction needs one combination family with roof uplift and one with roof downward pressure (26016: 103-118 uplift, 119-130 downward).**
- Evidence: AUD 72.

**A14 · SVAL / section values without units** (V, benchmark)
- Symptom: Iy is read as m⁴, so the section is 10⁸ too stiff. The results are plausible-looking garbage.
- Rule: **Always give units in brackets for section values: `IY 23130[cm4]`.**
- Test RX: `(?i)^\s*SV(AL)?\b.*\b(IY|IZ|IT|CM|A)\s+[\d.]+(?!\s*\[)` → 0 hits. (Percent values like `IT 100[%]` pass.)
- Evidence: BENm 9.

**A15 · Warping switched off with WARP 0 instead of CM 0 on SECT** (V, benchmark first round 13-16 % off)
- Rule: **For a "no warping" case, keep warping on and set CM 0 on the SECT, as the official input does.**
- Evidence: BEN 39-41; BENm 11.

**A16 · ASE MASS load case with area or line loads** (V, error 2430)
- Symptom: `error 2430`.
- Rule: **A MASS load case only converts nodal loads. Solve area and line load cases statically first, then refer to them.**
- Evidence: MEM 42.

**A17 · A MASS load case with FACD or DLZ** (V, error 436)
- Symptom: `error 436`.
- Rule: **A mass LC must not carry FACD or DLZ. Make a separate FACD 0 LC that copies only the area and line loads.**
- Evidence: MEM 43.

**A18 · ASE mesh too coarse for frequencies** (V, BE25 +0.8 to +7.6 %)
- Rule: **Use at least 8-10 beam elements per span (4 per half-wave of the highest mode needed) for ASE dynamics or buckling eigenvalues.**
- Evidence: BEN 33-37; BENm 11; MEM 22.

**A19 · `;` inside a `$` comment** (V, manual caution)
- Rule: **Never put `;` in a `$` comment, because `;` separates records.**
- Test RX: `\$[^\n]*;` → 0 hits (check for false positives inside strings).
- Evidence: BDKm 7.

**A20 · Non-ASCII characters (γ, ψ, °, ±, –, ²)** (V, the server warns; I, SOFiSTiK mis-reads them)
- Symptom: `write_dat_file` returns `warning: The file contains non-ASCII characters ...; saved as UTF-8`.
- Rule: **Write .dat files in pure ASCII: gamma, psi, deg, +/-, -, m2.**
- Test RX: `[^\x00-\x7F]` → 0 hits (26016 files: 0).
- Evidence: SRV 300-302.

**A21 · `+SYS`, `*SYS` or `$(...)` building a record keyword** (V, server refuses)
- Symptom: `status: not run`, "The input contains lines that can make SOFiSTiK run Windows commands …".
- Rule: **Never put `+SYS`, `*SYS`, a bare `SYS` record or a `$(...)` in a record's first word in a .dat sent to the MCP server. Run reports as a separate step (REP stage).**
- Test RX: `(?im)^\s*[+*-]?SYS\b|;\s*[+*]?SYS\b|^\s*\S*\$\(` → 0 hits.
- Evidence: RDM 155-163; SOL 955-959; REPR 63-70 (the report README suggests exactly such a line, see K05).

**A22 · #INCLUDE / +APPLY files that are missing or outside the server's folders** (V, server refuses)
- Symptom: `not run`, "These #INCLUDE / +APPLY files could not be found …" or "… are outside the folders this server may read".
- Rule: **Do not use includes. Concatenate everything into one .dat (the 26016 practice).** If an include is unavoidable, put it next to the .dat.
- Evidence: SOL 948-976; RDM 197-200; CHK2 1-5 (concatenation).

**A23 · BDK: CTRL persists item by item, the LC list is not restated, and restraints carry over** (V, manual + review)
- Symptom: a later member group silently inherits CURV, SWY or COLD settings, or LC selections, from the group before it.
- Rule: **Before every member group, write the full CTRL line (OPT, SCL, CURV, MTHD, BETA, LLT0, TAB, LTB, SWY, SWZ, LCST) followed by the full LC list. Write CVA, CVE and CVL immediately before each MEMB, because restraints apply only to the next MEMB.**
- Test RX (python): every `CTRL OPT` in a BDK block is followed by an `LC (` line within 3 lines; every `MEMB` is preceded by a `CVA` and a `CVE` since the previous `MEMB`.
- Evidence: BDKm 7, 11; BALL §5; CHK2 71298-71330.

**A24 · BDK `CTRL LTB NO`** (V, undocumented)
- Rule: **Do not use `LTB NO`. Use `LTB AUTO`, and check kzy = 0.6 kyy (Table B.1) in the ECHO MEMB FULL output of one hollow member.**
- Evidence: BDKm 11; LTBm 13; BALL 16, 46.

**A25 · BDK LCST number equal to an existing LC, or the same LCST used twice in one run** (V, shipped example says it is an error)
- Rule: **Give LCST a free number (26016: 9100) that is used nowhere else.**
- Evidence: AQBN 146.

**A26 · Joining radial lines drawn in opposite directions with CONT** (V, found in the model)
- Rule: **Before a `MEMB … CONT` chain, check that every SLN in it runs in the same direction. If one does not, check the lines one by one.**
- Evidence: LTBS 154, 185 (the 320 deg radial on L1 and the roof).

**A27 · Members too short for a buckling check (stubs < 0.3 m)** (V)
- Rule: **Leave members under 0.3 m out of BDK, list them in the header, and leave them to AQB.**
- Evidence: BALL 20; LTBm 13.

**A28 · Hard-coded values instead of parameters** (V, Wing's standing rule)
- Rule: **Every load value, factor and switch is a named STO# parameter at the top, with a comment that marks CONFIRM / NEW / [legacy]. No numbers in the load records except geometry.**
- Test RX (smoke): load records such as `AREA … TYPE P[GXYZ]{1,2}\s+[-\d.]+` with a literal number → flag for review.
- Evidence: MEM 6; AUD 101; UNI 31-35.

**A29 · STO# values persist in the CDB** (V, manual; I, risk)
- Symptom: a later program or file sees an old switch value. The BDK detail program deliberately reads its switches from the database.
- Rule: **Restate every switch with STO# in the program that uses it. Do not assume a value from an earlier run has gone away. When you mean a value to be local, use LET#.**
- Evidence: BDKm 7 ("STO# values persist in the CDB and RCL#name reads them back"); CHK2 77172.

### PRE: before pressing run

**P01 · Running a partial file (loads, BDK or AQB) on its own** (V, error 10127 on the sliding check)
- Symptom: `error 10127` (no N_DISP results for LC 1202), or "no results" because the run created a new, empty database named after the .dat.
- Root cause: sps.exe uses `<dat name>.cdb`. A check .dat that has no model goes into a fresh, empty .cdb. The MCP `run_calculation` has no `-cdb:` option.
- Rule: **Put the model, loads, analysis and checks in ONE .dat and run it once (the 26016 v2 practice). Or, on v1.3+, `clone_cdb(model.cdb, "<check name>")` and then run `<check name>.dat`. Never run a loads-only, BDK-only or AQB-only file by itself.**
- Test RX: the file contains `PROG AQUA` and `PROG SOFIMSHC` (or SOFIMSHA) before any `PROG BDK` or `PROG AQB`, **or** a `clone_cdb` was made to exactly `<stem>.cdb`. TOOL: after the run, `cdb_load_cases` lists the combinations BDK asked for.
- Evidence: WINDm 14; LONG 15; RUNLOG 32; IDEA LESSONS 39 ("on its own it makes an empty database"); SRV 553-557 (clone_cdb doc).

**P02 · Starting a run while another run uses the same .cdb, or while the PC is busy** (V)
- Symptom: `CDBASE: WAIT FOR LOCK` (a second Claude session ran be17b at the same time). On v1.2: "Another calculation is still running". On v1.3: "This model is already being calculated" or "Not enough free RAM to start a second calculation".
- Rule: **Before every run, call `dashboard_status` (and `check_cdb_lock` on v1.3). If any SOFiSTiK program is running, do not start. Never run the same .cdb from two sessions. Ask the lead to keep other Claude windows idle.**
- Test TOOL: `dashboard_status` → no running calculation; on v1.3 `check_cdb_lock(cdb).locked == false` and `calculating_here == []`.
- Evidence: BENm 10; LONG 13; RUNLOG 34; MSHm 11; SRV 393-442.

**P03 · A time limit that is too short (the 60 min trap)** (V, run 1 lost about 47 min)
- Symptom: `status: timed out`, "Stopped after 60 minutes …", or a person stopping the run early to beat the limit. Either way a lock is left (R01).
- Root cause: v1.1/v1.2 default 60 min. `timeout_minutes` can only **lower** the settings.json limit (code), and install.bat does not overwrite an existing settings.json.
- Rule: **Before a run, call `sofistik_status` and read `server_version` and `run_timeout_minutes`. If it is a number smaller than 2 × the estimate, STOP and ask the lead (only a settings.json edit by the owner can raise it). Pass `timeout_minutes` = 2 × the estimate only when `run_timeout_minutes` is "no limit".** (The clamp is V in the 1.1.0 and 1.3.0 source; for v1.2.0 it is I. RUNLOG says run 2 got a 360 min limit under v1.2.0, mechanism not recorded.)
- Test TOOL: `sofistik_status().run_timeout_minutes` ∈ {"no limit"} or ≥ 2 × estimate.
- Evidence: RUNLOG 7-9, 31; LONG 11; SRV11 282-284; SRV 330-332; install.bat 47; CHG 27-28.

**P04 · No run-time and RAM estimate** (V, Wing's explicit instruction)
- Rule: **Estimate before every run from the measured table: AQUA + SOFIMSHC + 3 SOFILOAD ≈ 3 min; ASE all LCs ≈ 6 min; MAXIMA ≈ 4 min; BDK ≈ 0.12-0.3 min per member at 47 combinations (227 members in 26 min on a free PC; about 300 members in about 87 min at near-full RAM); CDB ≈ 4 GB; BDK RAM up to about 17 GB. Report the estimate to the lead before starting.**
- Evidence: MEM 7; LONG 12; RUNLOG 17-26; MEM 12, 30; CHG 22-24 (v1.3 dashboard estimate needs one clean earlier run, RDM 224-226).

**P05 · Clean protocol, missing totals line, exit code** (V, settled on the PC)
- Symptom: Haiku sees no "0 errors and 0 warnings" line and thinks the run failed, or sees exit code ≠ 0 and thinks it failed.
- Rule: **Judge a run only by the `status` field: `ok` or `ok with warnings` means it finished. A missing totals line or an undocumented exit code is a note, not a failure.**
- Evidence: RDM 66-67, 201-205; REV 38, 53-56; MSG 159-197.

**P06 · Wrong code basis assumed silently** (V, open item)
- Rule: **State the code basis in the file header and the report: 26016 = EN 1990/1991/1993 + UK NA, ASSUMED (not confirmed). The model keeps NORM 'EN' '199x-200x' COUN 0. UK NA values go in through CTRL, TVAR and parameters. Do not switch NORM to 'BS' without the owner's decision, because that changes factors everywhere.**
- Evidence: MEM 27; AUD 5; LTBS 144; CHK2 15.

**P07 · Writing a .dat that already exists, or one a run is reading** (V, server refuses)
- Symptom: `error: … already exists. Use another name, or overwrite=True`, or "A calculation that reads this file is running …".
- Rule: **Version file names (`_v2`, `_v3`) instead of overwriting. Use `overwrite=True` only for your own file, and only when no run is using it. Never write into the folder of a running calculation until its input check is done.**
- Evidence: SRV 242-281; CHG 37-38.

**P08 · Files on the wrong PC** (V)
- Symptom: a file "not found", or manual tools that return nothing.
- Root cause: the folder tools reach NguyenPC. SOFiSTiK and the MCP server are on NguyenPC3, which has no manual PDFs or example files, and no route copies between the two PCs.
- Rule: **Write .dat files with the sofistik server's own `write_dat_file` (it lands on NguyenPC3). Use `search_manuals` (shipped index), not `read_manual_page`, on NguyenPC3.**
- Evidence: MEM 12-14; MCPm 10, 14.

**P09 · Engineering inputs not yet agreed, presented as fact** (V, open items)
- Rule: **Carry every CONFIRM item into the run log and the report as an assumption: qp 0.766 kPa, roof cpu, balustrade, roof access, ±15 K, RHS cf, hot-finished vs cold-formed hollow sections, BDK restraint switches (JOIN, DXR, DECK …), load height.**
- Evidence: AUD 17-33; LTBm 14, 16; BALL 29.

### RUN

**R01 · Stopping a running calculation (by hand, stop_calculation, a time-out, a restart)** (V, 17 Oct, about 47 min lost)
- Symptom: every later program aborts with `CDBASE: WAIT FOR LOCK ABORTED BY USER`. A file copy of the .cdb is locked as well.
- Root cause: two effects, both recorded. (a) An orphan bdk.exe outlived sps.exe and held the file (LCK 3-6; CHG 29-31). (b) A lock flag is written inside the .cdb (RUNLOG 11, 38). Killing the process does not clear (b).
- Rule: **Never call `stop_calculation`, kill a process or restart the Claude app while a calculation runs. Changing settings mid-run is never a reason to stop. If a run truly must end, ask the lead and the owner first.**
- Test: there is no `stop_calculation` call in Haiku's transcript unless it was explicitly authorised.
- Evidence: RUNLOG 9-11, 30; LONG 10; MEM 45; CHG 29-31.

**R02 · Restarting the Claude app or installing the server during a run** (V)
- Symptom: the run dies, and jobs are forgotten (`No job … Jobs are forgotten when Claude restarts`).
- Rule: **Never restart Claude, run install.bat or upgrade the MCP server while `dashboard_status` shows a running calculation.**
- Evidence: MEM 19-20; MCPm 19; SRV 451; RDM 186-189.

**R03 · Copying a big .cdb as a workaround** (V, 13 min lost, and the copy was locked anyway)
- Rule: **Never copy a .cdb larger than 500 MB through device_bash (about 10 MB/s, 180 s cap per call). Rebuilding is faster. On v1.3, `clone_cdb` copies on the PC, and only an unlocked file.**
- Evidence: RUNLOG 11, 36; LONG 14; SRV 551-640.

**R04 · Treating `status: running` as finished, or re-running** (V, behaviour from the source)
- Symptom: after about 40 s, `{"status":"running","job_id":…,"next":"Still working. Call get_job_result…"}`.
- Rule: **On `running`, keep the job_id and poll with `get_job_result(job_id)` (it waits at most 50 s per call). Never call run_calculation again on the same file. For long runs, poll sparsely (see M02).**
- Evidence: SRV 70, 140-147, 446-452; MCPm 12.

**R05 · Parallel runs when RAM is short** (V: BDK peak; I: risk)
- Rule: **Do not start a second calculation while BDK runs (about 17 GB of 31.5 GB). On v1.3, accept the server's "Not enough free RAM" refusal and wait. Never lower `min_free_ram_gb`.**
- Evidence: MEM 12; RDM 166-170, 227-228; SRV 415-442.

### MON: monitoring

**M01 · Lost connection taken as a dead run** (V, power cut 00:29-01:38Z, the run survived)
- Symptom: Remote Control or tool calls fail, or "Server sofistik unavailable".
- Rule: **A lost connection is not a stopped run. When the connection is back, check `dashboard_status` (or that sps.exe/bdk.exe are alive) before any rerun, lock clearing or file change.**
- Test TOOL: `dashboard_status` → the running module and the elapsed time, before any other action.
- Evidence: MEM 15; RUNLOG 14-15, 35.

**M02 · Monitoring in a way that disturbs the run or burns context** (V: rules; I: polling cost)
- Rule: **Follow progress only with `dashboard_status`, the .cdb modification time, or a count of `[ID n, LC m]` lines in the .lst. Never read the .cdb while it is being calculated (the server refuses: "This .cdb is being calculated right now"). Poll every 5-10 min, not every 50 s.**
- Evidence: RUNLOG 33; LONG 15; SRV 655-658.

**M03 · Run-time estimates that are too low** (V)
- Symptom: BDK past 80 min against an estimate of 35-40 min. The LTB note even said "a run of minutes".
- Rule: **When the run exceeds the estimate, do nothing to the run. Report "slower than estimate" with the elapsed time and the free RAM. Re-base later estimates on the slower figure (near-full RAM slows BDK by 2-3×).**
- Evidence: RUNLOG 15; MEM 30, 45; LTBS 173.

### ERR: messages and recovery

**E01 · `CDBASE: WAIT FOR LOCK ABORTED BY USER`** (V)
- Rule (current): **1) `dashboard_status`: if anything is running on that file, wait. 2) On v1.3, `check_cdb_lock` and then `clear_cdb_lock` (it ends only orphans, then runs SOFiSTiK's Clean Locks `dbinfo.exe <cdb> z`). run_calculation also does this by itself (`auto_clear_cdb_locks`). 3) On v1.2 (no lock tools), ask the owner to run Clean Locks (Teddy: Home > Database Tools > Clean Locks, or right-click the .cdb > SOFiSTiK > Clean Locks), or rebuild under a new file name. Never retry the same file in a loop (two reruns plus one copy lost 20 min).**
- Evidence: RUNLOG 10-11; MEM 21-22; CHG 9-16, 33-36; RDM 171-178; SRV 519-547.

**E02 · `check_cdb_lock` says `locked: false`, and Haiku reads it as "no lock"** (I, from source)
- Root cause: `check()` sees only programs that have the file open. A lock flag stored inside the .cdb is invisible to it and shows only when SOFiSTiK stops with WAIT FOR LOCK.
- Rule: **`locked: false` means only "no program holds it now". A stored lock shows only as WAIT FOR LOCK in a run. Then use `clear_cdb_lock(clean_stored_locks=true)`.**
- Evidence: LCK 226-238; SRV 501-517.

**E03 · `Server sofistik unavailable` together with `9999 INTERNAL ERROR`** (V, cause unknown)
- Rule: **Report it to the lead. The fix is a fresh session, because a new Claude Code process reloads the server. The fallback is `sps.exe -B0` from the shell. Before rerunning, check that the old run is gone and the .cdb is not locked (E01).**
- Evidence: BENm 9.

**E04 · `error 10127` (no results for an LC)** (V)
- Rule: **This usually means the file ran into an empty or wrong database (P01). Check the program list and the .cdb name, then rerun inside the model's database.**
- Evidence: WINDm 14.

**E05 · `error 2430` / `error 436` (ASE MASS)**: see A16 / A17 (V). MEM 42-43.

**E06 · `sps.exe wrote no new .prt protocol, so the calculation did not run`** (V, server message)
- Rule: **Read `reason`. Usual causes: a lock, a bad path, or no active PROG block ("No active PROG / +PROG block found"). Never treat it as a clean run.**
- Evidence: SOL 979, 1118-1119.

**E07 · `status: check: input changed during run`** (V, server)
- Rule: **The results are not trustworthy. Rerun without touching any file in that folder during the run.**
- Evidence: SOL 1124-1129; RDM 184.

**E08 · Fixing an error by guessing syntax** (I)
- Rule: **For every error, read `erg_messages[].input_before` (the 6 input lines before the message), find the record in the manual with `search_manuals` or `search_examples`, change one thing, and record the error number and the fix in the run log.**
- Evidence: SRV 312-316; MSG 92-157; RDM 219-221.

### RES: reading results

**D01 · "No errors" taken as "right"** (V, README warning)
- Rule: **After every analysis, check the reaction sums against hand totals before using any result. 26016: LC 2 SDL ≈ 887 kN; LC 21 lateral 180.5 kN (legacy) or 277.2 kN (new defaults); 102 deck LL is consistent with 6,482 kN at ULS for 151-154.**
- Test TOOL: `cdb_support_reactions(cdb, lc)` sum within 1 % of the hand value.
- Evidence: RDM 219-221; MEM 27; AUD 78, 239; MCPm 10.

**D02 · Reaction sign** (V, settled on the PC)
- Rule: **A reaction is the force of the support on the structure: a +Z load gives pz < 0, so a gravity (−Z) load gives pz > 0. Check the sign against the load direction before quoting.** (26016 load signs: +PG = down, PZP/PZZ negative = down, UNI 37.)
- Evidence: RDM 60-64; MEM 18.

**D03 · Units** (V)
- Rule: **The tools return mm, mrad, kN, kNm, m. Raw .cdb records are SI (m, kN). Utilisations from AQB and BDK are plain ratios, not percent. Watch for factor-1000 errors.**
- Evidence: RDM 57-59, 96; AQBN 84-86; NATF 23.

**D04 · `stale_results_warning` ignored** (V, server feature)
- Rule: **If a cdb_* answer carries `stale_results_warning`, do not use the numbers. Rerun or find the right .cdb.**
- Evidence: SRV 696-716; RDM 205-207.

**D05 · Second-order Mz printed as 0** (V, BE17)
- Rule: **ASE TH2/TH3 forces are in the undeformed element axes. The lateral moment of a twisted section is My·φx, not the printed Mz.**
- Evidence: BEN 32; BENm 8.

**D06 · Eigenmode or MAXIMA cases read as ordinary load cases** (V, server warnings)
- Rule: **Heed the server's warnings that an envelope includes eigenmodes or MAXIMA superposition cases. Never feed MAXIMA cases (4101+) to BDK or AQB.**
- Evidence: REV 22; CHG 87; AQBN 77.

**D07 · Filtering by SLN or group that pulls in the wrong beams** (V, review blocker, fixed)
- Rule: **Prefer group or beam numbers. Use the SLN filter only if the self-test SLN check passed, and read the GDIV/range warning.**
- Evidence: REV 17; RDM 215-216; CHG 86-87; WINDm 13 (group filter fails when GDIV is negative).

**D08 · Large tool answers** (V)
- Rule: **Keep `max_rows` small and filter by group or LC. Big answers land in a file, small ones inline.**
- Evidence: MSHm 11.

**D09 · Benchmark tolerance** (V)
- Rule: **Accept 0-1 % against the manual for statics and buckling. Expect +1 % f1 for 10-element ASE beams and +6-7 % uy for BE17. Never "fix" a model to hit a manual value without checking the manual's own data errors (BE1 E, BE17 grade and bow, BE25 I).**
- Evidence: BEN 26-47.

### MEM: member checks

**C01 · Wrong combinations fed to the checks** (V, HIGH in two reviews)
- Symptom: the checks run only on 101-118, which are all wind-with-uplift cases, so the F1 fix is missed. Or EQU 131-134, SLS, eigen or MAXIMA cases are included.
- Rule: **26016 ULS member checks = 101-130, 135-139, 141-148 and 151-154 (47 calculated cases). Exclude EQU 131-134, SLS 2xx, eigen 2001-2110 and MAXIMA 4101+.**
- Test RX: the BDK and AQB LC records equal exactly `(101 130 1)`, `(135 139 1)`, `(141 148 1)`, `(151 154 1)`.
- Evidence: UNI 24-28; AUD 171-172, 203, 217; CHK2 71300-71305, 77372-77376.

**C02 · BDK or AQB on MAXIMA envelope cases** (V, manual)
- Rule: **BDK and AQB need calculated load cases (ASE/COPY-built). Patterns must exist as real cases (151-154).**
- Evidence: BDKm 7; AQBN 77, 245; LTBS 184.

**C03 · Lcr = L for columns without proving non-sway** (V, the rule; open result)
- Rule: **The BDK column results are valid only if alpha_cr ≥ 10 for every checked case. If 3 ≤ alpha_cr < 10: switch on the TH2 block, rerun the MAXIMA part, and rerun BDK with SWAY 1. If alpha_cr < 3: stop and escalate.**
- Evidence: BALL 30; CHK2 77300-77318; LTBm 13.

**C04 · alpha_cr read from a local mode** (V, design warning; I, likely)
- Rule: **alpha_cr = the lowest positive factor of a GLOBAL (sway) mode. The first factor is often a stair member, an RHS 50×50 landing member or a kingpost shell. Classify each mode before quoting it. If all 20 are local, raise the EIGE count or FIXT the local parts.**
- Test: Haiku's alpha_cr report names the mode number and why it is global. HUMAN check of the mode shape if unsure.
- Evidence: CHK2 77300-77306; BALL 30, 46.

**C05 · Load height ignored for LTB (destabilising top-flange load)** (V, open; benchmark not yet run)
- Symptom: BDK sees the deck loads at the shear centre, so Mcr is 20-30 % too high and the check is unconservative.
- Rule: **Until `26016_ltb_benchmark.dat` proves BDK honours EZA, mark every UB LTB result "load at shear centre, unconservative for top-flange load". Ask for DECK 1 only where the panels really hold the flange. Hand-check the sagging regions with zg = h/2 (report tool `load_position top_flange`).**
- Evidence: LTBS 169-171; BDKm 7 ("No load-height item"); NATF 13, 23; LTBm 11.

**C06 · Restraint switches treated as agreed** (V, Wing has not agreed them)
- Rule: **Run BDK with JOIN 1 and with JOIN 0 and report the larger utilisation, unless twist restraint at every ring crossing is justified. Report the switch values with the results.**
- Evidence: LTBS 167; LTBm 16.

**C07 · Hot-finished vs cold-formed hollow sections** (V, open)
- Rule: **State the assumption (the model has BCY/BCZ 'A' = hot-finished). If cold-formed: change AQUA BCY/BCZ to 'C' (PROF 'RHSC'), rerun the model, and set COLD 1. BDK has no flexural-curve switch.**
- Evidence: BALL 29; LTBm 13; BDKm 11; LEAD 14.

**C08 · AQB taken as a member check, or its ratio compared with our 6.2.9 ratio** (V, manual)
- Rule: **AQB = cross-section 6.2 only, with no LTB. Its STRE C value equals the code check only at 1.0 and differs below it. Compare it only with the cross-section check. AQB writes 107/LC only for LCs typed `(D)` or `COMB … LCST`.**
- Evidence: AQBN 27-51, 132-136, 242-245.

**C09 · BDK per-combination values expected** (V)
- Rule: **BDK stores only the envelope per LCST (127/LCST, `m_scbn`, keyed by design-element ID = SLN). For per-combination values use the ECHO SUM table or separate LCST runs.**
- Evidence: AQBN 144-149.

**C10 · Members or effects BDK does not check** (V)
- Rule: **List as NOT CHECKED: torsion of the r 12 rings from barrier load, treads (plates), stubs < 0.3 m, kingpost shell buckling, connections, SLS. Never show them as PASS.**
- Evidence: BALL 19-22, 48-50; LTBS 177; LEAD 10.

**C11 · AS 4100 / AISC via SOFiSTiK** (V)
- Rule: **SOFiSTiK numbers are EN 1993 only (AQB AS = 1998, AISC = 2005, BDK EN/DIN/BS only). For AS 4100 / AISC 360, label SOFiSTiK values as an EN sanity check.**
- Evidence: AQBN 53-64, 72; NATF 13.

### REP: reports

**T01 · Report run on stale inputs** (V)
- Rule: **Before a report, check that design_params.xlsx sections match the current model (group 25 = UB 457x191x89, not 254x146x43) and that the .cdb is the latest clean run (no stale warning). The earlier B81 1.61 is void.**
- Evidence: MEM 36; LTBS 181; LTBm 18.

**T02 · Report combos typed as 101-118** (V)
- Rule: **Pass the full ULS set (C01). Never type `101-118`.**
- Evidence: AUD 172; REPR 41; AQBN 228.

**T03 · `+SYS py make_report.py` at the end of the .dat** (V, conflict)
- Rule: **Do not add the +SYS line through the MCP server (the run is refused). Run the report as a separate step on the PC after a clean run.**
- Evidence: REPR 63-70; RDM 155-163.

**T04 · Unchecked items shown as PASS, or defaults used silently** (V, lead decision)
- Rule: **N/A, not implemented, cantilever and torsion items = WARN with a reason. Print every default (lengths, load position, fabrication) as an assumption.**
- Evidence: LEAD 8-14; REPR 29-31, 45-46.

**T05 · Load cases not marked ULS** (V)
- Rule: **If the report warns "all load cases checked", rerun with the explicit combination list (C01).**
- Evidence: REPR 132-133.

### ENV: environment, remote and approvals

**X01 · RC refuses downloads, pip or running code on a relayed brief** (V)
- Rule: **Haiku must not try to install or upgrade anything. Only the owner's own typed words in the thread approve a download or install. A decision-card tap does not count.**
- Evidence: MEM 14; MCPm 19.

**X02 · `send_message` to a Remote Control session is refused** (V)
- Rule: **Do not steer an RC session by send_message. Only the owner's messages in that thread steer it.**
- Evidence: BENm 8.

**X03 · Folder-tool or device glitches** (V)
- Rule: **After `device_commit_files`, check the file size (it can push an old synced copy). If folder permission lapses, fall back to a zip in /mnt/project-files.**
- Evidence: MEM 14; MCPm 15.

**X04 · Calling v1.3 tools on a v1.2 server** (I, highly likely given the MEM 19-20 state)
- Rule: **Call `sofistik_status` first. If `server_version` < 1.3.0, do not call `check_cdb_lock`, `clear_cdb_lock` or `clone_cdb`, and expect one run at a time and the 60 min default.**
- Evidence: MEM 19-21; CHG 6-38.

### Optional add-ons (only if the skills include them)

- **W01 Wind tool**: CDB record reading inside CADINP "kept failing", so the Python route `wind_members.py` is preferred. The group filter fails for negative GDIV. The AS/NZS Mz,cat rows were typed from memory, so check them. Never apply drag to every member (that was the cause of the consultant mismatch). Evidence: WINDm 13-17, 22-23.
- **W02 Stairs wind sign**: on inclined flights the wind direction sets the sign of uplift or downward load. Evidence: STAIR 4-13; MEM 31.
- **J01 IDEA**: the SAF export needs `RESU YES` and must run inside the model's database. Select 101-130 + 135-154. SAF values are in IDEA's sign convention (N +, Vy −, Vz −, Mx −, My −, Mz +). IDEA ignores weld start/end, so use DoubleFillet. aiohttp must be installed. The Store python alias breaks `python`. Evidence: IDEAm (lessons 11-17; integration 21); IDEA LESSONS 17-41.
- **S01 Shell meshing**: `CTRL PSUP` default 0 puts a 4-quad macro at point supports (use −1). MCTL REGM needs 4-sided SARs and even, equal SDIV. Evidence: MESHR 17; MSHm 7.

---

## 3. Top 15: likelihood that Haiku hits it × cost

L = likelihood that a small model following skills hits it (1-5). C = cost: PC hours lost or a wrong engineering answer (1-5).

| Rank | ID | Failure | L | C | Score | Why it ranks here |
|---|---|---|---|---|---|---|
| 1 | R01 | Stopping or killing a running calculation leaves a lock in the .cdb | 4 | 5 | 20 | Happened on 17 Oct: 47 min lost, then a full rebuild. A "fix and rerun" instinct makes it likely. |
| 2 | P03 | Time limit too short: 60 min default, `timeout_minutes` can only lower it, settings.json survives upgrades | 4 | 5 | 20 | The 26016 chain is 90+ min. A timeout kills the run, which produces R01. |
| 3 | M01 | Lost connection, or a `running` status, read as a dead run, then rerun or lock-clear on a live .cdb | 4 | 5 | 20 | The power cut on 18 Oct. A rerun collides with the live run. |
| 4 | C01 | Wrong combination set (101-118 only, or EQU/SLS/MAXIMA included) | 4 | 5 | 20 | Two HIGH review findings. Every downstream tool defaulted to 101-118. |
| 5 | C03/C04 | Lcr = L accepted without alpha_cr ≥ 10, or alpha_cr read from a local mode | 4 | 5 | 20 | Unconservative column design. The first mode is very likely a local stair or kingpost mode. |
| 6 | P01 | A partial .dat (loads, BDK, AQB) run on its own goes into an empty database | 4 | 4 | 16 | Error 10127 seen. Teddy-style instructions ("run inside the project") do not translate to sps.exe. |
| 7 | A23 | BDK CTRL, LC and restraint carry-over between member groups | 4 | 4 | 16 | The silent wrong-curve or wrong-LC risk was caught only by review. |
| 8 | D01 | "Status ok" taken as a correct model; no reaction-sum check | 4 | 4 | 16 | The README warns. A small model stops at "0 errors". |
| 9 | P04/M03 | No or too-low run-time/RAM estimate (BDK 35-40 min estimated, 90+ min real at full RAM) | 4 | 4 | 16 | Wing's explicit rule. A bad estimate drives R01 and P03. |
| 10 | A11 | A load counted twice (LC NO −1, action building blocks, QF + QB, COPY LC 1, two wind directions) | 3 | 5 | 15 | Wing's top input rule. Wrong engineering with no error message. |
| 11 | C05 | LTB load height ignored (Mcr 20-30 % high) | 3 | 5 | 15 | Unverified BDK behaviour. A small model will report utilisations as final. |
| 12 | P02 | A second session or run on the same .cdb, or starting while the PC is busy | 3 | 4 | 12 | Happened with BE17 (a second Claude window). |
| 13 | A01/A02 | List > 25 values, or line > 255 characters | 4 | 3 | 12 | Would have broken the v1 BDK file. A cheap regex prevents it. |
| 14 | A04 | An expression in COPY FACT/NO | 3 | 4 | 12 | Wrong factors without an error. Caught only by the designer's re-read. |
| 15 | E01/E02/X04 | Wrong lock recovery: retry loop, copying the .cdb, trusting `locked:false`, calling v1.3 tools on v1.2 | 3 | 4 | 12 | Two reruns and a copy cost 20 min on 17 Oct. The tool version on the PC is v1.2. |

Just outside the top 15: A14 SVAL units (2×5), A20 non-ASCII (3×2), T01 stale report params (3×4), C07 hot/cold (3×4), D04 stale results (3×4), R02 restart during a run (2×5).

---

## 4. Conflicts between sources (which one is current)

| # | Topic | Older or other source says | Newer source says | Current, with evidence |
|---|---|---|---|---|
| K01 | Recovering from a .cdb lock | LONG 10 and RUNLOG 30, 36: "the only recovery is a full rebuild under a new file name" | MEM 21-22, 45 (01:42Z): SOFiSTiK Clean Locks, confirmed by Wing, "rather than rebuilding". CHG 9-16 (1.3.0): `clear_cdb_lock` + auto Clean Locks | **Clean Locks is the current method.** But the tool exists only in v1.3.0, which was not installed as of 01:42Z (MEM 20). Today: v1.3 → `clear_cdb_lock`; v1.2 → the owner runs Clean Locks by hand, or rebuild. |
| K02 | Cause of the lock | LCK 3-6 (docstring): an orphan BDK kept the .cdb open | RUNLOG 11, 38 and MEM 21: a flag stored inside the .cdb (a copy is locked too) | **Both.** CHG 9-16, 29-31 handles orphan first, then the stored flag. Implication: `check_cdb_lock.locked=false` does not rule out a stored flag (E02). |
| K03 | Time limit | LONG 11 and RUNLOG 31: "always pass timeout_minutes above the estimate" | CHG 27: no limit by default in 1.3.0 | **Neither rule is safe alone.** In the 1.1.0 and 1.3.0 code, `timeout_minutes` can only lower the settings.json value (SRV11 282-284, SRV 330-332), and install.bat keeps an existing settings.json (line 47), which may still say 60. Check `sofistik_status.run_timeout_minutes` (P03). |
| K04 | Parallel runs | LONG 13, MEM 19 and MSHm 11: one calculation at a time | CHG 17-21 (1.3.0): up to 2, with a RAM gate | **One at a time** while v1.2.0 is loaded (MEM 20-21). Even on v1.3, a BDK run leaves no RAM for a second one (RDM 169-170). |
| K05 | Report hook | REPR 63-70 and AQBN 215-235: add `+SYS py make_report.py …` at the end of the .dat | RDM 155-163: `allow_sys_commands` false refuses any .dat with +SYS | **The MCP refusal wins** for any run through the server. Run the report separately. |
| K06 | Combinations for downstream tools | REPR 41 example, AQBN 228, IDEA LESSONS 39 and IDEAm loads line: 101-118 | AUD 171-172 and UNI 24-28 (16 Oct): 101-130 + 135-154. AUDm 43 | **101-130, 135-154** (EQU 131-134 excluded from member checks). |
| K07 | MAXIMA result numbers | TPL 17-25: BASE 2100-3300 | AUD 46, AUDm 32 and UNI 23: 4101+; eigen modes use 2001-2110 | **4101+ for 26016.** The template numbering clashes with this project's eigen cases. |
| K08 | Combination factors | TPL 46-55 defaults: EN recommended (ψ0,W 0.6, ξ 0.85, NORM EN) | AUD 81 and UNI parameters: UK NA (ψ0,W 0.5) | **UK NA assumed** for 26016 (unconfirmed, MEM 27). The template must be switched to its UK-NA comments if used. |
| K09 | BDK run time | LTBS 173: "expect a run of minutes"; LONG 12: 35-40 min | MEM 45 and RUNLOG 15: "well over 80 min", about 300 members after about 87 min | **Plan for 90-120 min** for 311 members × 47 combinations on NguyenPC3 with RAM near full. |
| K10 | How cloud threads reach SOFiSTiK | MEM 24: "only through RC + this server" | MCPm 17 (2026-10-18): `mcp__remote-devices__sofistik__*` via the desktop app, no RC needed | **The direct remote-devices tools** (newer, confirmed by the meshing thread). |
| K11 | Number of tools | MCPm 12: 22; CHG 50 and MCPm 19: 24 | RDM 46 and SRV: 27 | **24 on the PC now (v1.2.0); 27 after the v1.3.0 install.** |
| K12 | Patterns file | LTBm 11: 26016_ltb_patterns.dat makes 151-154 | LTBm 12, AUD 174 and AUDm 30: folded into the unified file, superseded | **Do not run 26016_ltb_patterns.dat.** |
| K13 | BDK input file | 26016_ltb_bdk.dat (UB only) | BALL 3 and LTBm 13: 26016_buckling_all_bdk.dat supersedes it | **buckling_all_bdk**, now inside 26016_check_v2.dat. |
| K14 | Switch name | LTBS 163: `NDIV` | LTBm 13 and CHK2 71290: `NPART` | **NPART** (DIV is an operator). |
| K15 | BE17 status | BENm 8: "needs rerun" | BENm 11 and BEN 29: all 5 pass | **Pass** (uy +6-7 % explained as mesh). |
| K16 | Run instructions | AUD 180 and UNI 4: "run in Teddy INSIDE the 26016 project" | RUNLOG 32 and LONG 15: one concatenated .dat via MCP | **Concatenate into one .dat** for automated runs (P01). The Teddy instructions apply only to the owner working by hand. |
| K17 | Memory cross-reference | LONG 17 links [[project-26016-member-check]] | No such memory file exists in /tmp/claude/memory/team/silo/ | **Gap.** RUNLOG.md is the only record of the member-check run. |
| K18 | Settings changes | RDM 149: "then restart Claude" | SRV 114-115: `load_settings()` is called on every tool call | **I:** settings.json edits probably take effect without a restart. Follow the README (restart) unless a run is live, because a restart kills runs (R02). |

---

## 5. A preflight bundle the skills can carry (machine checks)

Run these on the .dat text before `write_dat_file`. Every one must pass. (They are all proven to give 0 hits on
the current 26016 files: UNI, the BDK and alpha_cr files, CHK2.)

```
non_ascii       [^\x00-\x7F]                                              -> 0   (A20)
long_line       any line longer than 255 chars                            -> 0   (A02)
long_list       ^\s*\w+\s+[^$!\n]*?(\d+\s*,\s*){20,}                      -> 0   (A01)
operator_name   (?i)(STO|LET|DEL|RCL)#\w*(DIV|SIN|COS|TAN|SQR)\w*         -> 0   (A03)
copy_expr       (?i)^\s*COPY\b.*FACT\s+#\w+\s*[-+*/(]                     -> 0   (A04)
imp_type        (?i)\bTYPE\s+'?IMP                                        -> 0   (A05)
quad_dt         (?i)\bQUAD\b.*\bTYPE\s+DT\b                               -> 0   (A06)
lc_no_minus1    (?im)^(?![!$]).*\bLC\s+NO\s+-1\b                          -> 0   (A09)
sys_cmd         (?im)^\s*[+*-]?SYS\b|^\s*\S*\$\(                          -> 0   (A21)
semicolon_cmt   \$[^\n'"]*;                                               -> 0   (A19)
include         (?im)^\s*(#INCLUDE|\+APPLY|APPL)\b                        -> 0   (A22)
has_model       PROG AQUA and PROG SOFIMSH[AC] appear before PROG BDK|AQB   (P01)
bdk_ctrl_lc     every 'CTRL OPT' in BDK followed by 'LC (' within 3 lines  (A23)
uls_set         BDK/AQB LC records == (101 130 1),(135 139 1),(141 148 1),(151 154 1)  (C01, 26016)
```

Tool-call preflight (in order): `sofistik_status` (version, run_timeout_minutes) → `dashboard_status` (nothing
running, free RAM) → [v1.3] `check_cdb_lock` → estimate time and RAM → report the estimate to the lead → `run_calculation`.

## 6. What is still unknown (do not let Haiku "decide" these)

- Whether BDK honours a load eccentricity (EZA). The benchmark has never been run (LTBm 11).
- Which Annex B table BDK picks with LTB AUTO for hollow sections (BALL 46).
- The layout of the ASE buckling-factor table, and alpha_cr for 26016 (BALL 46).
- The exact CADINP comma-list limit ("about 25", BDKm 7).
- How v1.2.0 handled `timeout_minutes` > 60 (RUNLOG 12 says 360 min worked; the code that did it is not on file).
- Whether run 2 (26016_check_v2) finished cleanly. The last record is 01:41Z, still in BDK (RUNLOG 15).
- The cause of `9999 INTERNAL ERROR` (BENm 9).
- AQB `m_class` encoding, and whether `m_tcf` includes the c/t criterion (AQBN 138-142).
