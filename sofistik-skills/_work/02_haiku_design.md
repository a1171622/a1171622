# 02 - How to write the skills so Haiku finishes the SOFiSTiK chain by itself

Author: small-model instruction designer, 2026-10-18. Offline work only; no run was started.
Evidence tags: `[server.py:N]` = /mnt/project-files/sofistik-mcp/sofistik_mcp/server.py line N;
`[solver.py:N]`, `[messages.py:N]`, `[results.py:N]` likewise; `[README:N]` = sofistik-mcp/README.md;
`[mem:<file>:N]` = /tmp/claude/memory/team/silo/<file>; `[RUN_LOG]` = 26016/member-check/RUN_LOG.md;
`[v2.dat:N]` = 26016/member-check/run/26016_check_v2.dat. **INFERRED** marks anything not proven by a
file or a manual page.

---

## 0. The design in one paragraph

Haiku is good at following a table and bad at holding a long chain in its head, judging engineering
trade-offs, and noticing that it has drifted. So the skills turn the chain into **one global state
machine (states S0-S9) split across three skills by what Haiku is doing at that moment**: authoring
(offline, harmless), running (costly PC time, can leave locks), reading and checking (read-only). A
**run ledger** file is the only memory that crosses skills, sessions and agents: every state starts by
reading it and ends by appending to it. Every state has entry and exit tests, every branch is a
decision table keyed on an exact tool return field, every loop has a counter with a hard cap, and every
situation that needs judgement ends in a numbered **STOP code** that hands control back to the lead.
Haiku never writes CADINP it cannot cite: every line it adds carries a `$ src:` comment pointing to a
shipped example or manual page, and it may only edit inside marked editable regions of approved
templates.

---

## 1. Architecture: three stage skills sharing one state machine

### 1.1 Options considered

| Option | For | Against | Verdict |
|---|---|---|---|
| A. One "state machine" skill holding the whole chain | One trigger, one ledger, no hand-over between skills | 900+ lines once recipes, error tables and templates are in; Haiku loses the current state in a long body; every task loads everything | Rejected as the only skill |
| B. Three stage skills, each with its own local steps | Short bodies | Hand-over between skills is implicit; a resumed agent does not know where it is | Rejected |
| **C. Three stage skills that own consecutive ranges of ONE numbered state machine, joined by the ledger** | Each body stays short; the ledger's `next_state` names the skill to load, so resume is mechanical; the lead can dispatch any one stage | Shared rules must be duplicated in each skill (self-contained rule) | **Recommended** |

### 1.2 The split

| Skill | States | What Haiku does | Risk class | Tools allowed |
|---|---|---|---|---|
| `sofistik-cadinp-author` | S0, S1, S2 | Read the brief, set up the ledger, build the `.dat` from approved templates and STO# parameters, self-check it offline | Harmless (nothing runs) | `sofistik_status`, `list_folder`, `read_text_file`, `search_examples`, `search_manuals`, `read_manual_page`, `write_dat_file` |
| `sofistik-run-and-fix` | S0, S3, S4, S5 | Pre-flight gate, start the run, wait, classify errors, fix with a cited source, re-run (bounded) | Costly (PC time, RAM, `.cdb` locks) | above + `run_calculation`, `get_job_result`, `read_calculation_messages`, `check_cdb_lock`, `clear_cdb_lock` (gated), `dashboard_status`, `report_check` |
| `sofistik-results-and-checks` | S0, S6, S7, S8, S9 | Prove the results are valid (status, staleness, equilibrium), extract BDK / alpha_cr / AQB answers, post findings, run the report tool, hand back | Read-only | `cdb_*`, `read_text_file`, `read_calculation_messages`, `report_check`, `dashboard_status`, report tool via shell (if present) |

S0 (read ledger and decide where to resume) is copied into every skill, so any one of them can be
loaded cold.

Why this cut and not "one skill per chain step" (write / run / parse / read / check / report):
- Steps 2 and 3 of the brief (run, then parse errors, fix, re-run) are one loop: splitting them would
  force a skill switch inside a loop, which is where a small model loses state.
- The cut follows the **risk boundary**: only `sofistik-run-and-fix` can spend PC time or leave a lock.
  Its forbidden list and gate can therefore be strict without cluttering the other two.
- The run skill is the one most likely to be dispatched alone ("re-run v3 and fix errors"), and the
  results skill the one most likely to be re-run alone ("re-read the results after Wing's change").
- Wind loads and IDEA StatiCa stay out: memory marks the wind tool untested [mem:MEMORY.md:37] and the
  IDEA import needs Wing's sketches and SAF export choices [mem:MEMORY.md:35]. They can become a 4th
  delivery later; a `S2.x` hook ("optional generated load block") is enough for now.

### 1.3 Why Haiku must NOT author models from scratch (scope limit for skill 1)

The real chain file is 77,380 lines [v2.dat], built by concatenating four generator outputs unchanged
[v2.dat:1-5]. Haiku cannot pass that through `write_dat_file(content=...)`, and it should not try to
re-type a model export. Skill 1 therefore allows exactly three authoring moves:

