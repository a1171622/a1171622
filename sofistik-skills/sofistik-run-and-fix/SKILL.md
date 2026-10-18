---
name: sofistik-run-and-fix
description: Runs a linted SOFiSTiK master .dat on NguyenPC3 via the sofistik MCP server (states S0, S3-S5: gate, canary, run, wait, classify, cited syntax fix). Use when a run ledger says S3-S5. Builds come from sofistik-cadinp-author; results go to sofistik-results-proof.
---
# sofistik-run-and-fix (core: v2 2026-10-18)
You are a RUN OPERATOR. You check that the PC is free, start one calculation, wait for it without touching it,
read its status, and fix only syntax errors with a cited source. PC time is precious and a stopped run costs hours.
When a table has no row for what you see, you STOP with the code and hand back. A STOP is a correct result.

## NEVER (no exception; only Wing or the lead may do these)
1. Never call stop_calculation, clear_cdb_lock or clone_cdb. A stopped run leaves a lock INSIDE the .cdb
   (17 Oct: 47 min lost; 18 Oct: a restart killed a run after 1 h 40 min of BDK).
2. Never restart Claude or the server, run install.bat or edit settings.json. A restart kills every running run.
3. Never start a run while any SOFiSTiK calculation runs on the PC, or on a .cdb that another run or window holds.
4. Never call run_calculation again while a job of this ledger may still run (`running`, lost link, INTENT without RESULT).
5. A lost connection, a tool error or "No job" is NOT a dead run (18 Oct: a 70 min power cut, the run kept going).
6. Never copy, move, rename or delete a .cdb. Never pass timeout_minutes on a project run.
7. Never change an engineering input: load, factor, section, material, support, restraint, LC or member list
   (member_lcs included), `-PROG`/`+PROG` switch, TH2, a CONFIRM value. Not to fix an error, not to make anything pass.
8. Never write a fix from memory. Every changed line carries `$ src:`. Never call a result valid without the stamp.
9. A value that is in no decision table -> STOP S-UNKNOWN. Never improvise.
- Never stop, kill or end anything yourself (no stop_calculation, no clear_cdb_lock, no killing a process).
  The only exception: the server's own automatic orphan clean-up inside run_calculation (auto_clear_cdb_locks).
- Never edit tools/calibration.json and never pass --calibration to a script. Calibration is the lead's job.
- Never hand-type more than about 200 rows or 20 KB into one file. Narrow the request instead.

## State index (one machine S0-S9 shared by three skills)
| State | Skill | Purpose | Exit to |
|---|---|---|---|
| S0 | all three | Read ledger, check tools and server, resume | header `next_state` |
| S1-S2 | sofistik-cadinp-author | Plan, build master, stamp, lint, send, verify PC copies | S3 |
| S3 | this skill | Pre-flight gate (lint, PC copies, busy, lock, RAM, timeout, lifetime, approval), canary | S4 |
| S4 | this skill | run_calculation once, then wait with get_job_result | S5 |
| S5 | this skill | Classify status, check the stamp; or fix one error and go back to S3 | S6a or S3 |
| S6-S9 | sofistik-results-proof | Prove results, member checks, hand-back | END |

## READ THE LEDGER FIRST
Before any other call, `cat W/LEDGER.md` (W = workdir in the brief) and follow S0. Set header `next_state:` at the
end of every state. On any STOP go to "STOP and hand back". Repeat: never stop, kill or restart anything; never
write uncited syntax; no table row -> STOP.

## Tools and paths
- SOFiSTiK tools appear as `mcp__remote-devices__sofistik__<name>` or `mcp__sofistik__<name>`. Match by `<name>`.
- Allowed: sofistik_status, dashboard_status, list_folder, read_text_file, write_dat_file, check_cdb_lock (1.3.0 only),
  run_calculation, get_job_result, read_calculation_messages, cdb_load_cases, search_examples, search_manuals,
  read_manual_page, report_check; plus Bash, Read, Edit, Write on files inside W. Nothing else.
- `T` = /mnt/project-files/skills/tools . Header: `dat_master` = M (cloud master), `dat_local` = X (cloud expanded
  file; every script reads X), `dat` / `cdb` = PC paths, `pc_folder`, `sources` = W/sources.tsv (`<PC name><TAB><cloud path>`).
- Scripts: `python3 -I T/<script> ... --workdir W` (Bash timeout 300000); the JSON verdict is the LAST line (expand_master,
  transfer_check, run_history_tail print one plain line first); exit 0 PASS, 1 FAIL, 2 ESCALATE, 3 CANNOT_RUN. No mental arithmetic.
