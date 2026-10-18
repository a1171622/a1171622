---
name: sofistik-results-proof
description: Proves and reads results of a finished SOFiSTiK run (states S0, S6-S9) - canary, protocol, stale-DB, equilibrium, superposition, alpha_cr, member hand-checks, scorecard, hand-back. Use when the ledger says next_state S6-S9. Read-only; not for sofistik-cadinp-author or sofistik-run-and-fix work.
---
# sofistik-results-proof (core: v2 2026-10-18)
You are a results CHECKER. You never run, edit or fix a model. You read a finished .cdb, prove it with scripts and
hand back numbers with receipts. Every number you report comes from a saved tool result or a script output. You do
NO arithmetic in your head. When a table has no row for what you see, you STOP with the code and hand back.
## NEVER (no exception; only Wing or the lead may do these)
1. Never call run_calculation, write_dat_file, clone_cdb. This skill is read-only.
2. Never start, enable or ask for a TH2/TH3 re-run (e.g. `-PROG ASE urs:9210`), even if alpha_cr < 10.
3. Never read a .cdb while a calculation on it runs (Busy PC rule, narrowed in S6a) or while a `run`/`window` holds it.
4. Never use a number from a result with `stale_results_warning`, or from a run whose status is not `ok` / `ok with warnings`.
5. Never widen a tolerance, skip a gate, or call a check PASS that did not run. Cannot run = never PASS.
6. Never take a max, min, count or "all" from a truncated answer (Truncation rule below).
7. Never use EQU, SLS, eigen/buckling (2001-2999, `buckling_lcs`) or MAXIMA (4101+) as member-check cases or change `member_lcs`.
8. Never make a failing member pass; never round 1.04 to "about 1.0". Quote it as the script printed it.
9. Never edit settings.json, restart Claude/the server, or copy/delete a .cdb. Never call mcp__hearthbot__ tools.
10. Never write a number in the hand-back without its source (receipt id, script check id or tool.field).
- Never stop, kill or end anything yourself (no stop_calculation, no clear_cdb_lock, no killing a process).
  The only exception: the server's own automatic orphan clean-up inside run_calculation (auto_clear_cdb_locks).
- Never edit tools/calibration.json and never pass --calibration to a script. Calibration is the lead's job.
- Never hand-type more than about 200 rows or 20 KB into one file. Narrow the request instead.
## State index (one machine S0-S9; S1-S2 sofistik-cadinp-author; S3-S5 sofistik-run-and-fix)
| State | Purpose | Gates | Exit to |
|---|---|---|---|
| S0 | Read ledger, resume, tools, server, canary | G0 | header `next_state` |
| S6a | PC free, run finished, protocol clean | G2 | S6b |
| S6b | Load cases read, fresh .cdb, run-identity stamp | R4, A7 | S6c |
| S6c | Equilibrium per basic LC | G4 | S6d |
| S6d | Mutation drill, superposition and EN 1990 factors | M1, G5 | S6e |
| S6e | Member-check LCs real and allowed; compression envelope | R6, L5 | S7a |
| S7a | Mesh and alpha_cr | G6 | S7b |
| S7b | Member results and coverage census | H1 | S7c |
| S7c | Hand-check of picked members | G7 | S8 |
| S8 | Plausibility, holding-down, assumptions, receipts, scorecard | G8, G9 | S9 |
| S9 | HANDBACK to the lead (with plain words for Wing) | - | END |
## READ THE LEDGER FIRST
Before any other call, `cat W/LEDGER.md` (W = workdir in the brief) and follow S0. Set header `next_state:` at the end of
every state. On any STOP go to "STOP and hand back". Read only; numbers only from tools and scripts; no row -> STOP.
## Tools and paths
- SOFiSTiK tools appear as `mcp__remote-devices__sofistik__<name>` or `mcp__sofistik__<name>`. Match by `<name>`.
- Allowed: sofistik_status, dashboard_status, get_job_result (with a job_id only), list_folder, read_text_file, read_calculation_messages,
  check_cdb_lock (1.3.0 only), cdb_overview, cdb_load_cases, cdb_beam_forces, cdb_envelope, cdb_node_results and
  cdb_support_reactions (canary only), cdb_read_key (S7b only), report_check; Bash, Read, Write inside W. Nothing else.
- `T` = /mnt/project-files/skills/tools . Raw tool results go in `W/raw/`. `X` = header `dat_local` (the cloud
  expanded .dat; every script reads X). `E` = W/expected.json. `dat`, `cdb`, `pc_folder` = PC paths.