| Move | Example | Allowed for Haiku? |
|---|---|---|
| M1 Change a STO# value inside an EDITABLE region of an approved parametric file | `STO#NPART 8` -> `10` | Yes, only if the line is not tagged `CONFIRM` and the brief names the new value |
| M2 Assemble a driver `.dat` from approved files (concatenate or `#INCLUDE`) in a fixed order | model -> unified loads -> BDK -> alpha_cr -> AQB | Yes, from the order table in the skill |
| M3 Add a small block copied from the skill's template library, filling `<<SLOTS>>` only | an extra `+PROG ASE urs:92nn` alpha_cr block for another PLC (the file itself says "Add any other PLC by copying a block" [v2.dat:77318]) | Yes, every added line carries a `$ src:` tag |
| M4 Write new records, new programs, new load generation, new geometry | anything else | **No: STOP S-AUTHOR (lead writes it)** |

How the big file is assembled is a decision for the lead (see open question Q2): by a shell copy
(`copy /b a.dat+b.dat out.dat` or a `py` script) when Haiku has a shell on NguyenPC3, or by a short
driver file with `#INCLUDE` lines (the server checks include files [README:197-200]). The `#INCLUDE`
spelling and its interaction with `+PROG` blocks must be verified with `search_examples "#INCLUDE"`
before the skill relies on it (**INFERRED**, not yet proven on this PC).

---

## 2. Control flow a small model can follow

### 2.1 Rules for writing the states

1. One state = one heading `## S4 Wait for the run`, then exactly four labelled parts in this order:
   **Enter if**, **Do**, **Exit to**, **Ledger line**. No prose paragraphs between them.
2. "Do" is a numbered list of single tool calls or single checks. One verb per step.
3. Every branch is a table whose first column is an exact value of a tool return field, copied
   verbatim from the server (e.g. `status` = `ok with warnings`), never a paraphrase.
4. The last row of every decision table is `anything else -> STOP S-UNKNOWN`. Haiku never improvises a
   branch.
5. Every loop names its counter, its cap and what happens at the cap.
6. The words "should", "consider", "if appropriate" are banned in skill bodies; use "must", "never",
   or a table.

### 2.2 The global state machine

| State | Skill | Purpose | Exit to |
|---|---|---|---|
| S0 | all | Read ledger, check server, decide resume point | state named in ledger `next_state`, or S1 if new |
| S1 | author | Brief -> run plan (which files, which LCs, estimate) | S2 |
| S2 | author | Build `.dat`, offline self-check (lint table) | S3 |
| S3 | run | Pre-flight gate (8 yes/no checks) | S4, or STOP |
| S4 | run | `run_calculation`, then wait with `get_job_result` | S5 |
| S5 | run | Classify status and messages; fix and loop to S3, or exit | S3 (fix), S6 (clean), STOP |
| S6 | results | Validity proof: status, `stale_results_warning`, equilibrium | S7, or STOP |
| S7 | results | Member-check extraction: BDK, alpha_cr, AQB | S8 |
| S8 | results | Findings to dashboard + report tool | S9 |
| S9 | results | Hand-back message to the lead in fixed format | END |

Snippet, as it would appear in `sofistik-run-and-fix/SKILL.md`:

```markdown
## S5 Classify the result

**Enter if:** the ledger's last line is `S4 RESULT` with a `status` value.

**Do:**
1. Read `status` from the run result. Look it up in table T5.
2. If the row says "fix": take the FIRST message in `erg_messages` whose `kind` is `error`.
   Build its fingerprint: `<program>#<number>` (e.g. `SOFILOAD#123`).
3. Add 1 to `fix_count[<fingerprint>]` in the ledger header. Add 1 to `runs_this_stage`.
4. If `fix_count[<fingerprint>]` > 3 -> STOP S-RETRY. If `runs_this_stage` > 6 -> STOP S-RETRY.
5. Go to "Fix one error" (section F). Then go to S3.

**T5 - status -> action**

| status (exact) | Action |
|---|---|
| `ok` | -> S6 |
| `ok with warnings` | Copy every warning (program, number, text) into the ledger. Warning numbers listed in table W as "harmless" -> S6. Any other warning -> STOP S-WARN |
| `errors` | fix (step 2) |
| `not finished` | STOP S-UNFINISHED (do NOT re-run: a program died; lead must look) |
| `timed out` / `stopped` | STOP S-LOCKRISK (a killed run can leave a lock inside the .cdb) |
| `check: input changed during run` | STOP S-CHANGED |
| `not run` | Read `reason`; look it up in table T3-NOTRUN |
| `no protocol` | STOP S-UNKNOWN |
| anything else | STOP S-UNKNOWN |

