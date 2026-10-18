# 11 Review B: can a Haiku executor run these skills end to end?

Reviewer B (adversarial, executor focus). Files reviewed:
- `skills/sofistik-cadinp-author/SKILL.md` (AUTH)
- `skills/sofistik-run-and-fix/SKILL.md` (RUN)
- `skills/sofistik-results-proof/SKILL.md` (RES)
- `skills/tools/README.md` and every script's `--help`
- checked against `sofistik-mcp/sofistik_mcp/` v1.3.0: server.py, solver.py, results.py, messages.py, dashboard.py, cdblock.py

Nothing was edited. No SOFiSTiK run was started. Local runs: `dat_lint.py` on 26016_check_v2.dat took 4.7 s and gave PASS. `mutation_drill.py` on the same file took 105 s and gave PASS (50 MB of mutants). `scorecard.ledger_agreed()` was run on a test `LEDGER.md`.

## What checks out (no finding)
- **MCP tool calls.** Every MCP tool name and parameter name/type used in the three skills matches server.py:
  `run_calculation(dat_path, timeout_minutes)`, `get_job_result(job_id, wait_seconds)`, `write_dat_file(path, content, overwrite)`,
  `read_text_file(path, start_line, max_lines)`, `list_folder(path, pattern, max_entries)`, `check_cdb_lock(cdb_path)`,
  `cdb_envelope(cdb_path, load_cases, what)`, `cdb_beam_forces(..., structural_lines, max_rows)`,
  `cdb_node_results(load_case, nodes)`, `search_manuals(query, manuals, max_hits)`, `read_manual_page(manual, page)` and the others.
- **report_check values.** Every status the skills use (running, attention, failed, passed) is in dashboard.py:52 CHECK_STATUSES. Every finding level (warn, fail) is in FINDING_LEVELS.
- **Return fields.** The fields the decision tables key on all exist:
  - `left_running`, `server_warnings`, `programs_in_input`, `seconds`, `peak_ram_mb`: solver.py:1083-1149
  - `erg_messages`, `messages_truncated`, `unfinished_programs`, `status`: messages.py:149-196
  - `load_cases_found/_missing/_without_data`, `superposition_load_cases`, `eigen_load_cases_skipped`: results.py:636-650
  - `exists/locked/holders[].kind`: cdblock.py:227-238
  - `calculating_here`: server.py:516
  - `processes.module`, `servers[].jobs`, `resources.ram_total_gb/ram_used_gb`, `status_folder`: dashboard.py:494-696
  - `total_lines/to_line`: server.py:236
- **Script CLIs.** Every script call in the skills matches its argparse CLI. Every script uses exit codes 0/1/2/3. The input JSON names line up: `W/raw/load_cases.json`, `W/expected.json`, `W/raw/selftest_results.json` with keys g0_*, `W/member_results.json`, `W/checked_members.json`, `W/raw/env_uls_beam.json`, `W/raw/overview.json`. mutation_drill children do not write into W/proofs.jsonl (checked).

---

## Findings

### B01 BLOCKER: the 3.5 MB 26016 .dat has no executable route to the PC
- **Where:** AUTH:188-191 (T2), AUTH:166 (S1-B), RUN:231-232 (F8 T2).
- **Problem:** 26016_check_v2.dat is 77,380 lines and 3,691,530 bytes. That makes it route T2. In T2 the skill sends nothing and needs `pc_copy_ready: yes`, meaning "the lead placed F at <dat>". The skills give the lead no channel for this. The only PC write tool is `write_dat_file(content=...)`, and a 3.6 MB string is about 1.2 M tokens in one tool argument. Neither Opus nor Haiku can send that.
- **The order also cannot work.** F carries a run stamp that S1 creates (run_id contains UTC MMDDHHMM). So the lead can only copy F after S2. But if `<stem>.dat` already exists when S1 step 5 runs, it STOPs S-BRIEF (AUTH:166). The only way through is a STOP plus a `resume:` instruction that the lead must write in free text.
- **Every fix has the same problem.** RUN F8 with T2 is STOP S-TRANSFER on every fix.
- **Fix (cheapest robust):** make the PC-resident approved file the payload and send only a small master .dat over T1:
  ```
  $ src: skill T-MASTER
  #INCLUDE C:\<PC work folder>\src\26016_check_v2.dat
  <T-STAMP block>
  ```
  - This is about 10 lines, so it is always T1.
  - solver.py allows and scans #INCLUDE inside readable folders (solver.py:16-20, 946-977).
  - The .cdb takes the master's name, so it is fresh. The stamp LC still proves run identity.
  - The "no #INCLUDE" rule (AUTH:253, 314, gotcha `incl` AUTH:288) comes from the check-only-.dat incident (error 10127). It is not about includes as such. Narrow it to "only the T-MASTER include lines, absolute PC paths, full chain".
  - **Identity of the PC copy:** the cleanest proof is a 5-line server addition, `sha256` in `list_folder` rows or a `file_sha256(path)` tool. Bash then compares it with `sha256sum` of the cloud copy that was linted.
  - Until that exists, use: `list_folder` size_kb, plus read_text_file of lines 1-5 and the last 10, plus 20 seeded random single lines. Compare all of them with the cloud copy in one Bash script. Put that script in tools/ so Haiku does not hand-compare.
  - The server also re-hashes included inputs during the run and flags `check: input changed during run` (solver.py:1124-1129).

