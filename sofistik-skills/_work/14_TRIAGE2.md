# Lead's triage, round 2 (re-verification by reviewers A and B), 2026-10-18
All MAJOR findings accepted. Owners: T tools, D1 author+run, D2 results.

T:
- N-01: combo_check factor check must test the INTENDED factor, not set membership: in uplift (G favourable) and EQU combos the G factor must be the favourable value (STR 1.0, EQU 0.9; UK NA). Add expected per-combo factors where the generator knows them; FI-6 (scratchpad/fi6) must FAIL. Test.
- N-02: member_check hand, AQB-only branch: PASS only when ALL member LCs were hand-checked; otherwise ESCALATE "give --extra-forces". FI-7 (scratchpad/fi7) must not PASS. Test.
- Mesh check: default to members in compression (use forces when given) so the 0.66-1.04 m ring chords in bending do not block forever; still fail closed when no forces are given.
- N7 doc: the server-lifetime test needs a run longer than ~60 s so run_calculation returns a job_id (e.g. BE25c 40-element eigen or a looped canary); say so in README + calibration.json "how".

D1:
- N1 OVERLAP NONE match; N2 S5 must accept a result recovered from read_calculation_messages (no programs_in_input/seconds) -> classify from messages; N3 canary runs BEFORE the S-CALIB row and is exempt from it (it is < 1 min); N4 resume after a STOP following the master write: re-write the SAME master with overwrite=true (server keeps .bak) only when the ledger shows this skill's own RESULT write for it, and re-measure the PC sizes on resume; N8 first ledger line carries next=S1 (or the resume table accepts READ new ledger); N9 a .mcp-running marker with no live process (dashboard + check_cdb_lock show nothing) -> STOP S-STALEMARKER with the file name (lead/Wing removes it), not S-BUSY forever; N10, N11 (job ids look like calc-xxxxxxxx), N12 (if the run_calculation answer is lost, use dashboard/run_history to find the run; if no job id can be found, STOP S-LOST with evidence), N13 (clear old read-back pages before a new read-back).
- Shared blocks: state in 13_SHARED_BLOCKS.md that the author skill carries A-D only (it never runs or reads results); keep C identical in all three (restore the two rows or change the master copy and all three).
- N14: document as a known limit in the author skill (26016 parameters live inside the source; a parameter change = new approved source from the lead).

D2:
- N5: after any resume, re-prove G0 (canary) before jumping to header next_state.
- N3 side: S0-NOCANARY hand-back must tell the lead exactly how to run the canary (run-and-fix S3 canary step).
- N6: beam-map pages <= 20 KB (smaller windows). Before S7b, estimate reads needed (members x LCs / page size); if above the cap -> STOP S7-NEEDS-EXPORT ("bulk member results need MCP export to file; lead decides"), never start a read marathon.
- A-11 remaining sentence: "factors are allowed EN 1990 + UK NA values, and uplift/EQU combinations use favourable G" (after T's N-01) - nothing stronger.
- N-02 skill side: hand exit 2 "give --extra-forces" for AQB-only members routes to step 2c (already exists) - check it does.
- Mesh: align with T's compression-only default.