**Exit to:** S3 after a fix, S6 when clean.
**Ledger line:** `S5 | status=<..> | errors=<n> | warnings=<n> | fp=<fingerprint or -> | next=<S3|S6|STOP code>`
```

The status values in T5 are exactly the server's: `ok`, `ok with warnings`, `errors`, `not finished`,
`no protocol` [messages.py:187-196]; `stopped`, `timed out`, `check: input changed during run`
[solver.py:1110-1129]; `not run` with a `reason` [solver.py:937-1019]; `running` with `job_id`
[server.py:145-147]. BAD statuses that make results invalid are listed in [server.py:79].

### 2.3 Bounded retries (caps written as numbers)

| Loop | Counter | Cap | At the cap |
|---|---|---|---|
| Fix the same error fingerprint | `fix_count[fp]` | 3 attempts | STOP S-RETRY |
| Runs in one stage (all fixes) | `runs_this_stage` | 6 runs | STOP S-RETRY |
| Lookup for one keyword (search_examples + search_manuals) | `lookups[kw]` | 4 queries | STOP S-NOSOURCE |
| `get_job_result` polls | `polls` | none while `status` = `running` (a stop is worse than waiting); progress check every 10 polls; if `elapsed_s` > 3 x estimate -> STOP S-SLOW **and keep the job running** | |
| Pre-flight gate retries (waiting for RAM / another job) | `gate_waits` | 3 waits of 10 polls each on the other job | STOP S-BUSY |
| `.cdb` reads returning `running` | per call | 10 polls | STOP S-READSLOW |

Why 3 and 6: on 26016 the load file has 7,986 lines; a typical syntax error is fixed in one try when
the fix is copied from an example; a third try on the same fingerprint means Haiku is guessing. The
caps are policy, not measured (**INFERRED**); the lead may tune them.

### 2.4 STOP codes (hand back, never guess)

Each STOP writes the ledger line `STOP <code> | <one-line reason> | <evidence>` and then returns the
hand-back message (section 3.4). Haiku does nothing else after a STOP; in particular it never stops a
running job on the way out.

| Code | When | Why Haiku must not decide |
|---|---|---|
| S-AUTHOR | The task needs a move outside M1-M3 (new records, geometry, load generation) | Engineering + syntax beyond templates |
| S-CONFIRM | A value to change is tagged `CONFIRM` or `[legacy ...]`, or the brief does not give the new value | 10 CONFIRM items are open with Wing in the unified load file (grep count), e.g. vb, ce, CPU [v2.dat:63229-63245] |
| S-NOSOURCE | No example or manual page shows the syntax after 4 lookups | Prevents invented CADINP |
| S-RETRY | Fix caps reached | Haiku is guessing |
| S-WARN | A warning not in the harmless list W | Warnings can hide wrong engineering [README:219-221] |
| S-UNFINISHED | `not finished` | A program died; needs the `.prt` read by the lead |
| S-LOCKRISK | `timed out`, `stopped`, "WAIT FOR LOCK" that the server could not clear, `left_running` present | Wrong recovery costs a full rebuild [RUN_LOG rule 1] |
| S-BUSY | Another calculation runs, or RAM gate refuses, after 3 waits | PC time is Wing's call [mem:MEMORY.md:7] |
| S-SLOW | Elapsed > 3 x estimate | The 26016 BDK ran far over its 40-min estimate [RUN_LOG 01:41]; only the lead may decide to wait more |
| S-CHANGED | `check: input changed during run` | Results unreliable |
| S-STALE | Any `stale_results_warning` on a `.cdb` read [server.py:686-716] | Results may belong to another run |
| S-EQUIL | Reaction sum differs from applied load by > 1 % | Model or load error |
| S-SWAY | Any alpha_cr < 10 | Needs the TH2 re-run branch, a design decision [v2.dat:77300-77318] |
| S-FAIL | Any utilisation > 1.0 | Report only; Haiku never "fixes" a failure by editing sections or restraints |
| S-SERVER | Tool missing, "Server sofistik unavailable", 9999 INTERNAL ERROR | Seen on 2026-10-17 [mem:project-sofistik-benchmarks.md:9]; needs a fresh session |
| S-LINK | Connection or session looks lost during a run | A lost connection is not a stopped run [mem:MEMORY.md:15] |
| S-UNKNOWN | Any value not in a decision table | Catch-all |

---

## 3. The run ledger

### 3.1 Where and how

- File: `<work folder>\<stem>_LEDGER.md`, next to the `.dat` (e.g.
  `C:\Sofistik workflow\26016-member-check\v3\26016_check_v3_LEDGER.md`).
- Written with the client's own file tool (Write / Edit / shell). `write_dat_file` cannot be used: it
  only writes `.dat` files and makes a `.bak` copy on every overwrite [server.py:254-255, 288-290].
- **Mirror**: after every state change Haiku also calls `report_check` with the same `check` name, so
  the state is on the dashboard and in `<first work folder>\_dashboard\checks\<name>-<code>.json`
  [README:126-145]. If the ledger file cannot be written (no file tool), the mirror becomes the ledger:
  one `report_check` finding per ledger line, level `info`. Note: `dashboard_status` only shows the
  last 15 findings [server.py:856]; the full list stays in the JSON file, readable with
  `read_text_file`.
- Append only. Haiku never edits an earlier step line; it may only rewrite the HEADER block.

### 3.2 Format (line-oriented, not JSON)

Key = value lines and pipe-separated step lines, because a small model breaks nested JSON more often
than it breaks one line, and a half-written last line does not corrupt the rest (**INFERRED** from
general experience, not tested on Haiku here).

```markdown
# LEDGER 26016_check_v3
## HEADER (rewrite in place)
run_id: 26016-v3-20261018
brief: Full chain v3: model + unified loads + BDK + alpha_cr + AQB, Wing's change #NPART 10
lead_owner: lead thread "26016 member checks via SOFiSTiK MCP"
dat: C:\Sofistik workflow\26016-member-check\v3\26016_check_v3.dat
cdb: C:\Sofistik workflow\26016-member-check\v3\26016_check_v3.cdb
server_version: 1.3.0
code_basis: EN 1990/1993-1-1 + UK NA (assumed, not confirmed by Wing)
estimate_min: 55   (source: RUN_LOG measured times)
timeout_min: 360
state: S4
next_state: S4
job_id: calc-3fa2b1c0
runs_this_stage: 1
fix_count: SOFILOAD#123=1
check_name: 26016 member checks v3
## STEPS (append only)
2026-10-18T09:02Z | S0 | new run | next=S1
2026-10-18T09:05Z | S2 | EDIT | file=26016_buckling_all_bdk.dat line 31 | STO#NPART 8 -> 10 | src=brief | next=S2
2026-10-18T09:07Z | S2 | LINT | 12/12 pass | next=S3
2026-10-18T09:08Z | S3 | GATE | 8/8 yes | ram_free_gb=27.1 | running=none | next=S4
2026-10-18T09:08Z | S4 | INTENT | run_calculation dat=...v3.dat timeout_minutes=360
2026-10-18T09:09Z | S4 | RESULT | status=running | job_id=calc-3fa2b1c0
2026-10-18T09:16Z | S4 | POLL 10 | elapsed_s=430 | module=SOFILOAD | est_left=48 min
...
```

### 3.3 INTENT / RESULT pairs (the resume rule)

Before every call that changes something (`write_dat_file`, `run_calculation`, `clear_cdb_lock`,
`clone_cdb`), Haiku appends an `INTENT` line; after it, a `RESULT` line. On resume (S0):

| Last line | Meaning | Resume action |
|---|---|---|
| `INTENT run_calculation` with no `RESULT` | The run may be live | Do NOT call run_calculation. Call `get_job_result()` with no job_id (the latest calculation [server.py:449]); if "No job ...", call `list_folder(<folder>, "*.mcp-running")` [README:186-187] and `dashboard_status`; if a run is live -> wait as S4; if none -> STOP S-UNKNOWN |
| `INTENT write_dat_file` with no `RESULT` | Write may or may not have happened | `read_text_file(dat, 1, 20)` and compare the header lines; then continue |
| `RESULT status=running` | Polling was interrupted | `get_job_result(job_id)`; if "No job" (jobs are forgotten on restart [server.py:451]) -> same as row 1 |
| `STOP <code>` | Waiting for the lead | Do nothing until the lead's brief says how to continue |
| anything else | | Go to `next_state` |

### 3.4 Hand-back message (fixed format, so the lead can parse it)

```
HANDBACK
run_id: 26016-v3-20261018
end_state: S9 | STOP S-SWAY
ledger: C:\...\26016_check_v3_LEDGER.md
summary: 3 lines max
numbers: status=ok with warnings; errors=0; warnings=4; sum_PZ applied=-2310.4 kN stored=-2310.4 kN (0.0 %);
         alpha_cr min=7.8 (PLC 146, LC 9261); BDK max eta=1.12 (member B81, LC 118); AQB max=0.84