### B02 BLOCKER (verify first): the run dies when the server process ends, but the skills assume it keeps running across Haiku sessions
- **Where:**
  - RUN:244: `run_live: yes (S-SLOW, S-POLLCAP, S-LINK: left alone)`
  - RUN:169: "S-POLLCAP ... the run stays running; a fresh agent resumes from S0"
  - RUN:175: S-SLOW "The run stays running"
- **Evidence:**
  - solver.py:22-24: each run's job object is closed "killing what is left, when the server process ends".
  - solver.py `_cleanup_at_exit` (atexit, after line 700): kills every `_ACTIVE` sps.
  - dashboard.py:569: "Claude or the server closed while it ran".
  - server.py:452: "Jobs are forgotten when Claude restarts".
  - The skills' own history at RUN:12-13: "18 Oct: a restart killed a run".
- **Problem:** if `mcp__remote-devices__sofistik__*` starts one server process per Claude session, then every hand-back during S4 kills the 26016 run: S-SLOW, S-POLLCAP and S-LINK, and also a context-full or crashed Haiku session. The 26016 chain estimate is 161 min, which is about 193 polls of 50 s, and the poll cap is 200 (RUN:169). Any slowdown at near-full RAM ("2-3 times", RUN:292) hits S-POLLCAP and so ends the session.
- **Fix:**
  - Confirm how remote-devices hosts the server: one persistent process shared by sessions, or one process per session. Write the answer into RUN as a stated precondition.
  - If it is per session, Haiku must not end the session while `run_live` could be yes. The poll cap must then be "hand back, but keep the session open". Better still, start long runs from a persistent host (Claude Desktop on the PC), which matches the 18 Oct lesson.

### B03 MAJOR: the skill's own timeout kills the run at about 3x the estimate (a self-inflicted stop)
- **Where:** RUN:116-119 (`cap_min = ceil(3e/10)*10`), RUN:156-157 (`run_calculation(dat_path, timeout_minutes=<timeout_cap_min>)`), RUN:175 (S-SLOW at `slow_after_s = 3e*60`).
- **Evidence:**
  - server.py:326-328: the limit is `min(timeout_minutes, settings)`.
  - solver.py:843-845: on timeout `_kill_tree(proc)`.
  - solver.py:1113-1117: status `timed out`, "The calculation was killed".
- **Problem:**
  - This contradicts NEVER-1, "a stopped run costs hours". The stop happens inside the server.
  - S-SLOW hands back at 3e and says the run "stays running". The server then kills it within the next 10 min (cap ≥ 3e, rounded up).
  - Table E is largely "(inferred)" (RUN:283-291), and the "unknown block" row is only 30 min. So a correct 26016 BDK run can be killed and leave a lock inside the .cdb (S-KILLED).
- **Fix:**
  - Never pass `timeout_minutes` for project runs. Pass it only for the canary (10). Keep `TIMEOUT_SHORT` (settings limit ≥ 2e) as the only time gate.
  - Make S-SLOW a NOTE plus a report_check to Wing, not an end of polling.

### B04 MAJOR (confirms F-EX1): rule W does not wait
- **Where:** RUN:141-143 (rule W); also RUN:88 and RUN:166 (Rule J calls).
- **Evidence:**
  - server.py:446-452: without job_id, `get_job_result` reads `_calcs.get(_latest["id"])`, which is per process.
  - A busy run started by another Claude process (or by Wing) is never in this process's `_latest`.
  - If this server has never run anything, the answer is `{"error": "No job (no calculation started yet)..."}` at once, and rule W then STOPs S-BUSY on the first try.
  - If it ran the canary, `_latest` is the finished canary job. `_wait` returns its old result at once (server.py:140-148). The 6 "waits" then take about 1 s in total, and gate_waits > 3 STOPs S-BUSY within about a minute.
- **Problem:** in neither case does the skill wait the intended about 5 min. Failing closed is safe, but the wait is fiction, and Haiku may read the canary's `ok` answer as being about the busy run.
- **Fix:** delete the wait. Rule W becomes: NOTE what is busy (dashboard `servers[].jobs[].dat`, `elapsed_s`, `processes.module`) and STOP S-BUSY at once ("PC time is Wing's call"). If a wait is truly wanted, use a Bash `python3 -I -c "import time;time.sleep(240)"` with `timeout: 300000`, capped at 3. Never use `get_job_result()` without a job_id.

### B05 MAJOR: T1 transfer verification cannot see a transcription slip in the middle of the file
- **Where:** AUTH:189-193, AUTH:212; RUN:105 and RUN:125 (tail only); RUN:231 (F8).
- **Problem:** Haiku re-types up to 400 lines of `cat F` as the `content` argument. The checks are line 1, `total_lines` N/N+1 and the tail stamp. A dropped digit or swapped line in lines 2..N-7 passes. Lint and the drill ran on the cloud F, not on the PC copy.
- **Fix:** after every write, read the whole file back. Use `read_text_file(path=<dat>, start_line=1, max_lines=2000)` (T1 is ≤ 400 lines, so one page) and save it. Then run Bash: `python3 -I -c` to strip the `"<n>: "` prefixes from `text` and `diff` against F. Any difference → STOP S-TRANSFER. Better: put this in a tools/ script, `transfer_check.py <F> <saved read>`.

