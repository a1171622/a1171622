# 15 Final check (independent, adversarial), 18 Oct 2026
Scope: the three SKILL.md files, tools/ (README, calibration.json, scripts, tests), 13_SHARED_BLOCKS.md, 14_TRIAGE2.md,
and the reviewers' "Re-verification" sections. Nothing in the project was edited. SOFiSTiK was not started.
Dry runs used a scratch W (copy of 26016_check_v2.dat, my own expected.json from make_expected_26016.py).
AUTH = sofistik-cadinp-author/SKILL.md, RUN = sofistik-run-and-fix/SKILL.md, RES = sofistik-results-proof/SKILL.md.

## Verdict list
- **MAJOR F1 - the scorecard is RED on every real run (three independent false-RED causes, shown by running scorecard.py).**
  (a) scorecard.py:33-35 requires a proof line with tool `G6_alpha_cr`, but member_check.py:132 writes tool
  `member_check_alpha` (G6_alpha_cr is only a check id inside it) and RES writes no P-PROOF for G6. Result: "RED:
  mandatory gate G6_alpha_cr missing", even when every gate PASSes.
  (b) scorecard.py:165-173 ("same inputs everywhere"): dat_lint (AUTH S2 step 5, RUN S3 step 1) records the sha of M
  (dat_lint.py:222), while mutation_drill / combo_check / coverage_census / collect record the sha of X. All of them
  append to the same W/proofs.jsonl, so the scorecard says "RED: proofs used different versions of the dat file:
  [['dat_lint'], ['mutation_drill']]". Reproduced on the dry-run W.
  (c) The same rule for role `load_cases`: member_check alpha records W/raw/buckling_lcs.json (RES:292-293) and
  equilibrium/combo/holding_down record W/raw/load_cases.json, so these are different shas and the scorecard is RED again.
  The tests miss it because test_receipts_scorecard.py:51 builds synthetic lines with tool "G6_alpha_cr", and the
  mutation drill scorecard cases are synthetic too. It fails safe (no false GREEN), but S8 always reports "failed" to the
  dashboard and to Wing.
- **MAJOR F2 - S7b dead-ends after calibration because of the README's static status line.** RES:309 says "Read
  T/README.md section `member results` ... Its status must be CALIBRATED", and RES:323 says "section status
  UNCALIBRATED -> STOP S7-UNCALIBRATED". README.md:478 says `**Status: UNCALIBRATED.**`, and nothing tells the lead to
  edit the README (calibration.json `_comment` and README:479 mention only calibration.json). A literal model STOPs
  S7-UNCALIBRATED even when calibration.json is CALIBRATED. Fix: take the status from calibration.json (as RUN S3
  step 8 does), or tell the lead to edit both.
- **MAJOR F3 - the 26016 happy path cannot reach S9.** RES:310-313: with P = 10 the READS estimate for 26016 is in the
  thousands (AQB, README.md:649-653), so the result is STOP S7-NEEDS-EXPORT "by design". S7c, S8 (holding-down, deflection,
  receipts audit, scorecard) and the normal S9 hand-back never run, and no `resume:` route past S7b is defined
  (RES:417-420 lists none for S7-NEEDS-EXPORT). This is documented, but the deliverable for 26016 stops at G0-G6.
  README.md:654 says something different ("collect AQB for a few LCs and ESCALATE the rest", and S-PAGECAP at :651).
- No BLOCKER found. No path stops or kills a project run, restarts Claude, clears a lock on a live run, deletes or
  copies a .cdb, edits calibration.json, or changes an engineering input (section 5).
- MINOR items: section 6.