open: what the lead must decide (one line per item, each with evidence)
```

---

## 4. Tool-call recipes (exact names, parameters, return fields)

Tool names below are the server's function names; on the PC they appear prefixed, e.g.
`mcp__sofistik__run_calculation` (cloud threads see `mcp__remote-devices__sofistik__*`
[mem:project-sofistik-mcp.md:17]). The skill must tell Haiku to match by suffix.

### 4.1 S0: server check and version branch

```
sofistik_status()  ->  server_version, work_folders, run_timeout_minutes, max_parallel_runs,
                       min_free_ram_gb, auto_clear_cdb_locks, sofistik.sps, manual_index_shipped
```

| `server_version` | Consequence for the skill |
|---|---|
| `1.3.0` | Lock tools exist; no default time limit; up to `max_parallel_runs` runs [CHANGELOG 1.3.0] |
| `1.2.0` | **No `check_cdb_lock` / `clear_cdb_lock` / `clone_cdb`**; default time limit 60 min; one calculation at a time [mem:MEMORY.md:20]. A locked `.cdb` -> STOP S-LOCKRISK (no automatic recovery) |
| missing / tool error | STOP S-SERVER |

Also check that `dat` lies inside one of `work_folders`; if not -> STOP S-UNKNOWN (writing is refused
outside them [README:151-153]).

### 4.2 S3: the pre-flight gate (all eight must be "yes")

| # | Question | How to answer |
|---|---|---|
| G1 | Is the server version known and recorded? | S0 |
| G2 | Is no other calculation of THIS model running? | `dashboard_status` -> no entry for this `.dat`; `list_folder(folder, "<stem>.mcp-running")` empty |
| G3 | Is the PC free enough? | `dashboard_status` RAM: free >= estimate RAM + 4 GB. 26016 full chain needs ~17 GB in BDK [RUN_LOG], so with another big run live the answer is "no" |
| G4 | Is the `.cdb` not held by another program? | v1.3.0: `check_cdb_lock(cdb)`: `locked` false, or holders only of kind `orphan`. Any holder kind `run` or `window` -> "no". v1.2.0: skip, rely on run result |
| G5 | Does the `.dat` have a `$ src:` tag on every line Haiku added? | Ledger EDIT lines vs file |
| G6 | Is `timeout_minutes` >= 3 x estimate and >= 120? | Estimate from table E (below) |
| G7 | Has the lead approved this run (brief or ledger line `APPROVED`)? | Runs over 15 min need the lead's approval in the brief |
| G8 | Will this session stay open until the run ends? | Yes only if Haiku can keep polling; see the warning below |

Any "no" -> wait (G2/G3: poll the other job up to 3 x 10 polls) or STOP (S-BUSY, S-LOCKRISK,
S-UNKNOWN).

**Warning G8 (critical):** "If Claude or the server is closed during a run, SOFiSTiK is stopped too"
[README:187-189]. If Haiku runs in its own Claude session whose server instance started the run,
ending that session kills the run and can leave a lock. Whether a Haiku subagent shares the lead's
server process (and so survives the hand-back) depends on how the lead hosts it: **INFERRED, must be
confirmed by the lead** (open question Q1). Until confirmed, the skill rule is: *a Haiku session that
started a run must poll it to the end or until STOP S-SLOW; it must state in the hand-back that the run
is still live and its job_id.*

Table E, run-time estimates (measured on NguyenPC3, 2026-10-17 [RUN_LOG]):

| Part | Time |
|---|---|
| AQUA + SOFIMSHC + 3 SOFILOAD | ~3 min |
| ASE all LCs and combinations | ~6 min |
| MAXIMA | ~4 min |
| BDK 311 members x 47 combos | 35-40 min estimate, but the v2 run was still in BDK after 86 min [RUN_LOG 00:15-01:41] |
| Peak RAM | 31 of 32 GB during BDK |

### 4.3 S4: start the run and wait

```
INTENT line -> ledger
run_calculation(dat_path="<full path>.dat", timeout_minutes=<G6 value>)
```
Leave `continue_on_error` false and `only_block_urs` unset unless the brief says otherwise
(`only_block_urs` runs only one `+PROG ... urs:n` block [server.py:317]; it is the cheap way to re-run
just the AQB block `urs:9501` on an existing `.cdb`, but only on the lead's instruction).

Return handling:

| Field present | Meaning | Next |
|---|---|---|
| `status: running`, `job_id` | Still working after ~40 s [server.py:140-147] | Poll loop |
| `status: not run`, `reason` | Refused before starting | Table T3-NOTRUN |
| any other `status` | Finished within 40 s | S5 |

Poll loop:
```
get_job_result(job_id="<job_id>", wait_seconds=50)     # 50 is the maximum [server.py:141]
```
- Each call returns either the same `running` dict (`elapsed_s` grows) or the final result.
- Every 10th poll: `dashboard_status()` and one ledger line `POLL n | elapsed_s | module | est_left`.
  This is also the only progress the lead sees if Haiku is lost.
- Never call `stop_calculation`. Never call `run_calculation` again for the same `.dat` while polling
  (it is refused anyway: "already being calculated" [server.py:397-401]).
- A 90-minute run is ~110 polls of ~150 tokens each: affordable, but it is why the ledger line every
  10 polls matters (a small model can lose the count; the ledger cannot).

Table T3-NOTRUN (`reason` text contains):

| Text in `reason` | Action |
|---|---|
| `already being calculated` | Copy `job_id` from the answer, poll it (resume) |
| `calculation(s) already running` / `Not enough free RAM` | S3 wait rule, then STOP S-BUSY |
| `.mcp-running` / `another calculation` / `lock_host` present | STOP S-BUSY (a lock file from another PC is never removed automatically [README:190-193]) |
| `+SYS` / `Windows commands` | Remove the offending line (it should never be there), ledger, back to S2. Never ask to change `allow_sys_commands` |
| `#INCLUDE` / `+APPLY` / `outside the folders` / `could not be found` | STOP S-UNKNOWN (file layout problem for the lead) |
| `No active PROG` | S2 lint failed; back to S2 once, then STOP S-UNKNOWN |
| `sps.exe not found` | STOP S-SERVER |
| anything else | STOP S-UNKNOWN |