### B06 MAJOR: hand-saving big tool results (P-SAVE) is expensive, and copying numbers by hand is a fabrication risk the receipts cannot catch
- **Where:** RES:57-59 (P-SAVE "Write the tool result ... exactly as returned"), RES:95-97 (P-RECEIPT), README:12-18.
- **Estimated sizes for 26016:**

  | Saved file | Source call | Rough size |
  |---|---|---|
  | `load_cases.json` | `cdb_load_cases("1-999,9990")`, about 300 rows × about 300 B | about 90 KB, about 30k output tokens |
  | `env_uls_beam` | 47 LCs; `per_lc` holds 6 components × max/min × concurrent values | about 100 KB, about 30k tokens |
  | G7 forces | up to 20 × `cdb_beam_forces`, about 10-20 KB each | up to about 70k tokens |
  | AQB pages (after calibration) | `cdb_read_key` 500 × CBEAM_DES records | hundreds of KB per page × 47 LCs: impossible by hand |

- **Problem:**
  - Claude Code's MCP output limit (default about 25k tokens) may cut results before Haiku sees them. Whether the harness saves MCP output to a file (the `cp` branch) is not verified.
  - `receipts.py add` only proves the value is in the raw file (README:181), and Haiku wrote that file. So a miscopied number in the raw file gets a valid receipt. Only the lead's 5-receipt re-call audit catches it, and that is a sample.
- **Fix (cheapest robust):**
  1. Never hand-type a result larger than about 4 KB. If the harness did not save it to a file, narrow the call: fewer LCs per call, `ends_only=true`, `beams=` ranges. If it still does not fit, STOP S-SAVE.
  2. Server addition (a few lines in `_cdb_call`): add `"sha256"` of the canonical JSON of each result, and have a tools/ check (`save_check.py <file>`) recompute it. A hand-saved copy then either matches byte for byte or STOPs. This closes the fabrication hole for every saved file.
  3. Cut `cdb_load_cases` to the LCs the scripts need: the basic LCs from expected.json, the combinations and 9990.

### B07 MAJOR: `job_id` is empty for any run that ends within about 40 s, and RES then STOPs S0-LEDGER
- **Where:** RUN:158 ("job_id (if any)"); RES:102-104 and RES:131 (`job_id` is a required key, empty → STOP S0-LEDGER); RES:145.
- **Evidence:** server.py:376-378: `return await _wait(job)` returns `job["result"]` when done. The solver summary (solver.py:1138-1149) has no `job_id`.
- **Problem:** small models, re-runs and anything under WAIT_S=40 s can never get through RES S0.
- **Fix:** in RES S0, allow `job_id` to be empty. In S6a, when job_id is empty, skip step 1 and let `read_calculation_messages` decide, as it already does for `No job`.

### B08 MAJOR: STOP/resume does not work between the skills (no exit after a RES STOP)
- **Where:**
  - RES:40-41: the STOP line is `STOP <code> | ...` with no UTC/state prefix, unlike AUTH:219 and RUN:236.
  - RES:128: "last step line starts with STOP → S9 waiting".
  - RES:357: S9 then appends `S9 | HANDBACK | ... | next=END`.
  - RES:100-104: header `next_state` is never rewritten after each state; only S9 sets END.
- **Problem:**
  - After any RES STOP, the last line is a HANDBACK line, not a STOP line. On the next session, RES S0 finds `next_state` END or S6a and either has no matching row (S-UNKNOWN) or restarts from S6a.
  - RUN and AUTH hit "anything else → S-UNKNOWN" (RUN:96, AUTH:131).
  - RES has no `resume: <code> <instruction>` row. AUTH:127 and RUN:92 have one. So after the lead fixes the cause, for example a calibration that ends S7-UNCALIBRATED (which every run hits today: README:323), only a hand-edit of the ledger restarts RES.
  - "starts with STOP" is also literally false for the AUTH/RUN format, whose lines start with the timestamp. Haiku may read it literally.
- **Fix:**
  - One shared STOP line format: `<UTC> | <state> | STOP <code> | ...`.
  - The resume test becomes "the newest line whose TAG is STOP or HANDBACK".
  - RES rewrites `next_state` after each state.
  - S9 does not append after a STOP; it only reports.
  - Add the same `resume:` row to RES S0.

### B09 MAJOR: GREEN is unreachable because scorecard does not find `LEDGER.md`
- **Where:** tools/scorecard.py:37 `glob(os.path.join(workdir, "*ledger*"))`; RES:324 `scorecard.py W` without `--ledger`; AUTH:34 names the file `W/LEDGER.md`.
- **Evidence:** Linux glob is case-sensitive. On a test dir that holds only `LEDGER.md` with `assumptions_agreed: yes`, `ledger_agreed()` returned `(False, None)`.
- **Problem:** every result is at best AMBER "no ledger found", even after Wing agrees.
- **Fix:** RES S8 step 8 calls `scorecard.py W --ledger W/LEDGER.md`. Also make the glob case-insensitive.

### B10 MAJOR (latent, after calibration): RES may not call the tool its README tells it to use, and the AQB read volume exceeds its own cap
- **Where:** RES:45-47 (allowed tools; `cdb_read_key` is missing, "Nothing else") vs README:404, 449-452 (S7b uses `cdb_read_key`); RES:81 (P-PAGECAP 30) vs README:435-438 (AQB: "several 500-record pages per LC, times 47 LCs").
- **Problem:** after calibration, Haiku must either break the allow-list or STOP. AQB extraction needs over 47 reads, each too big to hand-save (B06).
- **Fix:**
  - Add `cdb_read_key` to the RES allow-list.
  - Before calibrating AQB, decide on a bulk reader: a server-side `cdb_design_utilisation(lc range)` returning `{member, eta}` only. Until then, AQB stays UNCALIBRATED by design.