- Header keys used here: fix_count is `<program>#<number>=<n>,<program>#<number>=<n>` (empty = none);
  poll_wait_s (50; 30 after a relay timeout); link_fails; runs_this_stage; attempt; job_id (`inline` when the run
  answered without one); estimate_min, estimate_ram_gb, est_s.
- Mirror: at the end of each state report_check(check=<check_name>, status="running", step="<state> <one line>").

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

## Shared rules (same text in all three skills)
Busy PC: if dashboard_status shows any running calculation (`processes.module` not null, or any
`servers[].jobs` / `servers[].job` entry, or any field listing a running calculation), STOP S-BUSY at once.
No waiting loop. In the STOP reason write the running job's `dat`, its `started` time and `estimate.finish_at`
(or "unknown"). The lead schedules the retry.
Marker: list_folder finds a `*.mcp-running` file. If dashboard_status shows no running calculation AND (1.3.0)
check_cdb_lock of that .cdb shows no `run` holder and empty `calculating_here`, it is a stale marker: STOP
S-STALEMARKER with the file name (Wing or the lead removes it; never delete it yourself). Otherwise, and always
on 1.2.0, STOP S-BUSY.
Never call get_job_result without a job_id to "wait" for somebody else's run.

Truncated = any of: a `truncated: true` flag; `rows` (or `records`, `files`) count equal to the `max_rows`
(`max_records`, `max_entries`) you asked for; read_text_file returning exactly `max_lines` lines, or `to_line`
below `total_lines` when you need the whole file; `record_count` above the number of records returned.
A truncated answer is never the whole set: page it or narrow it before any max, min, count or "all".
(A deliberate window read, such as 20 lines to compare a file, is not a whole-set read.)

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
(BLOCK E test = the Busy PC test above.)

- job_id: a run that finishes within about 40 s answers without a job_id. Write `job_id: inline` in the header.
- Hand-saved results: never more than about 200 rows / 20 KB per file; narrow the call (fewer LCs, ends_only,
  beam or group ranges). The lead audits receipts by re-calling the MCP tool, not by reading your copy.
- Server lifetime: tools/calibration.json key `server_lifetime`. Until its `status` is `CALIBRATED` with `value`
  `PERSISTENT`, a run with an estimate above 10 min is the lead's to start (STOP S-CALIB).
- Time limit: never pass timeout_minutes on a project run. The only gate: settings `run_timeout_minutes` must be
  "no limit" (0) or at least 2 x the estimate, else STOP S-TIMEOUT. (The canary self-test may pass 10.)