### 4.4 S5: reading errors

The finished result carries (from [solver.py:1138-1149] and [messages.py:160-197]):
`status`, `errors`, `warnings`, `erg_messages` (each: `kind`, `number`, `program`, `line`, `text`,
`input_before` = the input lines just before the message), `unfinished_programs`,
`programs_without_totals`, `files` (`cdb`, `prt`, `erg`, `plb`: `path`, `updated_by_this_run`),
`seconds`, `peak_ram_mb`, `module_times`, `server_warnings`, `left_running`, `cdb_lock`, `reason`.

Rules:
1. Use `erg_messages` (it has `input_before`, the exact offending input). Fall back to
   `read_calculation_messages(dat)` if the result was lost.
2. Work on the FIRST error only; later errors are often consequences. Re-run after each fix.
3. `programs_without_totals` is normal on a clean run (SOFiSTiK prints no totals line then
   [README:66-67]); it is not an error.
4. `server_warnings` containing `exit code` with a clean protocol is informational [solver.py:1120-1123].
5. `server_warnings` containing `WAIT FOR LOCK` + `run again` means the server already cleared the lock
   and re-ran [solver.py:1086-1089]: record it, carry on.
6. `left_running` present -> STOP S-LOCKRISK.

Known-error table (the skill ships this; each row has its evidence):