### B11 MAJOR (F-EX4: half confirmed, half refuted)
- **Where:** AUTH:14-16 (NEVER 4: never change a "load-case or member list") vs AUTH:168 (S1-B rewrites `member_lcs` to the 26016 set and ESCALATEs). RES:18 (NEVER 7) and RES:102-131 have no check on `member_lcs`.
- **Problem:**
  - AUTH contradicts itself: it changes a brief's member-check set on its own.
  - The lead's claim that RES STOPs on 101-154 is **refuted**: no table in RES tests the value.
    - If `member_lcs` reaches RES as `101-154` (hand-edited ledger, or a non-26016 project), S6e runs the envelope over the EQU cases 131-134. R6 "passes" because expected equals got, and the Nmin receipt can come from EQU.
    - member_check takes its own `member_lcs` from the .dat BDK lists (member_check.py:241), so `lc_outside_set` does not catch it either.
- **Fix:**
  - AUTH S1-B: a `member_lcs` mismatch → STOP S-BRIEF (no rewrite).
  - RES S0: one Bash line that expands `member_lcs`, `equ_lcs`, `sls_lcs` and 4101-4499 and prints `OVERLAP` if they intersect → STOP S0-LEDGER.
  - Both skills then handle the same situation the same way.

### B12 MAJOR (confirms F-EX3): truncated reads with no `truncated` flag
- **Where:** RES:61-81 (P-READ sends a result to P-PAGE only on `truncated = true`); RUN:110-111 (`run_history.json` read with max_lines 2000).
- **Evidence:**
  - results.py:654-691: `cdb_read_key` returns at most `max_records` (≤500, server.py:818) records with `record_count`, and no `truncated` key.
  - server.py:236: `read_text_file` returns `to_line < total_lines` and no `truncated` key.
  - dashboard.py:312, 332-336: `run_history.json` is written oldest first, up to 300 runs, with `indent=1`. That is thousands of lines, and the newest runs are at the END.
