# 13 Shared blocks (owner: Design Engineer 1; binding wording of 12_TRIAGE L1-L12)
Copy each block below VERBATIM. Who carries what: sofistik-run-and-fix and sofistik-results-proof carry A-H;
sofistik-cadinp-author carries A-D only (it never runs SOFiSTiK, never polls and never reads results, so E-H do not apply).
Only text inside `<...>` is filled per skill. Version line for all three: `core: v2 2026-10-18`.

---------------------------------------------------------------------------------------------------
## BLOCK A - NEVER additions (append to each skill's NEVER list; keep the skill's own items)
```
- Never stop, kill or end anything yourself (no stop_calculation, no clear_cdb_lock, no killing a process).
  The only exception: the server's own automatic orphan clean-up inside run_calculation (auto_clear_cdb_locks).
- Never edit tools/calibration.json and never pass --calibration to a script. Calibration is the lead's job.
- Never hand-type more than about 200 rows or 20 KB into one file. Narrow the request instead.
```

---------------------------------------------------------------------------------------------------
## BLOCK B - Ledger (L1)
```
## Ledger (one file for all three skills: W/LEDGER.md)
- Header: `key: value`, one per line, rewritten in place. Set `next_state:` at the end of EVERY state.
- STEPS: append only. One line per event:
  `<UTC ISO> | <state> | <EVENT> | <detail> | next=<state>`
  UTC ISO: Bash `date -u +%Y-%m-%dT%H:%MZ`. EVENT is exactly one of:
  READ, INTENT, RESULT, PASS, FAIL, ESCALATE, STOP <code>, PREDICT, CLASSIFY, NOTE.
- Append with a quoted heredoc (nothing in it is expanded):
  cat >> W/LEDGER.md <<'EOF'
  2026-10-18T09:05Z | S3 | PASS | gate est=161 min | next=S4
  EOF
- INTENT/RESULT: before every call that changes something (write_dat_file, run_calculation, an Edit of a .dat,
  a Bash command that writes a .dat) append `INTENT <call> <target>`; right after the answer append
  `RESULT <call> <outcome>`. Never skip one.
- A STOP line is the LAST line a skill writes:
  `<UTC ISO> | <state> | STOP <code> | <one-line reason>, evidence=<tool.field or file:line> | next=<state>`
  (next = the state you were in). Then send the HANDBACK block and do nothing else.
```

---------------------------------------------------------------------------------------------------
## BLOCK C - Resume rule (L1; first rows of every skill's S0 resume table)
```
Read the LAST line of STEPS. Look at its EVENT field (the third field), not at the start of the line.
| Last line | Action |
|---|---|
| EVENT `STOP <code>` | Do nothing new. Send the same HANDBACK again, UNLESS the brief contains a line `resume: <state> because <reason>` written by the lead after that STOP. Then append `<UTC> | S0 | NOTE | resume <state> because <reason> | next=<state>`, set header `next_state: <state>` and go to <state>. |
| EVENT `INTENT` with no RESULT after it | Use the resume table of the state named in that line. |
| anything else | Go to header `next_state`. If that state belongs to a sibling skill, send the HANDBACK with `NEXT <state> (<skill>)`. |
```

---------------------------------------------------------------------------------------------------
## BLOCK D - STOP and HANDBACK (L1, L2)
```
## STOP and hand back
1. Append the STOP line (Ledger format). It is the last line you write.
2. report_check(check=<check_name>, status="attention", step="STOP <code>", findings=[{"level":"warn","text":"<code>: <reason>"}]).
   After ANY STOP the dashboard status is "attention" (all three skills). Only a RED scorecard is "failed".
3. Reply with exactly this block (also at a normal end, with end_state `<state> -> NEXT <state> (<skill>)`):
HANDBACK <skill name>
run_id: <run_id>
end_state: <state> -> NEXT <state> (<skill>) | STOP <code> in <state>
ledger: W/LEDGER.md        workdir: <W>
dat: <PC master .dat>      cdb: <PC .cdb>
job_id: <id | inline | ->  run_live: <yes | no | unknown>
summary: <max 3 lines>
numbers: <each number with its source: tool.field, script check id, or receipt id; never typed from memory>
extra: <skill-specific lines, e.g. scorecard and gates; or none>
escalations: <one line each, worst first, with evidence; or none>
open: <one line per decision for the lead, with evidence; or none>
resume: <the exact line the lead can paste into the next brief, "resume: <state> because <reason>"; or none>
for_wing: <2-5 plain sentences, no skill jargon: only what was proven, what was NOT checked, what Wing must decide>
```

---------------------------------------------------------------------------------------------------
## BLOCK E - Busy PC (L3)
```
Busy PC: if dashboard_status shows any running calculation (`processes.module` not null, or any
`servers[].jobs` / `servers[].job` entry, or any field listing a running calculation), STOP S-BUSY at once.
No waiting loop. In the STOP reason write the running job's `dat`, its `started` time and `estimate.finish_at`
(or "unknown"). The lead schedules the retry.
Marker: list_folder finds a `*.mcp-running` file. If dashboard_status shows no running calculation AND (1.3.0)
check_cdb_lock of that .cdb shows no `run` holder and empty `calculating_here`, it is a stale marker: STOP
S-STALEMARKER with the file name (Wing or the lead removes it; never delete it yourself). Otherwise, and always
on 1.2.0, STOP S-BUSY.
Never call get_job_result without a job_id to "wait" for somebody else's run.
```