| Program # / text | Cause | Fix allowed for Haiku |
|---|---|---|
| ASE 2430 (MASS) | MASS LC converts only nodal loads [mem:MEMORY.md:42] | None: STOP S-AUTHOR |
| MASS 436 | Mass LC carries FACD/DLZ [mem:MEMORY.md:43] | None: STOP S-AUTHOR |
| `CDBASE: WAIT FOR LOCK ABORTED BY USER` | Lock inside the `.cdb` [mem:sofistik-long-runs.md:10] | v1.3.0: server already tried; if status still bad -> STOP S-LOCKRISK. v1.2.0 -> STOP S-LOCKRISK |
| 9999 INTERNAL ERROR / server unavailable | Unknown; seen with server drop [mem:project-sofistik-benchmarks.md:9] | STOP S-SERVER |
| Error naming a variable such as `#NDIV` | `DIV`, `SIN`, `COS`, `SQR` inside variable names are operators [mem:sofistik-bdk-cadinp-facts.md:11] | Rename the variable in the editable region (cite that memory line) |
| Error on a long `LC 101,102,...` list | Comma lists hold ~25 values; `$$` is not for lists [mem:sofistik-bdk-cadinp-facts.md:7] | Replace with generation `LC (101 130 1)` as in [v2.dat BDK block] |
| Error at `COPY ... FACT #A*#B` | COPY FACT accepts only a plain `#name` or number [mem:project-26016-load-audit.md:46] | Precompute with `STO#X #A*#B` (pattern at [v2.dat:63200-63207]) |
| Any other number | | Section F (fix one error) |

Section F, "Fix one error" (in the run skill):
1. Write the fingerprint, `text`, and `input_before` into the ledger.
2. `search_examples("<PROGRAM> <RECORD>")`, e.g. `"BDK CVL"`; read at most 2 hits with
   `read_text_file(path, start, 60)`.
3. If unclear: `search_manuals("<RECORD> <ITEM>", manuals=["<program>"])`, then
   `read_manual_page(manual, pdf_page)`.
4. Make the smallest edit that makes the line match the source. Add `$ src: <file or manual> p.<n>`.
5. If no source after 4 lookups -> STOP S-NOSOURCE. If the fix would change an engineering value
   (factor, load, section, restraint, LC list content) -> STOP S-CONFIRM.

### 4.5 S6-S7: reading results

S6 validity proof (all must pass):

| Check | Call | Pass if |
|---|---|---|
| V1 run clean | ledger S5 | `ok`, or `ok with warnings` with only harmless warnings |
| V2 fresh | any `cdb_*` result | no `stale_results_warning` [server.py:686-689] |
| V3 cases exist | `cdb_load_cases(cdb, "101-154")` | each planned LC present with `has_results` containing `beams` |
| V4 equilibrium | `cdb_support_reactions(cdb, lc)` for LC 1 and LC 2, no node filter | `sum_kN` equals `sum_stored_by_sofistik_kN` and the applied load within 1 % (e.g. LC 2 SDL 887 kN [mem:MEMORY.md:27]). Reaction sign: a +Z load gives `pz` -1 [README:60-62]; compare magnitudes and state the sign |
| V5 sense check | `cdb_envelope(cdb, "101-154", what="support")` | `load_cases_missing` empty [results.py:636] |

Never use a node filter for V4: the sum is then partial (`sum_is_partial` true [results.py:394-405]).

S7 member checks. Honest gap: **the server has no tool for BDK or AQB utilisations, nor for buckling
eigenvalues** (eigen LCs are decoded only as frequency/period [results.py:251-255]; `cdb_envelope`
skips eigen LCs [results.py:604]). The skill must therefore use the protocol files:

| Answer | Source | Recipe |
|---|---|---|
| BDK eta per member | `.prt`/`.lst` of the run, `ECHO SUM FULL` = one line per member with its governing combination [26016/ltb/26016_buckling_all_members.md:40]; envelope stored as LC 9100 (`LCST 9100`) | `read_text_file` paging, 400 lines per call; record the max and every eta > 0.9. The exact table layout is **not yet seen** in this project: the first time, the lead must confirm the column meaning (STOP S-UNKNOWN on first use, then freeze the layout into the skill) |
| alpha_cr | ASE `EIGE ... BUCK` output for LC 9201/9221/.../9301 [v2.dat:77320-77350] | Read the eigenvalue list in the `.prt`; BE13 shows the shape of the answer (factors 38.553, 38.553, 154.215, 154.215 [BENCHMARK_RESULTS.md:71]). min alpha_cr < 10 -> STOP S-SWAY |
| AQB section utilisation | AQB `urs:9501` output (`ECHO USEP YES`) [v2.dat:77365-77380] | As BDK |

Recommendation to the lead (outside Haiku's scope): add one server tool (e.g. `read_design_results`:
BDK/AQB max utilisation per member, buckling factors per LC) or a small parser script shipped inside
skill 3. Paging a 4 GB-model protocol with `read_text_file` is the weakest link of the whole chain for
a small model (**INFERRED**: no protocol of the full run has been read yet).

### 4.6 S8: findings and reports

- `report_check(check=<check_name>, status="running", step="S7 BDK extraction", progress="7 of 9")`
  at each state change; findings exactly in the server's format: `{"level": "fail", "text": "B81 UB
  457x191x89: LTB ratio 1.12 > 1.0 (LC 118)"}` [server.py:831-833]. End with status `passed`,
  `failed` or `attention`.
- Report tool (needs a shell on the PC; the MCP server cannot run Python):
  `py make_report.py --source "<cdb>" --code EC3 --combos 101-130,135-139,141-148,151-154 --project 26016`
  (arguments from make_report.py:302-325). First run on a model writes `design_params.xlsx` with
  defaults [reports/sofistik_report/README.md]: Haiku reports that the run used defaults, and never
  fills in buckling lengths or restraints itself (S-CONFIRM). Note the memory warning that the earlier
  26016 report used the old group 25 section [mem:MEMORY.md:36].

---

## 5. Anti-hallucination devices