- **Problem:**
  - RUN S3 step 8 reads lines 1-2000, which are the oldest runs, and misses the newest one, so the estimate basis is wrong (and feeds B03's cap). It also costs about 20-30k tokens.
  - For read_key, `member_check.py collect` refuses incomplete page sets (README:458), which saves BDK/AQB. P-READ itself would still save a first page as "complete".
- **Fix:**
  - P-READ gets two new rows: `record_count` > number of `records` → page with `skip`; `to_line` < `total_lines` → page.
  - RUN S3 step 8: read from `start_line = total_lines - 400`, or drop the step and use the dashboard's `estimate` (dashboard.py:222).

### B13 MAJOR: "No job" means a dead run in RUN but "go on" in RES; a clean finished run gets declared lost
- **Where:** RUN:179 (S4-P: `No job`, module null → STOP S-LOST), RUN:194 (S5 step 1 `No job` → S-LOST) vs RES:155 (`No job` → go on, the protocol decides).
- **Problem:** after a server restart (jobs forgotten, server.py:452), RUN declares a run that finished `ok` while nobody polled as "died (lock likely)". The lead has to step in for nothing.
- **Fix:** in RUN, on `No job` with module null, call `read_calculation_messages(<dat>)` and `list_folder(<stem>.mcp-running)`. If the .prt is fresh and finished, go to S5 with that status. A truly dead run gives status `not finished`, which is S-UNFINISHED.

### B14 MINOR: AUTH resume after a write but before verification is a dead end
- **Where:** AUTH:125-130, AUTH:189-190.
- **Problem:** if the crash comes after `RESULT write_dat_file` (whose line carries `next=S2`), resume restarts S2 at step 1. Step 11 with `overwrite=false` → `already exists` → STOP S-BRIEF, although the file is ours and correct.
- **Fix:** add an S0-B row: last line `RESULT write_dat_file` → go to S2 step 12 (verify; B05 makes that verification complete).

### B15 MINOR: mutation_drill runs close to the Bash timeout and without `--expected`
- **Where:** RES:206.
- **Evidence:** 105 s on this container. Bash's default timeout is 120 s. Without a JSON answer the result is "no JSON printed" → STOP S-UNKNOWN. Without `--expected`, the 4 equilibrium_check mutants are skipped (help text).
- **Fix:** RES:206 becomes `python3 -I T/mutation_drill.py <dat_local> --expected <expected_json> --workdir W` with Bash `timeout: 600000`. Point `W/mutants` (50 MB per drill) to a scratch folder if W is a synced project folder.

### B16 MINOR: the instability-word check differs between RUN and RES
- **Where:** RES:149 greps the whole `g2_messages.json`, including `input_before` CADINP echo lines and file paths. RUN:199 checks only message `text`.
- **Problem:** a comment like `$ ... instability ...` echoed in `input_before` STOPs RES (S6-HARDWARN) after RUN passed the same run.
- **Fix:** RES uses a python one-liner over `messages[].text` and `erg_messages[].text` only, the same as RUN.

### B17 MINOR: more than 200 messages is a hard dead end in RES
- **Where:** RES:159; messages.py:92 and 153 (`max_messages=200`).
- **Problem:** a large BDK run with many warnings always STOPs S6-MSGTRUNC, and RES has no other route.
- **Fix:** the lead decides. Document it in the STOP meaning and offer a paged `read_text_file` of the .prt as the alternative route.

### B18 MINOR: S6b step 6 one-liner does not unwrap
- **Where:** RES:177.
- **Problem:** `d['rows']` assumes the bare shape. A harness-saved file (P-SAVE `cp` branch) is in MCP content shape → TypeError → no table row.
- **Fix:** use the script loader (`_common.unwrap`), or add the title read to `equilibrium_check.py`.

### B19 MINOR: no lock row for a .cdb held by an invisible program
- **Where:** RUN:129-134.
- **Problem:** `locked: true` with empty holders and `open_elsewhere: true` (cdblock.py:234-238) falls to S-UNKNOWN.
- **Fix:** add a row: `open_elsewhere` true → STOP S-WINDOW, with `advice` quoted.

### B20 MINOR: script outcomes with no table row
- **Where:** RES:95-97, RES:290-304.
- **Problem:**
  - `receipts.py add` exit 1 (value not in the raw file) and exit 3 have no row.
  - `pick` can return picks with `lc: null` (member_check.py:376 and 428, `G7_pick_lc` ESCALATE, exit 2). Step 2a would then call `cdb_beam_forces(load_case=null)`.
- **Fix:** receipts exit ≠ 0 → STOP S-RECEIPT. A pick with null `lc` → hand exit-3 path ("not hand-checked"), with no call.

### B21 MINOR: ledger format gaps
- **Where:** RUN:218, RUN:148, RUN:49.
- **Problem:**
  - `fix_count[fp]` is a per-fingerprint counter, but the header is plain `key: value` with no format given.
  - `CANARY ok` uses a tag that is not in the tag list.
  - `gate_waits` is never reset between attempts.
- **Fix:** write `fix_count: <fp>=<n>,<fp>=<n>`, add CANARY to the tag list, and reset `gate_waits` at the FIX line.

### B22 MINOR: the dashboard status after a STOP differs by skill
- **Where:** AUTH:221 and RUN:238 (`attention`, level warn) vs RES:41 (`failed`, level fail).
- **Problem:** the same kind of STOP shows differently to Wing.
- **Fix:** use one rule: a STOP is `attention`, and only a RED scorecard is `failed`.

### B23 MINOR: the RAM gate may never pass for 26016
- **Where:** RUN:116 (`free >= estimate_ram_gb + min_free_ram_gb` = 17 + 4 GB).
- **Problem:** if the PC's idle free RAM is under 21 GB, every gate STOPs S-BUSY. The 17 GB in table E is "at full RAM" (RUN:286), so the PC's total may be close to that.
- **Fix:** record the PC's `ram_total_gb` in table E. Set `estimate_ram_gb` from `run_history` `peak_ram_mb`.

### B24 MINOR: continuing after S-SLOW / S-POLLCAP needs free text from the lead
- **Where:** RUN:92, RUN:169.
- **Problem:** "a fresh agent resumes from S0", but S0-B on a STOP line only hands it back again unless the brief has `resume:`.
- **Fix:** give the exact resume instruction in the hand-back, e.g. `resume: S-POLLCAP continue poll job_id=<id>`, and add a matching S0-B row.

### B25 MINOR: 50 s waits through the remote relay are not verified
- **Where:** RUN:168 (`wait_seconds=50`); server.py:70 notes "Claude Desktop gives a tool call about 60 s".
- **Problem:** the remote-devices relay timeout is unknown. If it is under about 55 s, every poll fails, link_fails reaches 3 and the result is S-LINK (and B02 applies).
- **Fix:** measure the relay timeout once, then set `wait_seconds` to 30 if it is below 60 s.

### B26 MINOR: auto-clear lets the server end processes on the skill's behalf
- **Where:** RUN:133 ("orphan and auto_clear true → lock OK").
- **Problem:** `run_calculation` then kills the orphan programs and runs Clean Locks inside the .cdb (solver.py:1017-1021). The server guards are sound: open-file evidence plus a start-time match, cdblock.py:136-170 and 241-250. Still, NEVER-1 says "never kill a process" while the skill knowingly triggers a kill through the server.
- **Fix:** say so explicitly: "an orphan the server ends is allowed; any other kind is not". Or STOP S-LOCK for orphans as well, and let Wing decide.

---

## Practical limits (question 7), summary
- **Getting the .dat to the PC.** `write_dat_file` takes the whole text as one argument. 400 lines is about 20 KB and about 6-8k output tokens, which is fine. 3.5 MB is impossible, so B01's master .dat is required.
- **Hand-saving results.** Through the S6-S7 states, hand-saving costs about 130k+ output tokens of copied JSON before calibration (B06), and it grows to MBs after AQB calibration. Every copied byte is a fabrication or miscopy risk that receipts cannot detect, because the receipt checks against the copied file.
- **Cheapest robust package:**
  1. T-MASTER with #INCLUDE of PC-resident sources, plus a sha256 field from the server (B01).
  2. A sha256 in every cdb_* result, plus `save_check.py`, plus "never hand-type > 4 KB" (B06).
  3. Remove `timeout_minutes` from project runs (B03).
  4. Confirm the server's lifetime on the PC before any long run (B02).

---

## Re-verification (Reviewer B, against core v2, 18 Oct)

**Read:** AUTH = sofistik-cadinp-author/SKILL.md (361 lines); RUN = sofistik-run-and-fix/SKILL.md (395); RES = sofistik-results-proof/SKILL.md (450); 12_TRIAGE.md, 13_SHARED_BLOCKS.md, tools/README.md, calibration.json; every script's `--help`.

**Executed locally (no SOFiSTiK run):**
- Built a 26016 master: `#INCLUDE 26016_check_v2.dat` plus T-STAMP.
- expand_master: EXPANDED 77389, PASS, 0.4 s.
- Gotcha greps on X: only the known `semi` hits; MODEL-OK; lc9990 = 1.
- `dat_lint --sources --uls`: PASS, 5.3 s.
- transfer_check on simulated read-backs:
  - TRANSFER_OK on clean copies.
  - DIFF and exit 1 on a changed master line.
- run_history_tail on a synthetic tail: correct newest run found.
- P-MERGE (rows and env) and the R6 script on synthetic parts: work. R6 FAILs 131.
- AUTH S1 step 6 one-liner: tested (see N1).

### Status of B01-B26
| ID | Status | Evidence |
|---|---|---|
| B01 3.5 MB transfer | PARTLY | Master + #INCLUDE: AUTH:187-209, T-MASTER AUTH:277-291; tools work on the real file. **Still open:** the approved file must already be in `pc_folder` (AUTH:158, 179). The way it gets there is still undefined (the lead's job). Any fix inside a source above 400 lines -> STOP S-TRANSFER (RUN:277). |
| B02 server lifetime | PARTLY | S-CALIB gate in RUN:100-101, 179; calibration.json `server_lifetime` UNCALIBRATED. Two problems: the calibration "how" uses a canary (about 10 s), which answers **without** a job_id (WAIT_S 40, server.py:70, 376), so the test as written cannot run (N7). S-CALIB comes before the canary (N3). |
| B03 timeout kill | CLOSED | RUN:17, 102-103, 198 (no timeout_minutes); 3x is a NOTE only (RUN:219). Canary keeps 10 (RUN:187). |
| B04 rule W | CLOSED | Rule W removed; Busy PC = STOP at once (RUN:74-78, 167, 170). Only remaining no-id use: none (RUN:128 goes through Rule NJ). |
| B05 middle-of-file slips | CLOSED for the master | Full read-back + transfer_check + line count: AUTH:199-200, 208, 231-232; RUN:141-143, 166. Included files: only sampled windows (100 of 77,380 lines). Accepted per L7. |
| B06 hand-saving | PARTLY | 20 KB / 200-row cap (Block A, H; RES:106-111); P-GROUPS/P-MERGE; receipts `--path` and lead re-call. **Still open:** see N6. The S7a window size breaks the cap, and the AQB/PRT volumes are impossible. There is still no integrity hash on hand-saved files. |
| B07 inline job_id | CLOSED | RUN:97, 199, 205; RES:185. |
| B08 STOP/resume | PARTLY | Blocks B/C/D are verbatim in all three. RES no longer writes after a STOP (RES:388-392). `next_state` is set per state (RES:40). **New dead ends:** N4, N5, N8. |
| B09 scorecard ledger | CLOSED | scorecard.py:41 matches the basename case-insensitively; RES:372 passes `--ledger W/LEDGER.md`. |
| B10 cdb_read_key / AQB volume | PARTLY | Allowed (RES:47). Volume: RES:313-315 (`max_records=10`, cap 300 reads) vs about 10^4 AQB records per LC × 47 LCs -> S7b cannot finish on 26016 (N6). |
| B11 member_lcs | CLOSED | AUTH:176-177 STOP S-CONFIRM; RES:257-273 R6 script FAILs on EQU/SLS/eigen/MAXIMA (tested). |
| B12 truncation | CLOSED | Block F in RUN:80-84 and RES:80-84; run_history tail via run_history_tail (RUN:148-151, tested). |
| B13 "No job" | CLOSED (rule) | Block G is identical in RUN and RES. **But** what it recovers cannot pass RUN S5 (N2). |
| B14 resume after a write RESULT | PARTLY | AUTH:130 covers a crash. A resume after a STOP in S2 still hits `already exists` (N4). |
| B15 drill timeout / --expected | CLOSED | RES:247. |
| B16 hard-warning scan | CLOSED | RES:189 (text fields only, unwrap). |
| B17 more than 200 messages | PARTLY | Route PRT, RES:206-208: Haiku hand-saves the whole .prt in 200-line pages, up to 150 pages (about 30k lines, about 1-2 MB typed). Correct, but very expensive. |
| B18 unwrap in S6b | CLOSED | RES:226. |
| B19 open_elsewhere | CLOSED | RUN:171, 173; RES:197. |
| B20 receipts / null lc | CLOSED | RES:130, 337, 354. |
| B21 ledger format | CLOSED | RUN:51, 260; gate_waits removed; canary logged as PASS (RUN:188). |
| B22 dashboard after STOP | CLOSED | Block D, step 2 in all three. |
| B23 RAM gate | PARTLY | Peak from history (RUN:153). With no history (every new stem `_v3`, `_v4` is a new file name, so "same file" never matches), the gate is still 17 + 4 GB from table E. |
| B24 resume after POLLCAP | CLOSED | RUN:131, 210, 310. |
| B25 relay timeout | CLOSED (as a note) | RUN:213-214. |
| B26 server orphan clean-up | CLOSED | Block A (all three). |

### Contract re-check
- **MCP calls: all match server.py.** No mismatches found:
  - AUTH: read_text_file, list_folder, write_dat_file, search_examples, report_check, sofistik_status.
  - RUN: `run_calculation(dat_path)`; `run_calculation(dat_path, timeout_minutes=10)`; `get_job_result(job_id, wait_seconds)`; check_cdb_lock, read_calculation_messages, cdb_load_cases; `search_manuals(query, manuals, max_hits)`; `read_manual_page(manual, page)`; dashboard_status.
  - RES: `cdb_node_results(load_case, nodes)`, cdb_support_reactions, `cdb_beam_forces(beams | structural_lines, ends_only, max_rows)`, `cdb_envelope(load_cases, what)`, cdb_overview, `cdb_read_key(kwh, kwl, class_name, max_records, skip)`.
  - Return fields keyed on all exist: `finished` (messages.py:155, copied at :167), `estimate.finish_at` (dashboard.py:373), `open_elsewhere` (cdblock.py:237), `total_lines/to_line`, `record_count`.
- **Script CLIs: all match their argparse.** No mismatches found:
  - `expand_master <M> <X> <sources>`, `transfer_check <raw_dir> <sources>`, `run_history_tail <tail> <dat_name>`
  - `dat_lint --sources --uls`, `combo_check --expected [--families]`, `mutation_drill --expected`, `holding_down --sw-lc`, `scorecard --ledger`
  - `receipts add --path --label`
  - `member_check alpha --buckling-lcs --beam-map --dat`, `pick --seed`, `hand --member --lc --extra-forces` (nargs +)
- **Shared blocks:** checked line by line with a script.
  - A, B and D are verbatim in all three skills.
  - C is verbatim only in RES. AUTH and RUN replaced rows 2 and 3 with their own rows. AUTH's "anything else" is STOP S-UNKNOWN instead of "go to header next_state" (this causes N8).
  - **E, F, G and H are missing entirely from AUTH.** 13_SHARED_BLOCKS.md:134 says both D1 skills carry them. Low impact (AUTH pages its reads itself), but the claim "same text in all three" is false: MINOR.

### Resume walks (one STOP per skill)
- **AUTH, STOP S-TRANSFER in S1** (an include is not on the PC). The lead copies the file and writes `resume: S1 because copied`. S0-B row 1 -> NOTE -> S1 -> list_folder finds no master yet -> OK.
- **AUTH, STOP S-TRANSFER in S2 after the master was written.** `resume: S2 because ...` -> S2 restarts at step 1 -> step 8 `write_dat_file(overwrite=false)` -> `already exists` -> STOP S-BRIEF. **Dead end (N4).** Resuming at S3 instead fails too: RUN:168 compares PC sizes and `modified` with the old S2 `pc sizes` NOTE, and nothing refreshes it after the lead re-copies a file. Only a new stem gets out.
- **RUN, STOP S-CALIB** (always for 26016: 161 min, RUN:353). The lead starts the run and writes `resume: S4 because poll job_id=<id>`.
  - S0-B row 1 -> S4 poll -> `get_job_result(<id>)`.
  - If the lead's job lives in another server process: `No job` -> Rule NJ -> STOP S-LINK while it runs. Once it has finished: recovered from the protocol -> S5.
  - S5 row "number of `programs_in_input` differs" -> `read_calculation_messages` has no `programs_in_input` (only `programs`) -> STOP S-UNKNOWN. **Dead end (N2).**
  - Also `canary_cdb` was never set (N3) -> RES S0 STOP S0-NOCANARY.
- **RES, STOP S7-UNCALIBRATED** (always today). `resume: S7a because calibration.json CALIBRATED` -> S0-A row 1 -> S7a. Works, but this session's G0 canary is skipped (N5). S7b then hits the page cap (N6).

### NEW findings
**N1 MAJOR: the AUTH S1 overlap one-liner always prints `OVERLAP`, so a literal reading STOPs every correct brief**
- **Where:** AUTH:148 prints `OVERLAP NONE` when there is no overlap (tested); AUTH:175 matches on `` `OVERLAP` ``.
- **Problem:** a Haiku that matches literally STOPs S-CONFIRM on every correct brief.
- **Fix:** print `NONE` alone, or match on `OVERLAP [`.

**N2 MAJOR: a result recovered from the protocol, or an `inline` resume, cannot pass RUN S5**
- **Where:** RUN:93-94 (Rule NJ step 5) and RUN:231 hand over a `read_calculation_messages` answer, which has no `programs_in_input`, `seconds`, `server_warnings` or `left_running` (messages.py:158-197).
- **Problem:** RUN:241 (programs count differs) -> STOP S-UNKNOWN. RUN:234 needs `seconds`.
- **Fix:** add an S5 row: answer from the protocol -> compare `len(programs)` (the programs that ran) with programs_expected. Skip the time ratio and NOTE "no seconds (recovered)".

**N3 MAJOR: the canary never runs for a long run, so RES always STOPs S0-NOCANARY on 26016**
- **Where:** RUN:179 (S-CALIB row) comes before the canary, which runs only after PASS (RUN:184). RES:175.
- **Problem:** while server_lifetime is UNCALIBRATED, every 26016 path ends in S0-NOCANARY unless the lead hand-edits `canary_cdb`.
- **Fix:** run the canary (10 s, allowed) when every row passes except LONG, then STOP S-CALIB.

**N4 MAJOR: AUTH S2 cannot be resumed after a STOP that follows the write**
- **Where:** AUTH:198, 227; RUN:168.
- **Problem:** the resume dead end walked above.
- **Fix:**
  - S2 step 8 row: `already exists` AND the ledger has `RESULT write_dat_file <dat>` for this run_id -> skip to step 9.
  - S2 step 12 always refreshes the `pc sizes` NOTE.
  - The hand-back `resume:` line names the step.

**N5 MAJOR: RES S0 applies the resume table before the canary, so G0 can be skipped**
- **Where:** RES:154, 164-169.
- **Problem:** "anything else -> Go to header next_state" (S6a), read literally, skips steps 3-6 (the canary). The scorecard then lacks canary_check and gives RED; or, with an old canary line in proofs.jsonl, G0 is never re-proved this session. The same happens after every `resume:`.
- **Fix:** "S0-A only decides the target state. Always do steps 3-6 and S0-B, except on the STOP row."

**N6 MAJOR: S7a/S7b read volume breaks the 20 KB NEVER and the page caps on a 26016-size model**
- **Where:** RES:290-293, 313-315, 121.
- **Problem:**
  - S7a windows of 100 beams with `ends_only`, `max_rows=201`, give about 200 rows × about 150 B = about 30 KB per hand-saved page. That breaks the shared NEVER (20 KB).
  - The 26016 beam count (311 BDK members + 122 AQB SLNs, ≥ 8 elements per span) gives an estimated 30-50 windows. That is about 1 MB typed, or S-PAGECAP at 40 calls if Haiku treats the beam map as "one read".
  - S7b AQB with `max_records=10` needs far more than 300 reads.
- **Fix:**
  - Windows of 60 beams (about 18 KB).
  - Make the cap per call series explicit.
  - Accept S7b AQB as STOP S-PAGECAP by design until a bulk reader exists. State it in the S7b table so it is not reported as a failure.

**N8 MAJOR: a new ledger can dead-end in AUTH S0**
- **Where:** AUTH:116 tells Haiku to append `S0 | READ | new ledger`, with no `next=` field. AUTH:132-135: no row matches, and "anything else" -> STOP S-UNKNOWN.
- **Problem:** v1's "none (new ledger) -> S1" row was removed. A literal Haiku STOPs at the start of every new pipeline.
- **Fix:** restore Block C's verbatim "anything else -> header next_state" (the template sets `next_state: S1`). Or show the line as `<UTC> | S0 | READ | new ledger | next=S1`.

**N7 MINOR: the server_lifetime calibration test cannot produce a job_id**
- **Where:** calibration.json `server_lifetime.how`.
- **Problem:** the selftest canary finishes inside 40 s, so it never returns a job_id.
- **Fix:** use a run that takes over 60 s (e.g. the canary with a LOOP of extra load cases, or `sofistik_status` evidence plus a 2-minute benchmark .dat).

**N9 MINOR: a stale `.mcp-running` file blocks every gate permanently**
- **Where:** RUN:167; RES:196.
- **Problem:** a stale file left by a power cut makes every gate STOP S-BUSY. Only a run start removes stale lock files (solver.py:780-790).
- **Fix:** read it with read_text_file. If `host` is this PC and `dashboard_status` shows no SOFiSTiK process, STOP S-LOCK "stale lock file, Wing deletes it" (a different code, so the lead knows).

**N10 MINOR: RUN S3 step 8 writes `T` inside a Python string**
- **Where:** RUN:147.
- **Problem:** `open('T/calibration.json')` keeps `T` literal inside the string. If not substituted -> FileNotFoundError -> no row -> S-UNKNOWN. Fails closed, but it is avoidable.
- **Fix:** pass the path as argv, like every other one-liner.

**N11 MINOR: RUN S5 says "job_id a number"**
- **Where:** RUN:230.
- **Problem:** job ids are `calc-xxxxxxxx`, so a literal reading matches no branch.
- **Fix:** write "any id other than `inline`".

**N12 MINOR: the job_id is unrecoverable after a lost run_calculation answer**
- **Where:** RUN:310.
- **Problem:** dashboard job entries carry no job id (dashboard.py:221), so `resume: S4 because poll job_id=<id>` cannot be filled.
- **Fix:** document that the only follow-up is to wait, then `resume: S5`, which goes through Rule NJ (needs N2).

**N13 MINOR: stale `xfer__p<k>` pages can give a false TRANSFER_BAD**
- **Where:** RUN:141-143.
- **Problem:** pages from an earlier, longer master stay in W/raw and are compared against the new master.
- **Fix:** `rm -f W/raw/xfer__p*__<stem>.dat.txt` before each read-back.

**N14 MINOR (design): M1 edits are dead**
- **Where:** AUTH:181.
- **Problem:** every 26016 parameter is a `STO#` in the source, so any brief that names an M1 value STOPs S-AUTHOR. It fails closed, but every engineering change now needs the lead to edit the source.
- **Fix:** say so in AUTH S1-A.

### Verdict
Closed: B03, B04, B07, B09, B11, B12, B13 (rule only), B15, B16, B18-B22, B24-B26. Partly closed: B01, B02, B05 (included files), B06, B08, B10, B14, B17, B23. Nothing is fully open. **New majors: N1, N2, N3, N4, N5, N6, N8.** No new blocker. The 26016 path still cannot run end to end without the lead stepping in at S-CALIB and hand-setting `canary_cdb`, and it still cannot finish S7b.