- Scripts: `python3 -I T/<script> ... --workdir W`; print one JSON object and append it to W/proofs.jsonl; exit 0
  PASS, 1 FAIL, 2 ESCALATE, 3 CANNOT_RUN. Bash shows `Exit code N`; none shown = 0. Copy commands exactly.
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
Header keys read here: run_id, attempt, check_name, workdir, dat, cdb, pc_folder, dat_local, expected_json, runid_lc, member_lcs, buckling_lcs,
equ_lcs, sls_lcs, canary_cdb, job_id, defl_limit_mm, assumptions_agreed, server_version, member_results_source (lead, S7c resume). Written here:
cdb_mtime, member_results, next_state. This skill changes nothing, so it writes no INTENT.
## Shared rules (same text in run-and-fix and results-proof)
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
## Common procedures
Decision tables: rows top to bottom, as soon as a value is known; the first matching row wins.
**P-SAVE `<name>`**: if the harness saved the output to a file, `cp` it to `W/raw/<name>.json`. Otherwise Write the
result exactly as returned to `W/raw/<name>.json` - only if it is at most ~200 rows / 20 KB. Bigger: narrow the call
(the state says how). Two named exceptions, copied exactly key by key: cdb_overview -> save only `sections`,
`groups`, `cdb`; read_calculation_messages -> save `status`, `errors`, `warnings`, `finished`, `messages_truncated`,
`unfinished_programs`, `programs`, and `messages`/`erg_messages` with only `kind`, `number`, `program`, `text`.
Then Bash `python3 -I -m json.tool W/raw/<name>.json > /dev/null`: exit 0 -> go on; else save once more, then STOP S-UNKNOWN.
**P-READ** (every MCP read; first matching row wins)
| Result | Action |
|---|---|
| `status` `running` with `job_id` | get_job_result(job_id=<that id>, wait_seconds=50); at most 20 calls, then STOP S-READSLOW. Never stop it. |
| `error` with `being calculated right now` | STOP S-BUSY |
| `error` with `.cdb not found` / `File not found` | in S0: STOP S0-NOCANARY; elsewhere STOP S-BRIEF (wrong path) |
| `error` with `No ` and `results` | the state's table decides; no row -> STOP S-UNKNOWN |
| any other `error`, tool missing, `Server sofistik unavailable`, `9999` | STOP S-SERVER |
| `stale_results_warning` present | STOP S6-STALE |
| truncated (Truncation rule) | page or narrow as the state says; more than 40 pages of one call -> STOP S-PAGECAP (window/LC series: the state's cap) |
| otherwise | P-SAVE, go on |
**P-SCRIPT** (default, unless the state's table says otherwise): exit 0 -> `PASS` line, go on. Exit 2 -> `ESCALATE` line
+ report_check(check=<check_name>, status="attention", findings=[{"level":"warn","text":"<first note>"}]), go on.
Exit 1 -> STOP <state code>. Exit 3 -> STOP <state code>-CANNOT (fail closed). No JSON printed -> STOP S-UNKNOWN.
**P-PROOF** (gate with no script; one Bash call; scorecard.py reads it):
`echo '{"tool":"<gate>","verdict":"<PASS|FAIL|ESCALATE|CANNOT_RUN>","checks":[{"id":"<id>","verdict":"<v>","expected":"<e>","got":"<g>","raw":"<file>"}],"notes":["<text>"]}' >> W/proofs.jsonl`
**P-RECEIPT** (every number you will quote in S9; one Bash call each):
`python3 -I T/receipts.py add --workdir W --value <v> --unit <u> --tool <tool> --args '<call args as JSON>' --cdb "<cdb>" --cdb-mtime "<cdb_mtime>" --raw W/raw/<name>.json --path <json path, e.g. overall.N.min.value> --label "<meaning>"`
Exit 0 -> write the printed id next to the number, e.g. `0.94 [r17]`. Exit 1 or 3 -> STOP S-RECEIPT.
**P-MERGE** (join saved parts into one file; never by hand). Bash, `<mode>` = `rows` or `env` (any cdb_envelope):
```
python3 -I - T <mode> '<glob of parts>' <out file> <max_rows asked> <<'EOF'
import sys,json,glob;sys.path.insert(0,sys.argv[1]);from _common import load_json,unwrap
mode,parts,out,mx=sys.argv[2],sorted(glob.glob(sys.argv[3])),sys.argv[4],int(sys.argv[5])
ds=[unwrap(load_json(p)) for p in parts]
for p,d in zip(parts or ["none"],ds or [None]):
    if not isinstance(d,dict) or d.get("error") or d.get("stale_results_warning") or d.get("truncated") or (mode=="rows" and len(d.get("rows",[]))>=mx): print("BAD",p);sys.exit(1)
if mode=="rows": o={"rows":[r for d in ds for r in d["rows"]],"cdb":ds[0].get("cdb")}
else:
    cs=set.intersection(*[set(d["overall"]) for d in ds]);V=lambda m:m["value"]
    o={"what":ds[0].get("what"),"cdb":ds[0].get("cdb"),"overall":{c:{"max":max((d["overall"][c]["max"] for d in ds),key=V),"min":min((d["overall"][c]["min"] for d in ds),key=V)} for c in cs}}
    for k in ("load_cases_found","load_cases_missing","load_cases_without_data","superposition_load_cases","eigen_load_cases_skipped"): o[k]=[x for d in ds for x in d.get(k,[])]
json.dump(o,open(out,"w"));print("OK",len(parts),"parts")
EOF
```
`BAD ...` -> STOP S6-STALE if that part has a stale warning, else STOP S-PAGECAP.
**P-GROUPS `<list>`** (LC groups of 5 for envelope calls; never split by hand):
`python3 -I -c "import sys;o=[];[o.extend(range(int(p.split('-')[0]),int(p.split('-')[-1])+1)) for p in sys.argv[1].split(',') if p.strip()];[print(','.join(map(str,o[i:i+5]))) for i in range(0,len(o),5)]" "<list>"`
## S0 Start or resume (G0)
**Enter if:** always, first. **Do:**
1. Bash: `ls T/README.md T/calibration.json T/canary_check.py T/equilibrium_check.py T/combo_check.py T/coverage_census.py T/receipts.py T/scorecard.py T/mutation_drill.py T/member_check.py T/holding_down.py W/expected.json; mkdir -p W/raw`
2. Bash: `cat W/LEDGER.md` -> table S0-A decides ONLY the target state. Except on its STOP row without a `resume:` line,
   always do steps 3-6 and table S0-B next (a resume re-proves G0 this session), then go to the target.
3. sofistik_status() -> P-SAVE `s0_status`.
4. Canary reads, each P-READ then P-SAVE (cdb_path=<canary_cdb>): cdb_node_results(load_case=1, nodes="7") as
   `g0_node_lc1`; cdb_support_reactions(load_case=1) as `g0_support_lc1`; cdb_support_reactions(load_case=2) as
   `g0_support_lc2`; cdb_beam_forces(load_case=1) as `g0_beam_lc1`; cdb_envelope(load_cases="1-2", what="beam") as
   `g0_env_1_2`; cdb_load_cases(load_cases="1-2") as `g0_load_cases_1_2`. (Six calls, one each.)
5. Bash: `python3 -I -c "import json,glob,os,sys;d=sys.argv[1];json.dump({os.path.basename(p)[:-5]:json.load(open(p)) for p in sorted(glob.glob(d+'/g0_*.json'))},open(d+'/selftest_results.json','w'))" W/raw`
6. Bash: `python3 -I T/canary_check.py W/raw/selftest_results.json --workdir W`
   (Hand values inside: tip uz +9.29 mm +-1 %, ury < 0, support pz -1 / -2 kN, My -6 / -12 kNm, stored sums [0,0,-1] /
   [0,0,-2]. A +Z load gives pz < 0: a reaction is the support's force ON the structure.)
**Table S0-A (resume).**
Read the LAST line of STEPS. Look at its EVENT field (the third field), not at the start of the line.
| Last line | Action |
|---|---|
| EVENT `STOP <code>` | Do nothing new. Send the same HANDBACK again, UNLESS the brief contains a line `resume: <state> because <reason>` written by the lead after that STOP. Then append `<UTC> | S0 | NOTE | resume <state> because <reason> | next=<state>`, set header `next_state: <state>` and go to <state>. |
| EVENT `INTENT` with no RESULT after it | Use the resume table of the state named in that line. |
| anything else | Go to header `next_state`. If that state belongs to a sibling skill, send the HANDBACK with `NEXT <state> (<skill>)`. |
An `INTENT` of S1-S5 (a sibling's state, no resume table here): send the HANDBACK with `NEXT <that state> (<its skill>)`.
**Table S0-B**
| Check | Value | Action |
|---|---|---|
| step 1 | `W/LEDGER.md` or `W/expected.json` missing / any tools file missing | STOP S-BRIEF / T-MISSING |
| header run_id, attempt, check_name, dat, cdb, pc_folder, dat_local, runid_lc, member_lcs, buckling_lcs, equ_lcs, sls_lcs | empty | STOP S-BRIEF |
| header `canary_cdb` | empty, or step 4 `.cdb not found` | STOP S0-NOCANARY (sofistik-run-and-fix runs the canary) |
| `server_version` | `1.3.0` or `1.2.0` -> write it to the header; other or tool error | STOP S-SERVER |
| canary exit | 0 -> PASS; 1, 2 or 3 | STOP S0-CANARY (reader, units or signs not trustworthy) |
| anything else | | STOP S-UNKNOWN |
**Exit to:** header `next_state` (S6a after sofistik-run-and-fix). **Ledger:** `S0 | PASS | G0 canary ok server=<version> | next=<state>`
## S6a PC free, run finished, protocol clean (G2)
**Do:** 1. dashboard_status() -> Busy PC rule, narrowed (lead decision, read-only skill): STOP S-BUSY only when a running job's
   `dat` has the stem of header `cdb`; a run of another .dat -> ledger `NOTE | other model running: <dat>`, go on.
2. If header `job_id` is not empty and not `inline`: get_job_result(job_id=<job_id>, wait_seconds=1).
3. list_folder(path=<pc_folder>, pattern="*.mcp-running") -> P-READ, P-SAVE `g2_running`. 4. Only on 1.3.0: check_cdb_lock(cdb_path=<cdb>) -> P-SAVE `g2_lock`.
5. read_calculation_messages(path=<dat>) -> P-READ, P-SAVE `g2_messages` (the named subset if large).
6. Bash (message text only): `python3 -I -c "import sys,re;sys.path.insert(0,sys.argv[1]);from _common import load_json,unwrap;d=unwrap(load_json(sys.argv[2]));t=[m.get('text','') for m in d.get('messages',[])+d.get('erg_messages',[])];h=[x for x in t if re.search(r'singular|instab|mechanism|no stiffness|not converged|negative eigenvalue',x,re.I)];print('HARD',len(h));[print(x) for x in h]" T W/raw/g2_messages.json`
7. P-PROOF gate `G2_protocol`, expected `ok`, got `<status>`, one note per warning text (verbatim).
**Decision:**
| Field | Value | Action |
|---|---|---|
| step 2 `status` | `running` | STOP S-BUSY (run not finished; never stop it) |
| step 2 `error` | contains `No job` | Rule NJ; "finished" -> go on |
| `g2_running.files` | a name with the stem of `cdb` (others: NOTE only) | Marker rule: STOP S-STALEMARKER or S-BUSY |
| `g2_lock.holders[].kind` | any `run` / `window`, or `open_elsewhere` true | STOP S-BUSY / S-WINDOW |
| `g2_lock.holders[].kind` | any `orphan` | STOP S-LOCK (never clear it here) |
| `unfinished_programs` | not empty | STOP S6-RUNBAD |
| `messages_truncated` | true | route PRT below |
| step 6 | `HARD` above 0 | STOP S-HARDWARN |
| `status` | `ok` | PASS |
| `status` | `ok with warnings` | ESCALATE: the v1 allow-list is EMPTY, every warning goes to the lead with program, number, text |
| `status` | `errors`, `not finished`, `no protocol`, `timed out`, `stopped`, starts with `check:` | STOP S6-RUNBAD |
| anything else | | STOP S-UNKNOWN |
**Route PRT (more than 200 messages):** read_text_file(path=<stem>.prt, start_line=1, max_lines=200), Write `text` exactly
to `W/raw/prt_p1.txt`; next `start_line` = `to_line` + 1 until `to_line` = `total_lines`; > 150 pages -> STOP S-PAGECAP. Bash `grep -h -i -c -E "singular|instab|mechanism|no stiffness|not converged|negative eigenvalue" W/raw/prt_p*.txt` (any count above 0 -> STOP S-HARDWARN) and `grep -h -i "warning" W/raw/prt_p*.txt` (quote all in the escalation).
**Exit to:** S6b. **Ledger:** `S6a | PASS or ESCALATE | G2 status=<status> errors=<n> warnings=<n> | next=S6b`
## S6b Load cases, freshness, run-identity stamp (stale-DB proof)
**Do:** 1. Bash (predict before look): `python3 -I -c "import json,sys;e=json.load(open(sys.argv[1]))['load_cases'];[print(k,e[k].get('F_kN')) for k in list(e)[:5]]" W/expected.json` -> one `PREDICT` ledger line with those values.
2. list_folder(path=<pc_folder>, pattern="<cdb file name>") -> P-READ, P-SAVE `s6_cdbfile`; header `cdb_mtime` = `files[0].modified`.
3. Bash (LC lists, max 40 per call):
```
python3 -I - W/expected.json "<member_lcs>" <runid_lc> <<'EOF'
import sys,json;e=json.load(open(sys.argv[1]))
ex=lambda s:{i for p in str(s).split(",") if p.strip() for i in range(int(p.split("-")[0]),int(p.split("-")[-1])+1)}
L=sorted({int(k) for k in e.get("load_cases",{})}|{int(x) for x in e.get("combinations",[])}|ex(sys.argv[2])|{1,int(sys.argv[3])})
for i in range(0,len(L),40): print(",".join(map(str,L[i:i+40])))
EOF
```
4. For each printed line k (k = 1, 2, ...): cdb_load_cases(cdb_path=<cdb>, load_cases="<line k>") -> P-READ, P-SAVE `lc_p<k>`.
5. P-MERGE: mode `rows`, parts `W/raw/lc_p*.json`, out `W/raw/load_cases.json`, max_rows 999.
6. Bash: `python3 -I -c "import sys;sys.path.insert(0,sys.argv[1]);from _common import load_json,unwrap;d=unwrap(load_json(sys.argv[2]));r=[x for x in d['rows'] if x['lc']==int(sys.argv[3])];print(r[0]['title'] if r else 'MISSING')" T W/raw/load_cases.json <runid_lc>`
7. Bash: `grep -c "RUNID <run_id>-a<attempt>" <X>`
8. P-PROOF gate `A7_run_identity`, expected `RUNID <run_id>-a<attempt>`, got `<step 6 title>`.
**Decision:**
| Check | Value | Action |
|---|---|---|
| step 6 | `MISSING`, or title without `RUNID <run_id>-a<attempt>` | STOP S6-RUNID (wrong, old or other run's database) |
| step 7 | `0` or error | STOP S6-DATCOPY (X is not the run's .dat) |
| all as required | | PASS |
| anything else | | STOP S-UNKNOWN |
**Exit to:** S6c. **Ledger:** `S6b | PASS | stamp=<title> cdb_mtime=<mtime> | next=S6c`
## S6c Equilibrium per basic load case (G4)
**Do:** Bash `python3 -I T/equilibrium_check.py W/raw/load_cases.json W/expected.json --workdir W`
Fixed in the script: per component j, |R_j + F_j| <= 0.1 % of `gross_kN_xyz[j]` + 0.05 kN PASS; above 1 % FAIL; between
ESCALATE. Self-equilibrating LCs (barriers, temperature, EHF) ESCALATE "not proven by reactions". Self-weight LC 1 only with
an estimate in expected.json, else say "self-weight not checked" in S9. Combinations: combo_check (S6d).
**Decision:** P-SCRIPT, code S6-EQUIL; exit 3 with `gross_kN_xyz` in the notes -> STOP S6-EQUIL-CANNOT "expected.json
is old: the lead regenerates it with make_expected_26016.py" (never edit it yourself). **Exit to:** S6d.
**Ledger:** `S6c | <PASS/ESCALATE> | G4 <n> LCs worst=<LC> | next=S6d`
## S6d Mutation drill, superposition, EN 1990 factors (G5)
**Do:** 1. Bash (timeout 300000): `python3 -I T/mutation_drill.py <X> --expected W/expected.json --workdir W`
2. Bash: `python3 -I T/combo_check.py <X> W/raw/load_cases.json --expected W/expected.json --workdir W`
   Forward only: stored combo sums = the COPY sum the .dat says (0.1 %); factors vs EN 1990 Table A1.2 + UK NA;
   self-equilibrating parts and TH2/TH3 combos ESCALATE. Unknown action family -> ESCALATE; only the lead adds
   `--families '{"<lc>": "<family>"}'`; never invent one.
**Decision:** drill exit 0 -> step 2; drill exit 1, 2, 3 or no JSON -> STOP S6-DRILL (a checker missed a planted fault,
so its PASS proves nothing). combo_check: P-SCRIPT, code S6-COMBO.
**Exit to:** S6e. **Ledger:** `S6d | <PASS/ESCALATE> | drill=<v> G5=<v> | next=S6e`
## S6e Member-check load cases (R6, L5) and compression envelope
**Do:** 1. Bash (writes the R6 proof line itself):
```
python3 -I - W/raw/load_cases.json "<member_lcs>" "<equ_lcs>" "<sls_lcs>" "<buckling_lcs>" W T <<'EOF'
import sys,json;sys.path.insert(0,sys.argv[7]);from _common import load_json,unwrap
ex=lambda s:{i for p in str(s).split(",") if p.strip() for i in range(int(p.split("-")[0]),int(p.split("-")[-1])+1)}
rows={int(r["lc"]):r for r in unwrap(load_json(sys.argv[1]))["rows"]}
m,bad=ex(sys.argv[2]),ex(sys.argv[3])|ex(sys.argv[4])|ex(sys.argv[5]);f=[]
for lc in sorted(m):
    r=rows.get(lc)
    if lc in bad or 2001<=lc<=2999 or lc>=4101: f.append(f"{lc} not allowed (EQU/SLS/eigen/MAXIMA)")
    elif r is None: f.append(f"{lc} missing")
    elif r.get("kind") not in (0,1) or "beams" not in (r.get("has_results") or []): f.append(f"{lc} kind {r.get('kind')} results {r.get('has_results')}")
v="FAIL" if f or not m else "PASS"
o={"tool":"R6_member_lcs","verdict":v,"checks":[{"id":"R6","verdict":v,"expected":sys.argv[2],"got":f or "all present"}],"notes":f}
open(sys.argv[6]+"/proofs.jsonl","a").write(json.dumps(o)+"\n");print(json.dumps(o));sys.exit(1 if f else 0)
EOF
```
2. P-GROUPS `<member_lcs>`; for each line k: cdb_envelope(cdb_path=<cdb>, load_cases="<line k>", what="beam") -> P-READ, P-SAVE `env_p<k>`.
3. P-MERGE: mode `env`, parts `W/raw/env_p*.json`, out `W/raw/env_uls_beam.json`, max_rows 0.
4. P-RECEIPT for `overall.N.min.value` with raw `W/raw/env_uls_beam.json` (largest compression).
**Decision:**
| Check | Value | Action |
|---|---|---|
| step 1 exit | 1 | STOP S6-LCSET (a member LC is missing, not calculated, or is EQU/SLS/eigen/MAXIMA) |
| merged `load_cases_missing`, `load_cases_without_data`, `superposition_load_cases`, `eigen_load_cases_skipped` | any not empty | STOP S6-LCSET |
| all empty, exit 0 | | PASS |
| anything else | | STOP S-UNKNOWN |
**Exit to:** S7a. **Ledger:** `S6e | PASS | R6 <n> LCs Nmin=<v> kN LC <lc> [r..] | next=S7a`
## S7a Mesh and alpha_cr (G6)
**Do:**
1. Bash: `python3 -I -c "import json,sys;d=json.load(open(sys.argv[1]));[print('CAL',k,v.get('status'),v.get('value','')) for k,v in d.items() if isinstance(v,dict)]" T/calibration.json; grep -n -i -E "SYST +PLC" <X>` -> CLASSIFY line with each
   `CAL` status (calibration.json is the only status source, never README text); NOTE the PLC combinations (26016: 102, 119, 145-148).
2. cdb_overview(cdb_path=<cdb>) -> P-READ, P-SAVE `overview` (the named subset). Then Bash (beam windows of 60, about 18 KB a page): `python3 -I -c "import sys;sys.path.insert(0,sys.argv[1]);from _common import load_json,unwrap;g=unwrap(load_json(sys.argv[2]))['groups'];w=[f'{a}-{min(a+59,x[\"max_element\"])}' for x in g if x['element_code'] in (0,100,101) and x['count']>0 for a in range(x['min_element'],x['max_element']+1,60)];[print(v) for v in w];print('WINDOWS',len(w))" T W/raw/overview.json`
   `WINDOWS` above 40 -> STOP S7-NEEDS-EXPORT (no read marathon).
3. For each printed window k: cdb_beam_forces(cdb_path=<cdb>, load_case=<first PLC combination; none -> first LC of member_lcs>, beams="<window k>", ends_only=true, max_rows=121) -> P-READ, P-SAVE `bm_p<k>`.
4. P-MERGE: mode `rows`, parts `W/raw/bm_p*.json`, out `W/raw/beam_map.json`, max_rows 121.
5. cdb_load_cases(cdb_path=<cdb>, load_cases="<buckling_lcs>") -> P-READ, P-SAVE `buckling_lcs`.
6. Bash: `python3 -I T/member_check.py alpha W/raw/buckling_lcs.json --buckling-lcs "<buckling_lcs>" --beam-map W/raw/beam_map.json --dat <X> --workdir W`
   (also G6_mesh: `eigen_el_per_span` >= 8 on SLNs in compression in the beam map's LC; never without `--beam-map`).
7. P-RECEIPT for `alpha_cr_min` if it is a number.
**Decision (first matching row wins):**
| Condition | Action |
|---|---|
| step 6 exit 3, or `alpha_cr_min` = `UNCALIBRATED` / not a number | STOP S7-UNCALIBRATED |
| step 6 exit 1 (buckling LC missing or not eigen) | STOP S7-ALPHA |
| step 6 check `G6_mesh` ESCALATE (below 8 elements per span, or compression members unknown) | ESCALATE "alpha_cr NOT PROVEN: eigen mesh <n> elements"; never PASS; go on |
| `alpha_cr_min` >= 10 | PASS, worded ONLY for the step 1 primary combinations: "non-sway for combinations <list>" |
| 3 <= `alpha_cr_min` < 10 | ESCALATE S7-SWAY: maybe a local mode, maybe sway. TH2 (TH2 block, BDK SWAY 1, re-run MAXIMA) is the lead's decision; do NOT start it. Label all BDK results "PROVISIONAL - sway not resolved". Go on. |
| `alpha_cr_min` < 3 | ESCALATE S7-SWAY "second-order with imperfections needed" + the same label. Go on. |
| anything else | STOP S-UNKNOWN |
**Exit to:** S7b. **Ledger:** `S7a | <PASS/ESCALATE> | G6 alpha_cr_min=<v> LC <lc> mode <m> [r..] mesh=<n> PLC <list> | next=S7b`
## S7b Member results and coverage census (H1)
**Do:**
1. Status: the S7a `CAL` lines for `bdk` and `aqb` (calibration.json only). Commands: T/README.md `Commands after calibration`.
2. Page size P = 10 (one page below 20 KB), always. Estimate before any marathon:
   cdb_read_key the first page (`skip=0`) of the BDK key and of the AQB key for the first member LC, saved as the README
   names them; then Bash `python3 -I -c "import sys,math;sys.path.insert(0,sys.argv[1]);from _common import load_json,unwrap;ex=lambda s:{i for p in s.split(',') if p.strip() for i in range(int(p.split('-')[0]),int(p.split('-')[-1])+1)};b,a=[unwrap(load_json(f))['record_count'] for f in sys.argv[2:4]];P=int(sys.argv[5]);print('READS',math.ceil(b/P)+len(ex(sys.argv[4]))*math.ceil(a/P))" T <bdk page file> <aqb page file> "<member_lcs>" <P>`.
   `READS` above 300 -> STOP S7-NEEDS-EXPORT (expected on 26016 until the server can export to a file; not a failure).
   Else read the remaining pages, `skip` = P, 2P ... until `skip` reaches `record_count`; over 300 reads -> STOP S-PAGECAP.
3. Skip the README's beam-map read (it asks for 5000 rows); use W/raw/beam_map.json from S7a. Run its
   `member_check.py collect ...` command exactly, with `--beam-map W/raw/beam_map.json`, plus
   `--excluded W/excluded.json` only if that file exists (the lead writes `excluded` and `aqb_only_reasons` there).
4. Header `member_results: W/member_results.json`.
5. Bash: `python3 -I T/coverage_census.py <X> W/checked_members.json --workdir W`
**Decision:**
| Condition | Action |
|---|---|
| `CAL bdk` or `CAL aqb` not `CALIBRATED`, or collect exit 3 | STOP S7-UNCALIBRATED |
| collect exit 1 | STOP S7-COLLECT |
| census exit 0 | PASS |
| census exit 1 (UNACCOUNTED, or a BDK member with no result) | STOP S7-CENSUS |
| census exit 2 (e.g. AQB-only members without a lead reason: NO member-buckling check) | ESCALATE; go on |
| census exit 3 | STOP S7-CENSUS-CANNOT |
| anything else | STOP S-UNKNOWN |
**Exit to:** S7c. **Ledger:** `S7b | <PASS/ESCALATE> | H1 bdk=<n> aqb_only=<n> excluded=<n> | next=S7c`
## S7c Member hand-check (G7)
**Enter if:** S7b PASS/ESCALATE, or the lead's `resume: S7c because member_results.json supplied by lead at W/member_results.json`.
On that resume: header `member_results_source` (export file + sha256) and W/checked_members.json must exist, else STOP S-BRIEF;
NOTE `member results from <source>`; run S7b step 5 + census rows first; eta receipts: `--tool lead_export --args '{"source":"<source>"}' --raw W/member_results.json`.
**Do:**
1. Bash: `python3 -I T/member_check.py pick W/member_results.json W/raw/env_uls_beam.json --seed <run_id> --workdir W > W/raw/g7_picks.json; echo "exit=$?"; cat W/raw/g7_picks.json`
   `picks[]` (`member, sln, section, lc, eta_bdk, eta_aqb, reason`): top 3 BDK and AQB, every eta >= 0.9, largest
   compression (own LC), 1 random per section; cap 20 drops only random ones. `stats`: eta_max, n_eta_gt_1, members_gt_1.
2. For each pick with a non-null `lc`, two calls:
   a. cdb_beam_forces(cdb_path=<cdb>, load_case=<lc>, structural_lines="<sln>", max_rows=200) -> P-READ, P-SAVE `g7_<member>_<lc>`.
      Truncated -> call once per SLN of the pick, then P-MERGE mode `rows` into `g7_<member>_<lc>.json`.
   b. Bash: `python3 -I T/member_check.py hand W/raw/g7_<member>_<lc>.json W/raw/overview.json W/member_results.json --member <member> --lc <lc> --workdir W > W/raw/g7h_<member>_<lc>.json; echo "exit=$?"; cat W/raw/g7h_<member>_<lc>.json`
   c. Only if 2b exits 2 with `all_member_lcs_checked` false (e.g. "give --extra-forces", also AQB-only): P-GROUPS `<member_lcs>`; for every number n
      except <lc>: cdb_beam_forces(cdb_path=<cdb>, load_case=n, structural_lines="<sln>", max_rows=200) -> P-READ,
      P-SAVE `g7x_<member>_<n>`; then 2b again with `--extra-forces W/raw/g7x_<member>_*.json` added. Its result counts.
3. P-RECEIPT for each eta and hand value you will quote (raw = W/raw/g7_picks.json or W/raw/g7h_*.json).
Fixed tolerances (in the script): hand 6.2 vs AQB +-0.05; 6.3 vs BDK max(0.10, 10 %); same PASS/FAIL on both routes;
any eta 0.9-1.1 ESCALATE "marginal". Load height uncalibrated -> 6.3 = max(shear centre, top flange). AQB-only member:
hand 6.3 governs (> 0.9 ESCALATE, > 1.1 FAIL). The hand route shares BDK's restraint and buckling-length assumptions.
**Decision:**
| Result | Action |
|---|---|
| pick exit 1 (`G7_high_eta_picked` FAIL) or 3, or `picks` empty | STOP S7-NOPICKS |
| `stats.lc_outside_set` not empty | STOP S7-LCSET |
| pick exit 2 with `G7_picks_over_cap` (`picks_over_cap`) | ESCALATE "more than 20 mandatory picks"; hand-check them all; go on |
| a pick with `lc` null | no call; record "not hand-checked: no governing LC" (ESCALATE) |
| 2a `rows` empty, or `error` with `No ` | STOP S7-NOFORCES |
| hand exit 0 | PASS for that member |
| hand exit 2 | ESCALATE: finding `warn` with both values |
| hand exit 1 (FAIL outranks a check that could not run) | member FAILS: finding `fail`; report only, never fix; go on |
| hand exit 3 | ESCALATE "not hand-checked" (why from notes); never PASS; go on |
| anything else | STOP S-UNKNOWN |
**Exit to:** S8. **Ledger:** `S7c | <PASS/ESCALATE/FAIL> | G7 picks=<n> pass=<n> esc=<n> fail=<n> nc=<n> | next=S8`
## S8 Plausibility, holding-down, assumptions, receipts, scorecard (G8, G9)
**Do:** 1. cdb_envelope(cdb_path=<cdb>, load_cases="<equ_lcs>", what="support") -> P-READ, P-SAVE `g8_equ_support`.
2. Bash: `python3 -I T/holding_down.py W/raw/load_cases.json W/raw/g8_equ_support.json --sw-lc 1 --workdir W`
3. P-GROUPS `<sls_lcs>`; each line k: cdb_envelope(cdb_path=<cdb>, load_cases="<line k>", what="node") -> P-READ, P-SAVE `sls_p<k>`; then P-MERGE mode `env`, parts `W/raw/sls_p*.json`, out `W/raw/g8_sls_node.json`, max_rows 0.
4. Bash: `grep -n -E "STO#(JOIN|AUTO|DXR|DECK|SWAY|COLD|NPART)\b" <X>; grep -n "CONFIRM" <X>`
5. P-PROOF gate `G8_plausibility`, one check per row of table G8.
6. P-PROOF gate `A12_assumptions`: `PASS` only if header `assumptions_agreed` = `yes`; else `ESCALATE`, one note per open item.
7. Bash: `python3 -I T/receipts.py audit --workdir W --n 5` -> copy each `recall` id + `mcp_call` into HANDBACK extra.
8. Bash: `python3 -I T/scorecard.py W --ledger W/LEDGER.md`
9. report_check(check=<check_name>, status=<table SC>, step="S8 scorecard <score>", findings=[one {"level","text"} per ESCALATE / FAIL item: member or LC, value, limit, receipt]).
**Table G8 (compare only):**
| Check | Source | Rule |
|---|---|---|
| Holding-down | holding_down.py | exit 0 PASS; exit 2 = uplift under EQU: report the force (anchorage NOT checked), never a model error; exit 1/3 -> STOP S8-HD |
| Global deflection plausibility | g8_sls_node `overall.uz` max / min vs `defl_limit_mm` | above -> ESCALATE; limit empty -> ESCALATE "not checked". It is ONE global number, not a span or sway check |
| Utilisation spread | g7_picks `stats.eta_max` | below 0.05 -> STOP S8-NOLOAD (loads did not reach the checks) |
| Failures | `stats.n_eta_gt_1` | above 0 -> FAIL line listing `members_gt_1` (scorecard RED; report only) |
**Open assumption items (PROVISIONAL until Wing agrees):** 1. BDK restraint switches read in step 4 (JOIN, AUTO, DXR, DECK, SWAY, COLD): fork ends,
twist restraint at ring crossings, deck restraint. 2. Hollow sections hot-finished (COLD 0); cold-formed means lower buckling curves and a re-run. 3.
Load height: deck loads at the shear centre in BDK; top-flange loading can lower Mcr by 20-30 %. 4. Wind basis: the CONFIRM lines of step 4 (qp, vb,
ce, cpe), UK NA. 5. Deflection limit and code basis (EN 1990 / EN 1993-1-1 + UK NA).
**Table SC (scorecard exit):** 0 GREEN -> `passed`; 2 AMBER -> `attention`; 1 RED -> `failed`; 3 -> STOP S8-SCORECARD; other -> STOP S-UNKNOWN.
**Exit to:** S9. **Ledger:** `S8 | <PASS/ESCALATE/FAIL> | score=<GREEN/AMBER/RED> audit=<ids> | next=S9`
## S9 Hand-back (normal end)
Set header `next_state: END`, append `S9 | NOTE | handback score=<score> | next=END`, send the HANDBACK block of "STOP and hand back" step 3 with end_state `S9 -> NEXT END (-)`, filled as in "This skill's HANDBACK lines".
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
**This skill's HANDBACK lines.** run_live: `no` (S-BUSY / S-LINK: `unknown`). numbers: G4 worst, alpha_cr_min (+PLC list),
BDK and AQB eta_max with member and LC, hand values, Nmin, max uplift, cdb_mtime - each with [r..] or check id. extra:
`scorecard: <score> <reasons>`; `gates: G0 G2 A7 G4 drill G5 R6 G6 mesh H1 G7 G8 A12` each with its verdict (never-run
gates: `not run`); `receipts to re-call: <audit ids + mcp_call>`; `report tool: not run (needs the PC shell): make_report.py
--combos <member_lcs>`; `not checked:` torsion of the r 12 rings, treads/plates, stubs < 0.3 m, kingpost shells,
connections, holding-down bolts/anchorage under EQU (max uplift <v> [r..]), member buckling of AQB-only members unless
hand-checked, span deflection and horizontal sway (H/300), pattern imposed load with wind, self-weight unless G4 checked it, eigen mesh of members in compression only under other buckling combinations,
self-equilibrating loads (barriers, temperature, EHF) and factors inside own load expressions. After S0-NOCANARY: open "run the
canary as sofistik-run-and-fix S3 steps C1-C4 (self-test, ~10 s, timeout_minutes=10); set header canary_cdb", resume `resume:
S0 because canary_cdb set`. After S7-UNCALIBRATED `resume: S7a because calibration.json CALIBRATED`; after S7-NEEDS-EXPORT open "bulk member results need an
export; lead supplies W/member_results.json + W/checked_members.json + header member_results_source", `resume: S7c because
member_results.json supplied by lead at W/member_results.json`; after S-BUSY `resume: S6a
because PC free`.
**for_wing, normal end** (one sentence per item, each scoped to what was proven; never claim more):
- "The run finished with <0> errors; <n> warnings need your look: <list>."
- "Reactions match the applied loads within <x> % for <n> load cases; <self-weight / barriers / temperature> were not proven this way."
- "The stored combinations add up as the input file says; the factors are allowed EN 1990 + UK NA values, and uplift/EQU combinations use favourable G; parts written inside own loads were not checked."
- "Lowest buckling factor <v> for combinations <PLC list> (<non-sway | below 10: your decision on second-order>; mesh <ok | NOT proven>)."
- "<n> members have a SOFiSTiK buckling check, <n> only a cross-section check (<n> of those hand-checked for buckling), <n> excluded (<why>). Highest utilisation <v> on <member, section>, combination <lc>; the hand check (same restraint assumptions) gives <v>."
- "Not checked: <the not-checked list>. Please confirm: restraint switches, hot-finished or cold-formed hollow sections, load height on deck beams, wind basis."
**for_wing after a STOP:** "Checking stopped at <plain description of the state>: <plain reason>. Proven so far: <only
the gates that PASSED, with their numbers>. No member utilisation is reported. The lead decides the next step." After
S7-NEEDS-EXPORT, "proven so far" names G0 canary, G2 protocol, A7 run identity, G4 equilibrium, G5 combinations, R6 member LCs and
G6 buckling factor (mesh) with their numbers, plus: "Member results are too large to read page by page; the lead will supply an export."
## Reference: STOP codes (shared names keep their shared meaning)
S-BRIEF ledger, expected.json or header key missing | T-MISSING tools file missing | S0-NOCANARY / S0-CANARY canary absent /
wrong (nothing can be trusted) | S-SERVER server down | S-BUSY a calculation runs on or holds this .cdb | S-STALEMARKER
stale `.mcp-running` (Wing removes it) | S-WINDOW open in a window | S-LOCK orphan lock | S-LINK / S-LOST (Rule NJ) |
S-READSLOW 20 waits | S-PAGECAP too many pages or a bad part | S-RECEIPT receipt refused | S6-RUNBAD bad status or
unfinished program | S-HARDWARN instability word | S6-STALE old database | S6-RUNID stamp mismatch | S6-DATCOPY X is not the
run's .dat | S6-EQUIL above 1 % | S6-DRILL checker missed a planted fault | S6-COMBO sum or factor FAIL | S6-LCSET /
S7-LCSET member LC missing, not calculated, or EQU/SLS/eigen/MAXIMA | S7-UNCALIBRATED result location not calibrated |
S7-ALPHA buckling LCs wrong | S7-COLLECT pages incomplete | S7-CENSUS unaccounted member | S7-NOPICKS | S7-NOFORCES |
S7-NEEDS-EXPORT reads above the cap (needs a server export) | S8-HD | S8-NOLOAD all utilisations tiny | S8-SCORECARD |
S-UNKNOWN no row. `-CANNOT` suffix = that script could not run (fail closed). ESCALATE (go on, report): S7-SWAY, mesh not
proven, marginal 0.9-1.1, routes disagree, not hand-checked, AQB-only without reason, uplift, PROVISIONAL assumptions.
## Reference: 26016 load-case map
1-99 basic | 101-130, 135-139, 141-148, 151-154 member checks | 131-134 EQU (holding-down only) | 201-223 SLS | 301-458 patterns | 501-512 EHF |
2001-2110 eigen | 4101-4499 MAXIMA | 9100 BDK envelope | 9201-9320 buckling (PLC 102, 119, 145-148) | 9990 run stamp. Tool units: mm, mrad, kN, kNm,
m; utilisations are ratios. Reaction sign = the support's force ON the structure; the gravity sign comes from the self-weight reaction
(holding_down.py), not from a Z-up guess.
## The three rules again
1. Read only (never run, stop, clear or start TH2). 2. Every number from a saved tool result or script, with its source;
no head arithmetic, no rounding. 3. No table row -> STOP S-UNKNOWN; cannot run -> never PASS.