1. **Cite-or-stop.** Every CADINP line Haiku adds or changes ends with `$ src: <example path>:<line>`
   or `$ src: <manual> p.<pdf_page>` or `$ src: brief`. The lead's proof check is mechanical: grep the
   ledger's EDIT lines and the file for added lines without `src`. Keep the line under 255 characters
   and avoid `;` in the comment [mem:sofistik-bdk-cadinp-facts.md:7].
2. **Editable regions only.** Approved templates mark `$ <<EDITABLE name` ... `$ EDITABLE>>`. Haiku may
   change lines only inside them. Everything else is copied byte for byte. Lint rule L1 checks it.
3. **Copy, then fill slots.** Template blocks in skill 1 have `<<SLOT>>` placeholders and a slot table
   (allowed values, units). Example:

   ```markdown
   ### Block B-ALPHACR (ASE buckling factor for one primary combination)
   Source: 26016_check_v2.dat lines 77320-77324; manual fact [ASE EIGE BUCK, LMIN AUTO] from
   shipped example lateral_buckling.dat.
       +PROG ASE urs:<<URS>>
       HEAD <<PROJECT>> buckling factors, PLC <<PLC>>
       SYST PLC <<PLC>>
       EIGE 20 BUCK LC <<LCOUT>> LMIN AUTO
       END
   | Slot | Rule |
   | URS | 9201 + n, unused in the file |
   | PLC | a calculated ULS combination that exists (never a MAXIMA envelope LC) |
   | LCOUT | 9201 + 20*n, must not clash with any LC in the file |
   ```
4. **Lookup before write.** For any record not in the template library: `search_examples` first (real
   working files), then `search_manuals` + `read_manual_page` (the manual index ships with the server;
   NguyenPC3 has no example `.dat` files and no manual PDFs locally, so `search_examples` and
   `read_manual_page` may return nothing there [mem:project-sofistik-mcp.md:10]; then STOP S-NOSOURCE,
   do not fall back to memory).
5. **Return-field whitelist.** Decisions are made only on fields named in the tables. Free text such as
   `next` or `tip` is advice, not a command.
6. **Numbers come from tools.** Every number in a finding or hand-back carries the tool and LC it came
   from. A number Haiku computed itself is labelled `(computed: <formula>)`.
7. **Offline lint table before S3** (12 rows, yes/no), including: every `+PROG` has `END`; no comma LC
   list longer than 20 values; no variable name containing DIV/SIN/COS/SQR; every BDK `CTRL` is
   followed by its LC list (CTRL persists item-wise, restate it [mem:sofistik-bdk-cadinp-facts.md:11]);
   no LC TYPE 'IMP' in ASE linear or MAXIMA [mem:project-26016-load-audit.md:47]; BDK LC lists contain
   only calculated combinations, never MAXIMA superpositions [mem:sofistik-bdk-cadinp-facts.md:7] (the
   EN 1990 template builds MAXIMA envelopes 2100+, which BDK cannot use: do not feed them to BDK);
   SVAL IY/IZ carry explicit `[cm4]` units [mem:project-sofistik-benchmarks.md:9]; no `+SYS`.
8. **Two-key engineering values.** Lines tagged `CONFIRM` or `[legacy ...]`, partial factors, psi
   factors, section names, restraint switches (`STO#JOIN/AUTO/DXR/DECK/SWAY/COLD`, [v2.dat:71285-71293])
   change only when the brief gives the exact new value.

### 5.1 Forbidden actions list (verbatim in every skill, near the top)

```markdown
## NEVER (no exception unless the lead's brief names it by exact tool and job_id)
1. Never call stop_calculation. A stopped run leaves a lock INSIDE the .cdb.
2. Never end your session or hand back "done" while a job you started is `running`
   without writing its job_id in the ledger and the hand-back.
3. Never run two calculations on the same .cdb. Never run while check_cdb_lock shows a holder
   of kind `run` or `window`.
4. Never call clear_cdb_lock unless check_cdb_lock shows only `orphan` holders.
5. Never set timeout_minutes below 3 x the estimate (minimum 120).
6. Never write a CADINP line without a `$ src:` tag. Never write syntax from memory.
7. Never change a value tagged CONFIRM, a partial or psi factor, a section, or a restraint switch.
8. Never delete, rename or copy a .cdb (a 4 GB copy takes ~7 min and copies the lock too).
9. Never edit settings.json, ask for allow_sys_commands, restart Claude or the server.
10. Never make a failing member pass by editing the model. Report it.
11. Never present a number from a run whose status is not `ok` / `ok with warnings`, or that
    carries stale_results_warning.
12. Never call any tool not listed in this skill's "Tools" section.
```

Evidence for 1, 3, 4, 8: [RUN_LOG rules 1, 7], [mem:sofistik-long-runs.md:10-14],
[server.py:519-527]; for 9: a Claude app restart kills running calculations [mem:MEMORY.md:19].

---

## 6. Description lines (triggering)