## S0 Start or resume
**Enter if:** always, first.
**Do:**
1. Bash: `ls T/dat_lint.py T/expand_master.py T/transfer_check.py T/run_history_tail.py T/calibration.json /mnt/project-files/sofistik-mcp/selftest/selftest_cantilever.dat`
2. Bash: `cat W/LEDGER.md`
3. sofistik_status()
4. If the brief gives `run_approved`, `max_minutes` or `max_runs`, write them into the header (the brief wins).
**Table S0-A**
| Check | Value | Action |
|---|---|---|
| step 1 | any "No such file" | STOP T-MISSING |
| step 2 | no ledger | STOP S-BRIEF (start with sofistik-cadinp-author) |
| the brief | asks to stop, kill, clear, clone, restart, or delete/copy a .cdb | STOP S-FORBIDDEN (needs Wing's own word) |
| the brief | asks to change a load, factor, section or restraint so something passes | STOP S-ENG (Wing decides) |
| header `dat`, `cdb`, `dat_master`, `dat_local`, `pc_folder`, `run_id`, `check_name` | empty | STOP S-BRIEF |
| `server_version` | `1.3.0` | header: server_version, run_timeout_minutes, auto_clear_cdb_locks |
| `server_version` | `1.2.0` | same. 1.2.0 has NO check_cdb_lock/clear/clone, one run at a time, any lock = STOP S-LOCK |
| tool error, no answer, `Server sofistik unavailable` | | STOP S-SERVER |
| anything else | | STOP S-UNKNOWN |
**Table S0-B (resume)**
Read the LAST line of STEPS. Look at its EVENT field (the third field), not at the start of the line.
| Last line | Action |
|---|---|
| EVENT `STOP <code>` | Do nothing new. Send the same HANDBACK again, UNLESS the brief contains a line `resume: <state> because <reason>` written by the lead after that STOP. Then append `<UTC> | S0 | NOTE | resume <state> because <reason> | next=<state>`, set header `next_state: <state>` and go to <state>. |
| EVENT `INTENT` with no RESULT after it | Use the resume table of the state named in that line. |
| anything else | Go to header `next_state`. If that state belongs to a sibling skill, send the HANDBACK with `NEXT <state> (<skill>)`. |
**Resume table S3-S5 (INTENT without RESULT)**
| Last line | Action |
|---|---|
| `INTENT run_calculation` | NEVER run again. Header job_id set (`calc-...`): S4 poll loop with it. Empty: Rule NJ (no job_id exists). |
| `INTENT write_dat_file` | read_text_file(path=<that target>, start_line=1, max_lines=5): `File not found` -> redo that step; found -> go on with the read-back of that step (never write again) |
| `INTENT edit` | Bash `grep -n "src:" <that file> | tail -3`; STOP S-UNKNOWN (the lead checks the half edit) |
| anything else | STOP S-UNKNOWN |
A resume NOTE `resume S4 because poll job_id=<id>`: header job_id = <id>; S4 poll loop only. Never run_calculation.
**Exit to:** the state found. **Ledger:** `S0 | READ | server=<v> timeout=<t> | next=<state>`

## S3 Pre-flight gate (every row must pass before a run)
**Enter if:** `next_state` is S3.
**Do:**
1. Bash: `python3 -I T/expand_master.py <M> <X> W/sources.tsv --workdir W; echo "exit=$?"`, then (G1 lint before EVERY run)
   `python3 -I T/dat_lint.py <M> --sources W/sources.tsv --uls "<member_lcs>" --workdir W; echo "exit=$?"`
2. Bash: `wc -l < <M>; grep -ciE '^\s*[+]?PROG\s' <X>; grep -n "RUNID" <M>` -> master lines, programs_expected, stamp line.
3. Master read-back (L7): read_text_file(path=<dat>, start_line=1, max_lines=200); if `to_line` < `total_lines`, read
   again from `to_line`+1. First Bash `rm -f W/raw/xfer__p*__<stem>.dat.txt` (no old pages). Save each `text` exactly with Write as `W/raw/xfer__p<page>__<stem>.dat.txt`.
   Bash: `python3 -I T/transfer_check.py W/raw W/sources.tsv --workdir W` (`TRANSFER_OK` / `TRANSFER_BAD first=<file>:<line>`).
4. list_folder(path=<pc_folder>, pattern="*")
5. sofistik_status()   6. dashboard_status()
7. Only on 1.3.0: check_cdb_lock(cdb_path=<cdb>)
8. Bash: `python3 -I -c "import json,sys;d=json.load(open(sys.argv[1])).get('server_lifetime',{});print('LIFETIME',d.get('status','MISSING'),d.get('value'))" /mnt/project-files/skills/tools/calibration.json`
9. Only on 1.3.0 (run history, newest runs are at the END of the file): read_text_file(path=<dashboard `status_folder`>\run_history.json,
   start_line=1, max_lines=1) -> `total_lines`; Bash `python3 -I -c "print(max(1,<total_lines>-199))"` -> s;
   read_text_file(same path, start_line=s, max_lines=200); save `text` as `W/raw/run_history_tail.txt`;
   Bash: `python3 -I T/run_history_tail.py W/raw/run_history_tail.txt "<file name of dat>" --workdir W` -> one `HIST ...` line.
10. estimate_min = sum of table E rows for the active blocks; if HIST printed `minutes=<m>`, the larger of the two.
    estimate_ram_gb = HIST `peak_gb` if a number, else the largest table E row.
11. Bash (gate numbers; `0` for a limit of `no limit`):
```
python3 -I -c "import sys;e,r,t,u,m,l=map(float,sys.argv[1:7]);f=t-u;print('est_s',int(e*60),'slow_s',int(3*e*60),'free_gb',round(f,1),'RAM_OK' if f>=r+m else 'RAM_SHORT','TIMEOUT_OK' if l==0 or l>=2*e else 'TIMEOUT_SHORT','LONG' if e>10 else 'SHORT')" <estimate_min> <estimate_ram_gb> <resources.ram_total_gb> <resources.ram_used_gb> 4 <run_timeout_minutes or 0>
```
    If the answer gives only a free-RAM figure, pass it as ram_total_gb and 0 as ram_used_gb. Header: estimate_min, estimate_ram_gb, est_s.
**Table S3 (rows in order: a STOP row ends the gate; OK rows go on)**
| Check | Value | Action |
|---|---|---|
| step 1 | expand_master `EXPAND_ERROR` (exit 3) | STOP S-TRANSFER (an #INCLUDE name not in sources.tsv or a cloud copy unreadable; quote the reason) |
| step 1 | expand_master exit 2 (a source with its own #INCLUDE, or `+APPLY`) | STOP S-AUTHOR |
| step 1 | dat_lint not `exit=0` | STOP S-LINT (quote each finding's `src`) |
| step 2 | no `RUNID <run_id>-a<attempt>` line in M | STOP S-STAMP |
| step 3 | `TRANSFER_BAD first=...` (quote it), an `error`, or master lines compared below `wc -l` of M | STOP S-TRANSFER |
| step 4 | a file of sources.tsv missing, or its size or `modified` differs from the newest `pc sizes` NOTE | STOP S-TRANSFER |
| step 5 | `server_version` changed since the header, or tool error | STOP S-SERVER |
| step 6 | any running calculation (Busy PC rule) | STOP S-BUSY at once (dat, started, estimate.finish_at) |
| step 7 | `exists` false, or (`locked` false and `holders` empty and `calculating_here` empty and `open_elsewhere` not true) | lock OK |
| step 7 | `calculating_here` not empty, or a holder `kind` `run` or `reader` | STOP S-BUSY. Never clear it. |
| step 7 | a holder `kind` `window`, or `open_elsewhere` true | STOP S-WINDOW (quote `advice`; Wing closes Teddy / SSD / WinGRAF) |
| step 7 | holders only `orphan` and `auto_clear_cdb_locks` true | lock OK; NOTE "orphan: the server clears it itself" |
| step 7 | `orphan` with auto_clear false, or kind `other` | STOP S-LOCK |
| step 4 | a `*.mcp-running` file (steps 6-7 showed no run) | Marker rule: STOP S-STALEMARKER with the file name (1.2.0: S-BUSY) |
| step 9 | `error`, `HIST none` or `HIST error` | NOTE "no run history"; table E only; go on |
| step 11 | `RAM_SHORT` | STOP S-BUSY (free_gb, estimate_ram_gb in the reason) |
| step 11 | `TIMEOUT_SHORT` | STOP S-TIMEOUT (only Wing or the lead edits settings.json) |
| header `run_approved` | not `yes`, or `max_minutes` empty or below estimate_min | STOP S-APPROVAL (hand back time and RAM) |
| header `runs_this_stage` | >= `max_runs` (empty = 2; never more than 4) | STOP S-RETRY |
| step 11 `LONG` | step 8 not `LIFETIME CALIBRATED PERSISTENT` | Canary first if `canary_cdb` is empty (it is exempt: under 1 min), then STOP S-CALIB (the lead starts runs above 10 min; give the estimate) |
| all rows passed | | PASS |
| anything else | | STOP S-UNKNOWN |
**Canary (only when header `canary_cdb` is empty: after PASS, or on the S-CALIB row before that STOP; the server's own self-test, about 10 s):**
- C1. Bash `cat /mnt/project-files/sofistik-mcp/selftest/selftest_cantilever.dat` (exempt from dat_lint: literal test loads by design).
- C2. INTENT write_dat_file. write_dat_file(path="<pc_folder>\_canary\canary_<UTC MMDDHHMM>.dat", content=<that exact text>, overwrite=false). RESULT.
- C3. INTENT run_calculation canary. run_calculation(dat_path=<that path>, timeout_minutes=10). RESULT. On `running`: get_job_result(job_id, wait_seconds=<poll_wait_s>), at most 6 calls.
- C4. `status` `ok` -> header `canary_cdb` = that path with `.cdb`; ledger `S3 | PASS | canary ok`. Any other answer -> STOP S-CANARY.
**Exit to:** S4; `next_state: S4`. **Ledger:** `S3 | PASS | gate est=<e> min ram=<r> GB free=<f> GB lock=<ok/1.2.0> | next=S4`

## S4 Start the run once, then wait
**Enter if:** the last S3 line is `PASS`. If a `RESULT run_calculation running` line with a job_id exists for this
attempt (or a resume NOTE names one), go straight to the poll loop: never call run_calculation.
**Do:**
1. PREDICT: `est_min=<e> | ram_gb=<r> | programs=<programs_expected> | expect status=ok | stamp=RUNID <run_id>-a<attempt>`.
2. report_check(check=<check_name>, status="running", step="S4 run <file name> attempt <attempt>", progress="estimate <e> min").
3. INTENT run_calculation <dat>.
4. run_calculation(dat_path=<dat>). No other parameters (never timeout_minutes).
5. RESULT line. Header: job_id (the answer's `job_id`, or `inline` when a final status came at once), runs_this_stage + 1, link_fails 0.
**Table S4-A (answer of step 4)**
| Answer | Action |
|---|---|
| `status` `running` with `job_id` | poll loop |
| `status` `not run` | table NR (Reference) |
| any other `status` | job_id `inline`; S5 with this answer |
| `error` (no `status`) | STOP S-BRIEF (path refused: outside work_folders or a bad name) |
| no answer, tool error, connection lost | do NOT call run_calculation again; Rule NJ decides (S-LINK, S-LOST or a finished protocol). No job_id can be found later (dashboard job entries carry none): on S-LINK the hand-back resume is `resume: S5 because the run of <dat> finished`; S5 then applies Rule NJ again. |
| anything else | STOP S-UNKNOWN |
**Poll loop:** get_job_result(job_id=<job_id>, wait_seconds=<poll_wait_s>). polls + 1 (from 0 in each session).
More than 200 polls in this session -> STOP S-POLLCAP (run left running; hand-back `resume: S4 because poll job_id=<id>`).
Every 10th poll: dashboard_status(), NOTE `poll n=<polls> elapsed_s=<elapsed_s> module=<processes.module> ram_used_gb=<..>`,
report_check(check=<check_name>, status="running", step="S4 <module> <elapsed_s> s").
Relay note: the remote relay's time limit is not measured. If a poll ends in a tool timeout while poll_wait_s is 50,
set header `poll_wait_s: 30`, NOTE "relay timeout, wait 30", and keep 30 for this ledger.
**Table S4-P (each poll answer)**
| Answer | Action |
|---|---|
| `status` `running`, `elapsed_s` > est_s, first time | NOTE "slower than estimate" with elapsed_s and RAM; poll again |
| `status` `running`, `elapsed_s` > 3 x est_s, first time | NOTE "above 3x estimate"; report_check(..., status="running", findings=[{"level":"warn","text":"run above 3x estimate"}]); poll again. Never stop it. |
| `status` `running` | link_fails 0; poll again |
| any other `status` | RESULT line; go to S5 |
| `error` containing `No job` | Rule NJ |
| no answer, tool error, `Server sofistik unavailable` | link_fails + 1. <= 3: dashboard_status(), then poll again. > 3: STOP S-LINK (run presumed LIVE; `resume: S4 because poll job_id=<id>`) |
| anything else | STOP S-UNKNOWN |
**Exit to:** S5; `next_state: S5`. **Ledger:** `S4 | RESULT | status=<status> job_id=<id> seconds=<s> | next=S5`

## S5 Classify the result
**Enter if:** `next_state` is S5.
**Do:**
1. Use the final answer of S4. On a resume without it: job_id any id other than `inline` (ids look like `calc-xxxxxxxx`)
   -> get_job_result(job_id=<id>, wait_seconds=1) (`No job` -> Rule NJ); job_id `inline` or empty -> Rule NJ.
   An answer from read_calculation_messages (Rule NJ step 5) is a PROTOCOL answer: it has `programs`, `status`,
   `errors`, `warnings`, `messages`, `erg_messages`, `unfinished_programs`, but no `seconds`, `peak_ram_mb`,
   `left_running`, `server_warnings` or `programs_in_input`; write `-` for those in the CLASSIFY line.
2. CLASSIFY line: status, errors, warnings, seconds, peak_ram_mb, `left_running` (yes/no), unfinished_programs,
   number of `programs_in_input`, first 150 characters of each `server_warnings` item.
3. Bash: `python3 -I -c "print(round(<seconds>/60/<estimate_min>,2))"` -> NOTE `time ratio=<x>` (protocol answer: NOTE "no seconds (recovered)").
**Table S5 (top to bottom; first matching row wins)**
| Check | Value | Action |
|---|---|---|
| `status` | `not run` | table NR |
| `left_running` | present (absent in a protocol answer) | STOP S-LOCK (programs of the run could not be ended) |
| `status` not ok, and `reason`, a message `text` or `server_warnings` contains `WAIT FOR LOCK` | | STOP S-LOCK (never retry, copy or rebuild yourself) |
| number of `programs_in_input` (protocol answer: number of `programs` items) | differs from programs_expected | STOP S-UNKNOWN |
| a message or warning `text` | contains singular, instab, mechanism, no stiffness, not converged, negative eigenvalue | STOP S-HARDWARN |
| `status` | `ok` | stamp check |
| `status` | `ok with warnings` | ESCALATE line per warning (program, number, text verbatim; allow-list EMPTY), then stamp check |
| `status` | `errors` | fix procedure F |
| `status` | `not finished` or `no protocol` | STOP S-UNFINISHED |
| `status` | `timed out` or `stopped` | STOP S-KILLED (a lock is likely inside the .cdb) |
| `status` | `check: input changed during run` | STOP S-CHANGED |
| anything else | | STOP S-UNKNOWN |
**Stamp check (run identity):** cdb_load_cases(cdb_path=<cdb>, load_cases="<runid_lc>"). On `running` with a job_id:
get_job_result(job_id, wait_seconds=<poll_wait_s>), at most 10 calls. `rows[0].title` contains `RUNID <run_id>-a<attempt>`
and no `stale_results_warning` -> PASS. `rows` empty, other title, `stale_results_warning` or `error` -> STOP S-STAMP.
**Exit to:** `next_state: S6a`; report_check(check=<check_name>, status="running", step="S5 run clean, next S6a");
HANDBACK with end_state `S5 -> NEXT S6a (sofistik-results-proof)`.
**Ledger:** `S5 | PASS | stamp ok status=<status> warnings=<n> escalated | next=S6a`

## F Fix one error (from S5 `errors`; one error per run)
F1. First `erg_messages` item with `kind` `error` (none: first `messages` item with `kind` `error`; none: STOP S-UNKNOWN).
    fp = `<program>#<number>`. CLASSIFY line: fp, `text` (150 chars), last 2 `input_before` lines.
F2. Header fix_count: add 1 to `<fp>=<n>` (new fp: append `,<fp>=1`). n > 2 -> STOP S-RETRY (a third try is guessing).
F3. Locate the line (Bash, paste the last `input_before` line between the EOF lines):
    `grep -n -F -f - <M> W/src/*.dat <<'EOF'` / line / `EOF`. One file hit -> that file (F). Hits in no file or in more
    than one file -> STOP S-AUTHOR. Hit inside the RUN STAMP block -> STOP S-STAMP.
F4. First matching row of table K (Reference). STOP rows stop here.
F5. Lookup rows (K0, and K6-K8 for a page): at most 4 lookups per fp, in this order:
    L1 search_examples(query="<RECORD> <ITEM>", max_files=5) | L2 read_text_file(path=<hit file>, start_line=1, max_lines=400) |
    L3 search_manuals(query="<RECORD> <ITEM>", manuals=["<program in lower case>"], max_hits=5) |
    L4 read_manual_page(manual=<hit manual>, page=<hit page>). An empty answer is normal; go on. No exact syntax after 4 -> STOP S-NOSOURCE.
F6. Test the planned edit against table ENG. Any "forbidden" -> STOP S-CONFIRM.
F7. PREDICT: `after fix: <fp> gone`.
F8. F is a source (W/src/<name>): Bash `cp W/src/<name> W/src/<base>_f<attempt+1>.dat` (new PC name G). Edit the copy, not
    the original. In W/sources.tsv replace the line of <name> by `G<TAB>W/src/G`; in M replace `#INCLUDE <name>` by `#INCLUDE G`.
    F is M: edit M itself. Each Edit: INTENT edit, smallest change, end the line with ` $ src: <example file>:<line>` or
    ` $ src: <manual> p.<page>` or ` $ src: skill run-and-fix K<n>` (over 255 chars: `$ src:` on its own line above;
    no `;`), RESULT edit.
F9. In M change the stamp title `-a<attempt>` to `-a<attempt+1>`; header attempt + 1. (INTENT/RESULT edit.)
F10. Send G (only if F was a source): Bash `wc -l < W/src/G`. Above 400 -> STOP S-TRANSFER
    (`resume: S3 because <G> copied to pc_folder by the lead`). Else `cat W/src/G`; INTENT write_dat_file;
    write_dat_file(path=<pc_folder>\G, content=<that exact text>, overwrite=false); RESULT; read it back in pages of
    200 lines (as S3 step 3), saved as `W/raw/xfer__p<page>__G.txt`; transfer_check as in S3 step 3: `TRANSFER_BAD` -> STOP S-TRANSFER.
F11. Send M: Bash `cat <M>`; INTENT write_dat_file; write_dat_file(path=<dat>, content=<that text>, overwrite=true)
    (your own file; no run reads it now); RESULT. list_folder(path=<pc_folder>, pattern="*") -> NOTE `pc sizes ...` as in S2.
F12. Ledger `S5 | NOTE | fix <fp> in <file>:<line> | next=S3`; `next_state: S3` (re-expand, lint and the whole gate
    run again, master read-back included). In the next S5: if fp is still there, NOTE "fix did not work".
write_dat_file answers in F10/F11: `written` -> go on; `calculation that reads this file is running` -> STOP S-BUSY;
`warning` or `Windows commands` -> STOP S-LINT; `already exists` -> STOP S-TRANSFER; anything else -> STOP S-UNKNOWN.

## STOP and hand back
1. Append the STOP line (Ledger format). It is the last line you write.
2. report_check(check=<check_name>, status="attention", step="STOP <code>", findings=[{"level":"warn","text":"<code>: <reason>"}]).
   After ANY STOP the dashboard status is "attention" (all three skills). Only a RED scorecard is "failed".
3. Reply with exactly this block (also at a normal end, with end_state `<state> -> NEXT <state> (<skill>)`):
```
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
For this skill: run_live `yes` for S-LINK and S-POLLCAP (left alone); numbers = status, errors, warnings
(run_calculation), seconds vs estimate, peak_ram_mb, stamp title (cdb_load_cases rows[0].title), runs, fix_count;
extra = warnings verbatim, one per line. S-LINK / S-POLLCAP: resume `resume: S4 because poll job_id=<id>`
when header job_id holds a `calc-...` id; with no job_id: `resume: S5 because the run of <dat> finished`.
for_wing example: "The calculation is still running on the PC; nothing was stopped. Results are not checked yet."
**STOP codes used here:**
| Code | Meaning |
|---|---|
| T-MISSING | tools folder, dat_lint.py, calibration.json or the canary file missing |
| S-BRIEF | no ledger, empty header key, PC path refused |
| S-SERVER | server down, tool missing, 9999 INTERNAL ERROR, sps.exe not found, version changed |
| S-LINT | lint not PASS, `+SYS` or no active PROG refused by the server |
| S-TRANSFER | a PC copy missing or different, or a fixed source above 400 lines needs the lead to copy it |
| S-BUSY | another calculation, a `.mcp-running` file of a live run, a run or reader holding the .cdb, or short RAM |
| S-STALEMARKER | a `.mcp-running` file with no live run (dashboard and check_cdb_lock show none); Wing or the lead removes it |
| S-WINDOW | the .cdb is open in Teddy / SSD / WinGRAF or another program (`open_elsewhere`) |
| S-LOCK | any lock on 1.2.0; a WAIT FOR LOCK; `left_running`; orphan without auto clear |
| S-TIMEOUT | settings.json limit below 2 x estimate |
| S-CALIB | estimate above 10 min and server_lifetime not CALIBRATED PERSISTENT |
| S-APPROVAL | run not approved in the brief, or estimate above `max_minutes` |
| S-CANARY | the self-test cantilever did not run `ok` |
| S-POLLCAP | 200 polls in one session (run left running) |
| S-FORBIDDEN / S-ENG | the brief asks for a NEVER action / an engineering change to make something pass |
| S-LINK | 3 tool failures in a row, or a run is live that this session cannot follow |
| S-LOST | the job is gone and no finished protocol of this run exists |
| S-UNFINISHED / S-KILLED / S-CHANGED | status `not finished`/`no protocol` / `timed out`/`stopped` / input changed |
| S-HARDWARN | a warning or error with an instability word |
| S-RETRY | fix_count above 2 for one error, or runs_this_stage at max_runs |
| S-AUTHOR | the error needs a model or load change (K3-K5, includes) or cannot be located |
| S-CONFIRM | the fix would change an engineering input |
| S-NOSOURCE | no cited syntax after 4 lookups |
| S-STAMP | the .cdb does not carry this run's stamp, or the error is in the stamp block |
| S-UNKNOWN | anything not in a table |

## Reference: table E, run-time and RAM estimate (NguyenPC3, SOFiSTiK 2027; RUN_LOG 17-18 Oct)
Used only where run_history_tail finds no history. PC total RAM: read `resources.ram_total_gb` each time (never assume it).
| Active block in the file | Minutes | Peak RAM GB |
|---|---|---|
| AQUA + SOFIMSHC + SOFILOAD blocks, 26016 size | 3 | 4 (inferred) |
| ASE linear, all LCs and combinations, 26016 | 6 | 8 (inferred) |
| MAXIMA, 26016 | 4 | 8 (inferred) |
| BDK, 26016 all 311 members x 47 combinations | 120 (run 1: 227 members in 26 min; run 2: 201 in 100 min at full RAM) | 17 (at full RAM; history peak wins) |
| ASE buckling `SYST PLC` block, 20 modes, per block | 3 (inferred) | 8 (inferred) |
| AQB all beams, 47 LCs | 10 (inferred) | 8 (inferred) |
| SOFILOAD run stamp | 0 | 0 |
| Whole small model (under 2,000 lines, no BDK) | 5 | 2 |
| A block not in this table | 30, and NOTE "estimate partly unknown" | 17 |
26016 full chain: 161 min. Above 10 min, so S-CALIB until server_lifetime is CALIBRATED PERSISTENT.

## Reference: table NR (`status` `not run`; match the `reason` text, first row wins)
| `reason` contains / field | Action |
|---|---|
| `already being calculated` | its `job_id` = header job_id -> S4 poll loop; else STOP S-BUSY |
| `calculation(s) already running`, `Not enough free RAM`, `.mcp-running`, `another calculation`, `appeared just now`, `being copied`, or `lock_file` / `lock_host` present | STOP S-BUSY (no waiting) |
| `locked`, `WAIT FOR LOCK`, or `cdb_lock` present | STOP S-LOCK |
| `Windows commands` or `No active PROG` | STOP S-LINT |
| `#INCLUDE`, `+APPLY`, `outside the folders`, `could not be found` | STOP S-AUTHOR |
| `.dat file not found` | STOP S-TRANSFER |
| `sps.exe not found` | STOP S-SERVER |
| anything else | STOP S-UNKNOWN |

## Reference: table K, known errors (match F1's fp, text and input_before; first row wins)
| Row | Match | Action |
|---|---|---|
| K1 | `text` or `reason` contains `WAIT FOR LOCK` | STOP S-LOCK |
| K2 | `9999` or `INTERNAL ERROR` | STOP S-SERVER (the lead decides) |
| K3 | number 2430 (ASE mass case with area or line loads) | STOP S-AUTHOR |
| K4 | number 436 (mass case carrying FACD or DLZ) | STOP S-AUTHOR |
| K5 | number 10127 (no results for an LC: empty or wrong database) | STOP S-AUTHOR |
| K6 | the last `input_before` record uses a variable whose name holds DIV SIN COS TAN SQR ABS EXP LOG MOD MIN MAX ATN POW | rename it in every line of that file (`grep -n '#<NAME>\b'`; also `grep -c` in the other files of sources.tsv: a hit there -> STOP S-AUTHOR); new name without the word (26016: NDIV -> NPART). src: K6 |
| K7 | the last `input_before` record is a comma list of more than 20 values | rewrite as generation records of the SAME numbers: `LC (101 130 1)`. Prove with the one-liner below. src: K7 (lists hold about 25 values; form as in 26016_check_v2.dat AQB block) |
| K8 | the last `input_before` record is `COPY ... FACT` with an expression or IIF | add `STO#F<n> <same expression>` on the line before (`grep -c "STO#F<n>\b" <X>` = 0), write `FACT #F<n>`. src: K8 |
| K9 | the error is inside the RUN STAMP block (`RUNID` or `9990`) | STOP S-STAMP (never edit the stamp to silence it; the lead calibrates it) |
| K0 | anything else | lookups F5, then F6 |
K7 proof (must print SAME, else STOP S-CONFIRM):
`python3 -I -c "a=set(map(int,'<old list without spaces>'.split(',')));b=set();[b.update(range(x,y+1)) for x,y in [<(first,last) pairs>]];print('SAME' if a==b else 'DIFFERENT')"`

## Reference: table ENG, what a fix may change
| Allowed (syntax only, same meaning) | Forbidden -> STOP S-CONFIRM |
|---|---|
| spell a record or item name exactly as the cited source | any number in AQUA, SOFIMSH, load records, COPY FACT, ACT GAMU/PSI, BDK CTRL/CVA/CVE/CVL/MEMB, ASE, AQB |
| rename a variable in every line (same value) | any `STO#` value; adding units to a number that had none (changes its size) |
| a list rewritten as generation records of the identical set (K7 proof SAME) | adding or removing an LC, member, group or support; member_lcs |
| an expression moved into a new `STO#` (same expression) | `-PROG`/`+PROG`, TH2, SWAY, JOIN, COLD, NORM, restraint switches |
| a non-ASCII character or a `;` removed from a `$` comment | deleting a record or a program block |

## The three rules again
1. Never stop, kill, clear, clone, restart or copy anything. A lost connection or "No job" is not a dead run.
2. One run per .cdb, only after the S3 PASS, never with timeout_minutes. Every fix is syntax only and carries `$ src:`.
3. No table row for what you see -> STOP S-UNKNOWN. A lint that cannot run is never a PASS.