## 1. Round-2 items (14_TRIAGE2.md)
| Item | Status | Evidence |
|---|---|---|
| T N-01 intended factor | DONE | combo_check.py:34-40 and 184-225. The G factor in the title must equal FACD and the COPY G factors. Intended per-combination factors come from expected.json `combination_factors` (make_expected_26016.py:144-166; present in my generated file). test_FI6_* pass: C4_107-110 and C4_131-134 FAIL; the clean check_v2 gives 74/74 C4 PASS with intended_compared |
| T N-02 hand-only all LCs | DONE | member_check.py:681-698. PASS only when all_lcs, else ESCALATE "give --extra-forces for all member LCs". test_FI7 passes |
| T mesh compression default | DONE | member_check.py:710-751 (compression from --compression-forces, else from the beam map's own N; neither -> None -> ESCALATE fail closed, :756-758). test_mesh_compression_default_and_fail_closed passes |
| T N7 lifetime doc | DONE | README.md:611-617; calibration.json server_lifetime.how ("60-120 s", WAIT_S 40, BE25c / looped canary) |
| D1 N1 OVERLAP | DONE | AUTH:151 prints `NONE` / `OVERLAP [..]`; AUTH:178 matches `OVERLAP [`. Ran it: `NONE` for the 26016 set, `OVERLAP [131]` for 101-131 |
| D1 N2 protocol answer in S5 | DONE | RUN:243-245, 248, 253, 255 (`programs` count, `-` for missing fields, no time ratio) |
| D1 N3 canary before S-CALIB | DONE | RUN:192, 195 |
| D1 N4 resume after the write | DONE | AUTH:202-203 (overwrite=true only with this run_id's own RESULT; .bak kept, server.py:285-289); AUTH:214-215 (pc sizes always re-measured) |
| D1 N8 new-ledger line | DONE | AUTH:117 `... READ | new ledger | next=S1`; Block C "anything else" row verbatim (AUTH:132) |
| D1 N9 stale marker | DONE | RUN:78-81 (Block E), RUN:186, RUN:336; RES:76-79, 198 |
| D1 N10 | DONE | RUN:158 (path passed as argv). README.md:630 still has the old literal `T/` form (MINOR m7) |
| D1 N11 | DONE | RUN:241 (`calc-xxxxxxxx`; matches server.py:119 `f"{kind}-{uuid...[:8]}"`) |
| D1 N12 | DONE | RUN:218, 324-325 |
| D1 N13 | DONE | AUTH:204; RUN:153 |
| D1 shared blocks | DONE | 13_SHARED_BLOCKS.md:2-3 and 139-144; C identical in all three (section 3) |
| D1 N14 | DONE | AUTH:165 |
| D2 N5 | DONE | RES:156-157 |
| D2 N3 side | DONE | RES:417-419 |
| D2 N6 | DONE | RES:288-290 (windows of 60, max_rows 121, `WINDOWS` > 40 -> S7-NEEDS-EXPORT); RES:310-313 (READS estimate, > 300 -> S7-NEEDS-EXPORT) |
| D2 A-11 sentence | DONE | RES:424, exact wording |
| D2 N-02 skill side | DONE | RES:340-342: step 2c fires on exit 2 with `all_member_lcs_checked` false, which is what member_check.py:659 and 688-698 emit |
| D2 mesh align | DONE | RES:294 |

All 21 items are DONE. Nothing is PARTLY or NOT DONE.

## 2. Test suite
`python3 -I /mnt/project-files/skills/tools/tests/run_tests.py` -> **55 passed, 0 failed, 0 skipped** (FI-4 to FI-7 included).
calibration.json mtime is unchanged (03:43:18).

## 3. Mechanical checks
- **MCP tools and parameters:** a script read every `@mcp.tool()` signature in server.py and every `name(param=...)`
  call in the three skills. Every tool and every parameter exists. No skill calls stop_calculation, clear_cdb_lock or
  clone_cdb; they are named only in the NEVER lists. RES calls write_dat_file / run_calculation nowhere. Return fields
  the skills rely on also exist: `job_id`/`elapsed_s` (server.py:146), `total_lines`/`to_line`/`text` (:238-239),
  `files[].modified/size_kb` (:210-211), `record_count` (results.py:664), `programs_in_input` (solver.py:1141),
  `left_running` (solver.py:1098), `finished`/`unfinished_programs` (messages.py:155, 181), `resources.ram_*`,
  `processes.module`, `servers[].jobs`, `status_folder` (dashboard.py:495, 540, 694-696), `element_code/min_element/max_element`
  (results.py:220).
- **Script CLIs:** every script was run with `--help`. Every invocation in the skills matches its argparse (positional
  order, `--sources --uls`, `--expected`, `--families`, `--sw-lc`, `--ledger`, `receipts add --path`, `member_check
  alpha --buckling-lcs --beam-map --dat`, `pick --seed`, `hand --member --lc --extra-forces`, and the required
  `--workdir` of mutation_drill and member_check). All inline one-liners were executed: S1 overlap, S3 lifetime and gate
  numbers, S2 windows, P-GROUPS, S6b LC list, S7a windows, S7b READS. All work.
- **Shared blocks (diff script):** A, B, C, D are verbatim in all three skills. E, F, G, H are verbatim in RUN and RES and
  absent from AUTH, as 13_SHARED_BLOCKS.md:2-3 states. One cosmetic difference: in RES:167 the first line of C shares its
  line with the label `**Table S0-A (resume).**` (same text). RUN:73 and RES:71 still title E-H "same text in all three
  skills", which is no longer true (MINOR m6).

## 4. Happy-path walk, 26016 (literal small model)
**Author S0-S2 (dry-run with the real file):** the template plus the `next=S1` READ line, then S1 (ran steps 3-6: 20
CONFIRM lines, TH2 grep empty, `NONE`), then S2. expand_master gives `EXPANDED 77389`. Gotchas: only the known `semi`
hits at the documented lines +3; `lc9990` = 1; `MODEL-OK`. dat_lint exit 0 in 5 s. Simulated PC read-backs (master page
plus 5 windows of the seeded set) gave TRANSFER_OK; master 11 lines compared >= `wc -l` 10. Window 10b gives
`total_lines` = N+1, which the table allows. No dead end. Information the lead must supply: the expected_json path (who runs
make_expected_26016.py is implied, not stated; m3), and 26016_check_v2.dat already in pc_folder (S-TRANSFER otherwise, a
known limit).

**Run S0-S5 (LIFETIME CALIBRATED PERSISTENT, PC free):**
- S3 passes only if the brief gives `run_approved: yes` and `max_minutes` >= 161, and settings `run_timeout_minutes` is 0
  or >= 322. RUN_LOG says the default limit was 60 min, so S-TIMEOUT is likely until Wing edits settings.json. That stop
  is correct, but it is a precondition nobody in the pipeline sets.
- RAM: table E gives 17 + 4 GB on a 32 GB PC. It passes only with 21 GB free. The run_history read probably fails
  (status_folder is outside read_folders), so table E is used.
- Canary after PASS, then S4. The poll loop is capped at 200 polls x 50 s = 167 min, or 100 min after a relay timeout
  (30 s). RUN_LOG measured BDK at 201 members in 100 min, so the full chain is about 190 min or more. **Expect STOP
  S-POLLCAP** and a lead resume (`resume: S4 because poll job_id`). That is a designed hand-off, not a dead end (m1).
- S5: `programs_in_input` = 16 = `grep -ciE '^\s*[+]?PROG\s' X` (checked: 15 in the source plus the stamp; `-PROG` lines
  are excluded on both sides). Stamp title `RUNID 26016checkv3-10180902-a1` is 30 characters (<= 32). OK.
- `programs_expected` is not a header key. On a resumed S5 it lives only in the S4 PREDICT line (m4).

**Results S0-S9 (calibration assumed done):**
- S0 canary, S6a, S6b (7 cdb_load_cases calls of <= 40 LCs), S6c, S6d (the mutation drill on the real X took 130 s,
  under the 300 s Bash limit; exit 0), S6e (10 envelope calls) and S7a all walk cleanly.
- Risk in S6a: if the run has more than 200 warnings (BDK often warns per member), `messages_truncated` sends the model
  to Route PRT, which hand-saves the whole .prt in 200-line pages (cap 150 pages). A 26016 .prt is very likely longer,
  so this ends in S-PAGECAP. The P-SAVE subset of 200 messages also exceeds the 20 KB hand-type NEVER (m2).
- S7a: `WINDOWS` depends on the beam count (about 1,000-1,500 beams in 18 groups, so 20-45 windows). It may hit the
  40-window cap. Not measured (m5).
- **S7b: STOP S7-UNCALIBRATED from the README status line (F2). Even with that fixed, STOP S7-NEEDS-EXPORT (F3).** S7c,
  S8 and S9 are unreachable on 26016.
- If S8 were reached, the scorecard would be RED (F1).
- RES S0-A row "INTENT with no RESULT" sends the model to "the resume table of the state named". For an S3-S5 INTENT
  left by run-and-fix, RES has no such table and no fallback row (m8).

## 5. Dangerous paths
- Stop or kill a run: none in the skills. stop_calculation / clear_cdb_lock / clone_cdb appear only in NEVER lists.
  Residuals:
  - The canary's `timeout_minutes=10` (RUN:198) lets the server kill a hung canary. It is the skill's own throw-away
    .cdb in `_canary`.
  - settings `run_timeout_minutes` kills a project run at its limit. The gate requires >= 2 x estimate, but table E's BDK
    120 min underestimates RUN_LOG (about 155 min for 311 members). Recommend "no limit" for 26016.
  - `auto_clear_cdb_locks` (RUN:184) lets the server end processes it classifies as orphan. This is the documented,
    allowed exception, and S3 step 6 (Busy PC) stops first if any sps.exe runs.
- Server answers that suggest a forbidden action ("stop it with stop_calculation" server.py:401, "restart Claude"
  config.py:196, "clear_cdb_lock ends it" cdblock.py:222) are all routed to STOP rows (RUN NR table, S2/F10 write rows,
  S3 lock rows). No table row follows the advice.
- Restart Claude / settings.json: forbidden in all three. Only STOP rows mention it.
- .cdb delete or copy: none. Cloud-only deletes: AUTH:137 (M, X in W), AUTH:204 / RUN:153 (W/raw/xfer pages),
  mutation_drill.py:104 (W/mutants). The PC .dat is overwritten only in AUTH:202-203 (same master, own RESULT, .bak kept)
  and RUN:295 (F11, own master, after the run ended). The server refuses both while a run reads the file
  (server.py:258-266).
- calibration.json: no tool writes it (grep). member_check refuses `--calibration` without TOOLS_TEST (member_check.py:877-881).
  The mutation drill does not use it. The test run left it unchanged.
- Engineering inputs: AUTH M1 only with value and decider and no source hit; RUN table ENG / K7 proof / F6. Edge case: a
  lead `resume: S2` after an F-fix rebuilds M from the brief (AUTH S2 step 2: original #INCLUDE, attempt 1). That
  silently drops the fix. It fails closed at RUN S3 S-STAMP (attempt mismatch), but the PC master is overwritten with
  the pre-fix master (overwrite=true, .bak kept) (m9).

## 6. MINOR
- m1 26016 run likely ends in S-POLLCAP (200 x 50 s < about 190 min); table E BDK 120 min is optimistic against RUN_LOG.
- m2 RES Route PRT and the 200-message P-SAVE subset conflict with the 20 KB hand-type rule on a warning-heavy run.
- m3 Who produces expected.json (make_expected_26016.py) is not stated in AUTH S1-A; the run_id needs `date -u +%m%d%H%M`,
  but no Bash line gives it.
- m4 `programs_expected` is not a header key (needed by a resumed S5).
- m5 S7a `WINDOWS > 40` is not measured on 26016. S7b's "P = 500 if the harness saves results to files" cannot be known
  before the call.
- m6 RUN:73 / RES:71 headings "same text in all three skills" (AUTH has no E-H). RES:167 label merged with Block C's first line.
- m7 README.md:630 keeps the literal `T/calibration.json` inside the Python string (fixed in RUN:158). README.md:649-654
  contradicts RES S7b (ESCALATE vs STOP S7-NEEDS-EXPORT, S-PAGECAP vs S7-NEEDS-EXPORT).
- m8 RES S0-A "INTENT without RESULT" row has no fallback for a sibling skill's INTENT. AUTH S2 resume falls to
  S-UNKNOWN, which is fine. A canary crash leaves `INTENT run_calculation` that RUN's resume table treats as the
  project run (Rule NJ, then S-LOST): fails closed, but the cause is misleading.
- m9 A resume into AUTH S2 after a RUN fix rebuilds the pre-fix master (see section 5).
- m10 S5 HARDWARN is scanned by eye over up to 200 messages in RUN; RES uses a script (RES:191).