The lead dispatches Haiku with an explicit instruction ("Use skill sofistik-run-and-fix; ledger
<path>"), so triggering is mostly deterministic. Descriptions still matter when Haiku resumes alone or
picks the next stage from `next_state`. Rules:

- Third person, starts with the action, names the chain states it owns, names the trigger nouns a
  brief will contain (`.dat`, CADINP, run, errors, `.cdb`, BDK, alpha_cr, AQB, report), and says what
  it does NOT cover, pointing to the sibling skill by name.
- Mention the ledger in each, so a resumed agent with only a ledger path picks correctly.
- Under ~400 characters; no marketing words.

```yaml
---
name: sofistik-cadinp-author
description: Builds a parametric SOFiSTiK CADINP .dat for the member-check chain (states S0-S2)
  from approved templates and STO# parameters, with a cited source on every added line, then lints
  it offline. Use when a brief asks to prepare, change or assemble a .dat, or a run ledger says
  next_state S1 or S2. Does not run SOFiSTiK (use sofistik-run-and-fix) or read results.
---
```
```yaml
---
name: sofistik-run-and-fix
description: Runs a SOFiSTiK .dat through the sofistik MCP server on NguyenPC3 (states S0, S3-S5):
  pre-flight gate, run_calculation, waiting with get_job_result, classifying errors and warnings,
  cited fixes and bounded re-runs, with lock and RAM safety. Use when a brief asks to run, re-run or
  fix errors of a .dat, or a run ledger says next_state S3, S4 or S5. Does not interpret results.
---
```
```yaml
---
name: sofistik-results-and-checks
description: Reads and proves SOFiSTiK results from a .cdb (states S0, S6-S9): run validity,
  stale-result and equilibrium checks, BDK member buckling, ASE alpha_cr and AQB cross-section
  utilisations, dashboard findings, report tool, and the hand-back to the lead. Use when a brief
  asks to read, check or report results, or a run ledger says next_state S6-S9. Never runs or edits.
---
```

---

## 7. Length budget and order inside each SKILL.md

Targets (policy; **INFERRED** from general small-model behaviour and Anthropic's skill guidance that a
SKILL.md body should stay under ~500 lines; not measured on Haiku in this project):

| Part | Lines | Position |
|---|---|---|
| Frontmatter | 5 | top |
| "You are / your job / when to STOP" (3 lines) + NEVER list | 20 | 1st screen |
| State index for this skill (table: state, enter-if, exit-to) | 10 | 1st screen |
| S0 (shared, identical in all three) + ledger format | 40 | 2nd |
| This skill's states, each Enter / Do / Exit / Ledger | 80-140 | middle |
| Decision tables (status, not-run reasons, known errors, STOP codes) | 60-90 | after the states |
| Templates / reference facts (blocks with slots, LC numbering, run-time table) | 60-100 | last |
| **Total** | **275-400** (hard cap 450) | |

Rules:
- The first 40 lines must be enough to act safely if Haiku reads nothing else: identity, NEVER list,
  state index, "read the ledger first".
- Repeat the 3 most expensive rules (never stop a run; never write uncited syntax; STOP on anything
  not in a table) once at the top and once at the end of the skill; small models weight the start and
  end of a long context most (**INFERRED**).
- Long reference material (the full EN 1990 template, BDK record cheat-sheet, example excerpts) goes in
  files inside the skill folder (`templates/`, `reference/`) if the delivery format allows it (open
  question Q3); the SKILL.md then names the exact file and section to read at the exact state, e.g.
  "S2 step 4: read templates/B-ALPHACR.md".
- Shared core (NEVER list, S0, ledger, STOP code table) is byte-identical in the three skills, with a
  version line `core: v1 2026-10-18`, so the lead can diff them.

---

## 8. Proof-checking hooks for the lead ("robust proof checking")

1. Ledger audit: every `INTENT` has a `RESULT`; every `EDIT` has a `src`; every `STOP` has evidence.
2. Diff audit: compare the run `.dat` against the approved sources; only EDITABLE regions and `$ src:`
   lines may differ.
3. Number audit: re-read 3 numbers from the hand-back with the same tool calls (e.g. one
   `cdb_support_reactions`, one BDK line, one alpha_cr) and compare.
4. Canary before trust: the first time the skills run on a new server version or PC, run the
   server's self-test or a benchmark with a known answer (BE13: Pcr 38.553 kN; selftest cantilever tip
   deflection ~9.3 mm [README:36-37]) when no other run is live, and record it in the ledger.
5. Golden replay: keep one small model (the 100-line 26016_ltb_benchmark.dat [mem:project-26016-ltb-check.md:11])
   as a regression test for the skills: after each skill edit, a fresh Haiku runs S0-S9 on it and the
   lead compares the hand-back to the stored one.

---

## 9. Open questions for the lead

- **Q1 (blocking for long runs):** does a Haiku agent use the same MCP server process as the session
  that dispatched it? If not, a Haiku session that ends while a run is live kills the run
  [README:187-189]. Decide whether Haiku must poll to the end or whether the lead takes over polling.
- **Q2:** may Haiku use a shell on NguyenPC3 (to concatenate generator outputs, read `.lst`, run
  `make_report.py`)? Without it, assembly must use `#INCLUDE` (to be verified) and the report stage is
  out of Haiku's reach.
- **Q3:** may a skill ship supporting files (`templates/`, `reference/`) next to SKILL.md, or must
  everything be inside the one file? The budget above assumes supporting files are allowed.
- **Q4:** add a server tool (or a skill-bundled parser) for BDK/AQB utilisations and buckling factors?
  Without it S7 is the least reliable state.
- **Q5:** which warnings count as harmless (table W)? Needs one clean full-chain protocol (the v2 run
  in progress) to be read by the lead and frozen into the skill.
- **Q6:** v1.2.0 is what is loaded until the post-run restart [mem:MEMORY.md:20]; write the skills for
  1.3.0 with the 1.2.0 branch (section 4.1), or wait for 1.3.0 to be installed?