---------------------------------------------------------------------------------------------------
## BLOCK F - Truncation (L4)
```
Truncated = any of: a `truncated: true` flag; `rows` (or `records`, `files`) count equal to the `max_rows`
(`max_records`, `max_entries`) you asked for; read_text_file returning exactly `max_lines` lines, or `to_line`
below `total_lines` when you need the whole file; `record_count` above the number of records returned.
A truncated answer is never the whole set: page it or narrow it before any max, min, count or "all".
(A deliberate window read, such as 20 lines to compare a file, is not a whole-set read.)
```

---------------------------------------------------------------------------------------------------
## BLOCK G - "No job" after a server restart (L6)
```
Rule NJ (get_job_result answers `error` containing `No job`, or no job_id exists because an answer was lost):
1. dashboard_status(): a calculation is running (BLOCK E test) -> STOP S-LINK (a run is live that this session
   cannot follow; never start another).
2. list_folder(path=<PC folder of dat>, pattern="<stem>.*") -> note `modified` of <stem>.dat, <stem>.prt, <stem>.cdb
   and whether <stem>.mcp-running exists. (Both times are PC local time; compare them with each other only.)
3. <stem>.mcp-running exists: on 1.3.0 check_cdb_lock(cdb_path=<cdb>): a `run` holder or `calculating_here` not
   empty -> STOP S-LINK; else STOP S-STALEMARKER with the file name. On 1.2.0 -> STOP S-LINK.
4. <stem>.prt missing, or its `modified` is earlier than <stem>.dat's -> STOP S-LOST (no protocol of this run).
5. read_calculation_messages(path=<dat>): `finished` true -> treat the run as finished; use this answer as the
   final result (NOTE "result recovered from protocol"). `finished` false or any error -> STOP S-LOST.
```

---------------------------------------------------------------------------------------------------
## BLOCK H - Small facts every skill uses (L10, L11, L9, L8)
```
- job_id: a run that finishes within about 40 s answers without a job_id. Write `job_id: inline` in the header.
- Hand-saved results: never more than about 200 rows / 20 KB per file; narrow the call (fewer LCs, ends_only,
  beam or group ranges). The lead audits receipts by re-calling the MCP tool, not by reading your copy.
- Server lifetime: tools/calibration.json key `server_lifetime`. Until its `status` is `CALIBRATED` with `value`
  `PERSISTENT`, a run with an estimate above 10 min is the lead's to start (STOP S-CALIB).
- Time limit: never pass timeout_minutes on a project run. The only gate: settings `run_timeout_minutes` must be
  "no limit" (0) or at least 2 x the estimate, else STOP S-TIMEOUT. (The canary self-test may pass 10.)
```

---------------------------------------------------------------------------------------------------
## Header keys (union; each skill reads what it needs)
run_id, project, brief, check_name, workdir, dat_master (cloud master), dat_local (cloud EXPANDED file = master with
every #INCLUDE replaced by the cloud copy; this is what every script reads), dat (PC master path), cdb (PC .cdb),
pc_folder, sources (`W/sources.tsv`), runid_lc (9990), attempt, expected_json, member_lcs, member_lcs_approved_by,
buckling_lcs, equ_lcs, sls_lcs, defl_limit_mm, assumptions_agreed, server_version, run_timeout_minutes,
auto_clear_cdb_locks, run_approved, max_minutes, max_runs, canary_cdb, job_id, estimate_min, estimate_ram_gb, est_s,
runs_this_stage, fix_count (`<program>#<number>=<n>,<program>#<number>=<n>`), link_fails, poll_wait_s, state,
next_state, plus results-proof's own keys (cdb_mtime, member_results, ...).
Note for D2: `eigen_el_per_span` is no longer a brief value (A-07: measured by tools); author does not write it.

## STOP codes shared by name (meaning identical everywhere)
S-UNKNOWN (no table row) | S-SERVER (server down, 9999, tool missing) | S-BUSY (L3) | S-LINK (run live, cannot follow)
| S-LOST (run gone, no finished protocol) | S-CALIB (calibration missing for this step) | S-TIMEOUT (L8)
| S-TRANSFER (PC copy missing or different) | S-CONFIRM (engineering input or member_lcs needs the lead/Wing)
| S-FORBIDDEN (brief asks for a NEVER action) | S-ENG (brief asks to change engineering to make something pass)
| S-STALEMARKER (a .mcp-running file with no live run) | T-MISSING (tools file missing).

## Note for D2 (how D1 placed the blocks; round 2)
Both D1 skills paste A at the end of NEVER, B as the "## Ledger" section, C as Table S0-B with exactly its three rows
(each skill's own INTENT rows sit in a separate state resume table below it), and D as "## STOP and hand back" (skill
lines added after it). run-and-fix pastes E, F, G, H under "## Shared rules (same text in all three skills)"; author
does not carry E-H. Round 2 changed E (stale `.mcp-running` marker -> S-STALEMARKER), G (title line and step 3) and H
(server_lifetime status CALIBRATED + value PERSISTENT): re-copy them. New shared STOP code: S-STALEMARKER.
PC read-backs that are saved by hand use pages of max_lines=200 (L10).
