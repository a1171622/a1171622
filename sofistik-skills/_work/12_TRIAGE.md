# Lead's triage of reviews A, B and the Haiku exam (2026-10-18)
Lead verified: A-01 (member_check.py:555-573 ignores hand 6.3 when eta_bdk is null) and A-02 (combo_check.py:75-77 skips combos with own loads) by reading the code; F-EX1 by server.py:446-451.
ALL BLOCKER and MAJOR findings are accepted. Minors accepted unless noted. Owners: D1 = author + run-and-fix skills, D2 = results-proof skill, T = tools.

## Cross-cutting rules (binding on all three skills; D1 owns the wording, D2 copies it verbatim)
L1 Ledger = W/LEDGER.md (one name, all skills). Step line: `<UTC ISO> | <state> | <EVENT> | <detail> | next=<state>`.
   EVENT in {READ, INTENT, RESULT, PASS, FAIL, ESCALATE, STOP <code>, PREDICT, CLASSIFY, NOTE}.
   A STOP is the LAST line a skill writes; then the HANDBACK block (fixed format, same in all three). Header `next_state:` updated at the end of EVERY state.
   Resume: S0 reads the last line; `STOP` -> do nothing until the brief carries `resume: <state> because <lead reason>`; INTENT without RESULT -> the resume table of that state.
L2 Dashboard: report_check status after any STOP = "attention" in all three skills.
L3 Busy PC (F-EX1/B04): STOP S-BUSY at once, with the running job, its start and the estimated finish. No waiting loops. The lead schedules the retry.
L4 Truncation (F-EX3/B12): rows returned == max_rows, or read_text_file returning max_lines, counts as TRUNCATED even with no flag.
L5 member_lcs (F-EX4/B11/A-19): no skill ever rewrites it. If the brief's set differs from the reference set for the project -> STOP S-CONFIRM in author; results-proof checks every LC it reads against member_lcs and FAILs on 131-134 / SLS / eigen / 4101+.
L6 "No job" after a server restart (B13): same rule in both skills: check dashboard_status (running?), then the run's .cdb/.prt modification time and the protocol end marker; finished -> treat as finished and read the protocol; unknown -> STOP S-LOST.
L7 Big files (B01/B05): the run .dat is a SMALL master file Haiku writes in full (<= 400 lines): parameters, `#INCLUDE` of approved files already on the PC (exact paths in the brief), the run-identity stamp. After writing: read the whole master back and compare line by line with the cloud copy; for each included file compare line count + first/last 20 lines + 3 random 20-line windows with the cloud copy. Any mismatch -> STOP S-TRANSFER.
L8 Timeout (B03): never pass timeout_minutes on project runs. Gate: settings run_timeout_minutes must be 0 or >= 2x estimate, else STOP S-TIMEOUT.
L9 Server lifetime (B02): new calibration item SERVER_LIFETIME. Until calibration.json says PERSISTENT, any run with estimate > 10 min -> STOP S-CALIB (the lead runs it). Calibration test: short canary run, end the agent, a new agent calls get_job_result(job_id) and dashboard_status.
L10 Hand-saved results (B06): never hand-type more than ~200 rows / ~20 KB into one file; narrow the request instead. Receipts are audited by the LEAD re-calling the MCP tool (not by reading Haiku's copy); receipts carry a JSON path (A-18). Recommendation to Wing: MCP 1.4 export-to-file + PC-side proof tool.
L11 Short runs with no job_id (B07): ledger job_id = "inline".
L12 NEVER list addition: never edit tools/calibration.json or pass --calibration (A-16); NEVER-1 clarified: Haiku never stops or kills anything itself; the server's automatic orphan clean-up inside run_calculation is allowed (B26).

## Tools (T)
A-01 hand 6.3 governs when eta_bdk missing (ESCALATE > 0.9, FAIL > 1.1, never PASS without it). A-02 mixed combos: predict COPY sum + own load totals or ESCALATE, and the note must not claim G4 proves them.
A-03 deck/roof beams: use max(shear-centre, top-flange) until the LTB benchmark is calibrated. A-04 AQB-only members need a reason per group, else ESCALATE.
A-05 add an EN 1990 + UK NA gamma/psi factor table check for combos (combo_factors in combo_check); self-equilibrating LCs -> ESCALATE "not proven by reactions" (no C4 implementation in v1).
A-06 per-component reference: PASS <= 0.1 % of that component's applied total + 0.05 kN; else FAIL above 1 %, ESCALATE between.
A-07 measure elements per member span from the beam map; < 8 -> alpha_cr NOT PROVEN.
A-09 scorecard: RED if any pick not hand-checked or any member > 1.0. A-17/B09: scorecard --ledger arg, case-insensitive; LC 1 self-weight: compare to the model's volume x density when available, else note (not a default ESCALATE).
A-10 holding-down: read gravity direction from the LC 1 reaction sign, not an assumed Z up.
A-13, A-14, A-18, A-22 (CANNOT_RUN must not outrank FAIL; not-hand-checkable consistent with skill), A-23 (>= 5 members, different governing checks), A-24 (canary also checks cdb_load_cases reaction sum).
B15 mutation_drill: --expected support, and say it needs timeout 300000 in Bash.
Add a test for every fault injection in reviewer A's FI-1..FI-5 and keep all 28 old tests green.

## D2 results-proof
B07, B08 (L1), B10/A-15 (cdb_read_key allowed; page cap raised to fit AQB 47 LCs or STOP S-PAGECAP), B13 (L6), B16 (scan message text only), B17 (route > 200 messages: read protocol by pages), B18, B20, B22 (L2), A-07, A-08 (name the 6 primary cases with alpha_cr), A-10, A-11 (rewrite FOR WING: only what was proven; list unchecked items incl. EQU holding down, members with no buckling check, self-weight route; add a STOP version), A-12, A-21, A-22, F-EX2 (pick every member >= 0.9).

## D1 author + run-and-fix
L1-L12 wording, B03, B04, B05, B12 (run_history tail), B14 (resume after write RESULT), B19, B21 (define fix_count format, reset gate_waits), B23 (RAM gate from run_history peak, not a fixed 21 GB), B24 (resume row), B25 (note), A-19 (L5), A-20 (remove the TH2 block from Haiku's templates: TH2 is the lead's call).
