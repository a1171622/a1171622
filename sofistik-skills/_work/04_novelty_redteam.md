# 04 - Novelty scout and red team (Haiku-driven SOFiSTiK chain)

Author: novelty scout / red-teamer, 2026-10-18. Offline work only (no runs started, nothing on NguyenPC3 touched).

Evidence read: `skills/_work/BRIEF.md`; memory `MEMORY.md`, `sofistik-long-runs.md`, `sofistik-bdk-cadinp-facts.md`,
`project-26016-ltb-check.md`, `project-26016-load-audit.md`, `project-sofistik-mcp.md`, `project-sofistik-benchmarks.md`,
`sofistik-report-generator.md`; `sofistik-mcp/README.md`, `CHANGELOG.md`, `sofistik_mcp/server.py` (tool list lines
171-903, `_stale_warnings` 696-716); `26016/member-check/RUN_LOG.md`; `26016/member-check/run/26016_check_v2.dat`;
`sofistik-benchmarks/BENCHMARK_RESULTS.md`; `reports/sofistik_report/README.md`, `CONTRACT.md`.

Tool names below are the server's own (`server.py`); in a cloud thread they appear as
`mcp__remote-devices__sofistik__<name>` (project-sofistik-mcp.md). "v1.3.0 only" marks tools that are not loaded on
NguyenPC3 until the 1.3.0 install + Claude restart (MEMORY.md: `check_cdb_lock`, `clear_cdb_lock`, `clone_cdb`,
parallel runs, run-time estimate).

Design stance: Haiku is reliable at *following procedures and comparing numbers*, unreliable at *judging whether an
engineering answer is plausible*. So every idea below converts a judgement into a mechanical comparison against
something independent (a known answer, a second path, a physical law, a deliberate fault), and makes the result of
that comparison the thing Haiku reports, not its own opinion.

---

## Part A - Novel ideas (18)

Rating = value for "autonomous success + trustworthiness" per unit cost, 1-10.

### A1. Number receipts (provenance-tagged results, re-read by the lead) - 10/10
**What.** Every number Haiku writes into a findings file or report carries a receipt:
`{value, unit, tool, args, cdb_path, cdb_mtime, receipt_id}` appended to an append-only `ledger.jsonl` at the moment
the tool returned it. A sentence like "B81 governs, ratio 0.94, LC 118" is only legal if it cites receipt ids. The lead
(or a 30-line Python script) samples 3-5 receipts at random and re-calls the same tool with the same args; any
mismatch voids the whole report.
**Why.** The single most dangerous Haiku failure is a fluent summary with a transposed or invented number (R10). Receipts
make fabrication detectable and cheap to audit; they also give the "flight recorder" for free (the ledger is the
recorder), and they let Wing trace any number in a report back to a cdb record - matching the report tool's own
traceability rule (CONTRACT.md line 156: "Every value used must be traceable").
**Cost.** ~50 tokens per receipt; lead spot-check 5 tool calls; no PC run.
**Feasible now.** Yes: all `cdb_*` tools are deterministic reads; `cdb_mtime` from `list_folder`. Ledger written by
Haiku with `write_dat_file`-style file writes is not possible (it only writes .dat) - so the ledger lives in the
cloud thread's working folder or in `report_check` findings (inferred: `report_check` findings text can carry the
receipt id). Recommend the ledger as a cloud-side file the executor writes with its normal file tools.

### A2. Combination algebra checker ("load atoms") - 10/10
**What.** A deterministic Python parser reads the .dat (SOFiLOAD `LC`/`COPY NO n FACT f` records and the `STO#` factor
variables) and expands every combination down to *load atoms* (each LINE/AREA/NODE load record of each primary LC,
identified by its own line number). It then asserts: (a) no atom appears twice in any combination (Wing's rule "no
load ever counted twice"); (b) every combination's factors equal the EN 1990 Table A1.2(B) formula for its family,
recomputed from the `STO#` values; (c) EXCL groups never co-occur (two wind directions); (d) legacy LCs from the
export that the unified file does not redefine are reported.
**Why.** The 26016 file builds wind combinations from overlapping primaries: e.g. `COPY NO 81`, `COPY NO 25`,
`COPY NO 85` (check_v2.dat:65991-65993) where 81-84 are "lateral-only blocks" and 21-24 are "lateral + canopy uplift"
(project-26016-load-audit.md). Mixing 21 and 81 in one combo double-counts the lateral load and SOFiSTiK will run it
with 0 errors. Only an atom-level expansion can prove absence of double counting. It also catches the concatenation
hazard in R4 (the model export carries its own SOFILOAD + `ACT` records at check_v2.dat:4192-4259 before the unified
file's at 63181).
**Cost.** One-off ~400-line script (lead or a Sonnet worker writes it once, embedded in the skill as a code block);
run time seconds; zero PC time.
**Feasible.** Yes, pure text; the audit generator already has `check_v2.py` (project-26016-load-audit.md) to build on.

### A3. Equilibrium and superposition closure from data already in the .cdb - 9/10
**What.** Two zero-cost property tests run on every result set:
1. *Load closure*: for each primary LC, SOFiSTiK's stored reaction sum (`cdb_load_cases` gives reaction sums;
   README line "SOFiSTiK's own stored reaction sum") must equal minus the applied total computed independently from
   the .dat (sum of area x pressure, line x length; e.g. LC 2 SDL = 887 kN, MEMORY.md). Tolerance 0.5 %.
2. *Superposition*: for each linear combination, reaction sum = sum(factor_i x reaction sum_i) of its primaries
   (factors from A2). Same for a sample of 20 beam forces via `cdb_beam_forces`. Any residual > 0.1 % in a linear
   (TH1) combo means a wrong factor, a missing load, or that the combo was overwritten by a TH2 run (R2).
**Why.** This is the "scale loads by 2" property test without spending a run: linearity is checked on results that
exist. It catches wrong signs, unit slips (kN vs N, kPa vs kN/m2) and lost loads mechanically.
**Cost.** ~10 `cdb_load_cases`/`cdb_beam_forces` calls, few k tokens; no PC run.
**Feasible.** Yes (`cdb_load_cases`, `cdb_support_reactions`, `cdb_beam_forces`). Sign rule needed: reactions are
force of support on structure, +Z load gives pz = -1 (README "Confirmed on SOFiSTiK 2027").

### A4. Twin micro-models: isolate the governing member three ways - 9/10
**What.** For the top N (say 5) members by BDK utilisation, Haiku generates a tiny stand-alone .dat: one member, the
same section and restraints (fork ends / CVL stations copied from the BDK block), loaded with the end forces and
member load read from the big model (`cdb_beam_forces` at stations). Run it through BDK (seconds, < 100 MB RAM), and
also through the Python EC3 calc in `reports/sofistik_report` (sofrep). Three numbers for chi_LT, Mcr and the 6.61/6.62
ratio must agree within 3 %.
**Why.** BDK on 311 members is a black box run once over 80+ min near full RAM (RUN_LOG.md). A twin gives an
independent, cheap cross-check exactly where it matters (the governing members), and a Mcr discrepancy exposes
restraint input errors (e.g. load height: memory says BDK has "no load-height item", project-26016-ltb-check.md wants
`26016_ltb_benchmark.dat` run first to see if `EZA` lowers Mcr; hand Mcr 112.4/89.1/141.7 kNm).
**Cost.** 5 x ~3 k tokens to write; 5 tiny runs (~10 s each); only when no big run is live, or under v1.3.0's RAM gate.
**Feasible.** Yes with `write_dat_file`, `run_calculation`, `cdb_beam_forces`; sofrep runs on the PC via Python.
Must wait for the live 26016 run to end on v1.2.0 (one calculation at a time).

### A5. Fault injection ("mutation testing") of the checkers - 8/10
**What.** Before trusting the verification skills, the lead builds a *mutant set*: copies of the .dat (or of saved
tool outputs) each with one known defect - a load doubled in one combo, gamma_G 1.0 instead of 1.35, wind +X sign
flipped, a member dropped from BDK, `SVAL IY 23130` without `[cm4]` (m4 default, project-sofistik-benchmarks.md),
`LC 101,102,...` comma list of 30 values, a variable named `NDIV`. Each checker (A2, A3, A6, A9, A13) must flag its
mutant. Score = mutants caught / mutants. Only checkers with 100 % catch on their own class ship in the skill.
**Why.** A checker that never fires looks identical to a checker that is broken. This proves each guard works, and
the mutant catalogue doubles as a regression suite for future skill edits.
**Cost.** Static mutants: zero PC time, ~20 k tokens once. Run-requiring mutants (A3 on a mutated small model):
a few seconds each on a tiny model, later.
**Feasible.** Static part now (text only). Dynamic part after the live run.

### A6. CADINP gotcha linter built from the memory facts - 9/10
**What.** A rule table in the skill (and a Python linter) encoding every verified gotcha, run on every .dat before
`run_calculation`:
- comma lists > ~25 values; `$$` continuation of a list; lines > 255 chars (sofistik-bdk-cadinp-facts.md)
- variable names containing DIV, SIN, COS, SQR (operators)
- `SVAL IY/IZ` without explicit `[cm4]` (default m4)
- `COPY NO/FACT` with an expression instead of a plain `#name` or number (load audit)
- MAXIMA `ACT` records not restating GAMU/PSI (ACT resets to INI defaults)
- `LC FACT` on a case holding temperature (does not scale it); QUAD `DT` used for uniform temperature (should be DTXY)
- BDK `LC` list referencing MAXIMA superposition cases (>= 4101) or not restated after each `CTRL`
- `LC TYPE 'IMP'` in ASE linear / MAXIMA
- ASE `MASS` LC carrying FACD/DLZ (error 436); area/line LCs in MASS (error 2430)
- `+SYS`/`$(...)` first words (server refuses anyway; lint early)
- unit tags: every dimensioned literal in AQUA/SOFiLOAD checked against UNIT 5 expectations (dimensional lint).
**Why.** These run *without error* or fail late in a 60-min chain. Several (comma list truncation, LC FACT +
temperature, ACT reset) give wrong numbers silently. Linting is the cheapest possible guard.
**Cost.** Seconds; zero PC.
**Feasible.** Yes; rules are all in memory files already, cite them in the skill.

### A7. Run-identity stamp inside the database - 8/10
**What.** Every generated .dat carries a run id (hash of the .dat text + timestamp) written into the database in a
readable place: the `HEAD` text and the title of a dummy load case (e.g. `LC 9999 TITL "RUNID 7f3a..."`) or a
`STO#RUNID`. After the run, Haiku reads it back (`cdb_load_cases` load_cases="9999"; titles are kept by ASE, README)
and refuses to use any result whose stamp does not match the .dat it believes it ran.
**Why.** There are already three 26016 databases (two locked leftovers, RUN_LOG.md) plus copies; `_stale_warnings`
(server.py:696) only compares mtimes and same-session history. A content stamp proves *which* input produced the
results, across sessions and across PC copies.
**Cost.** One line in the .dat, one read. Zero extra PC time.
**Feasible.** Yes (`cdb_load_cases`). `STO#` persistence in the CDB is a memory fact; reading a STO value back
needs `cdb_read_key` with an unknown key (inferred, not verified) - use the LC title route.

### A8. Golden canary + BDK canary at session start - 8/10
**What.** Before touching a real model, Haiku runs (or reads the most recent result of) two micro-runs with known
answers in a scratch folder: (1) the self-test HEA 200 cantilever (tip 9.3 mm, M 6 kNm, README self-test table);
(2) a BDK canary: the 6 m UB 254x146x43 LTB benchmark (hand Mcr 112.4 kNm at zg 0, project-26016-ltb-check.md).
Pass = tool chain, DLL readers, units, licence (BDK, eigen) all alive. Fail = stop and escalate before burning an
80-min run.
**Why.** Catches a broken server, a changed SOFiSTiK build, a missing licence or a units regression in < 1 min,
instead of discovering it after the big run.
**Cost.** ~20 s PC, ~3 k tokens. Skip if `dashboard_status` shows a live big run (v1.2.0 = one calc at a time);
then reuse the last canary result if < 24 h old.
**Feasible.** Yes (`run_calculation`, `cdb_node_results`, `cdb_beam_forces`, `dashboard_status`). The BDK canary
needs the benchmark .dat copied into a work folder on NguyenPC3.

### A9. Coverage census ("every member accounted for") - 9/10
**What.** A reconciliation table, produced mechanically: all beam elements by group from `cdb_overview` vs members in
BDK MEMB records vs members in BDK output vs members in AQB output vs members in the report. Every element must land
in exactly one bucket: checked-BDK, checked-AQB-only, deliberately excluded (with the reason from the .dat comment), or
**UNACCOUNTED** (blocks a PASS verdict).
**Why.** "All members pass" is the most likely confident wrong answer: the 26016 BDK file excludes stubs < 0.3 m,
treads, `RING3 0` rings and CHS 610 by design (check_v2.dat:71162-71166 + switches at 71279-71284), and the model
has groups 0, 1, 2, 6, 7 that appear in no BDK switch (check_v2.dat:82-99; what they are is not confirmed here -
inferred to be non-member groups). A census turns silent omissions into an explicit list Wing can approve.
**Cost.** A few `cdb_overview`/`read_text_file` calls; text processing; no PC run.
**Feasible.** Yes.

### A10. Eigenmode "globality index" for alpha_cr - 9/10
**What.** For each buckling eigen LC (9201...), read the mode-shape displacements (`cdb_node_results`, load_case =
mode LC) and compute: fraction of nodes with |u| > 10 % of max, and the share of the deformation carried by
column-top / deck-level nodes. Classify each mode as LOCAL (one stair member, one landing RHS, a shell panel) or
GLOBAL (sway of a level). alpha_cr = lowest GLOBAL factor. If all 20 are local -> escalate.
**Why.** The .dat itself warns that the lowest modes may all be local (check_v2.dat:77300-77307) and tells a human to
"look at the mode shapes in the Animator". Haiku cannot look; without this it will report the smallest factor as
alpha_cr - either a false sway classification or, worse, a local factor > 10 masking a global one < 10 (inferred
order cannot be assumed).
**Cost.** 20 node reads per PLC x 6 PLCs (max_rows must be raised or paged), ~30 k tokens. No PC run.
**Feasible.** Mostly: assumes ASE stores mode shapes as readable load cases 9201+ (inferred - verify on a canary
model first with `cdb_load_cases`).

### A11. Confidence score with a hard escalation rule - 9/10
**What.** Haiku does not decide "trustworthy"; it fills a scorecard of objective signals and the score decides:
canary pass (A8), lint clean (A6), combo algebra clean (A2), equilibrium closure < 0.5 % (A3), run stamp match (A7),
coverage 100 % accounted (A9), alpha_cr from a GLOBAL mode (A10), twin agreement < 3 % (A4), receipts spot-check
clean (A1), and *knife-edge band*: any governing ratio in 0.90-1.10, or depending on an unconfirmed assumption (A12).
GREEN = all pass -> report. AMBER = only knife-edge/assumption flags -> report with flags. RED = any check failed ->
stop, write the scorecard, escalate to the lead. No narrative override allowed.
**Why.** Turns "when should Haiku ask?" into arithmetic. Makes escalation cheap and predictable for the lead.
**Cost.** Negligible beyond the checks themselves.
**Feasible.** Yes; post the scorecard via `report_check` (status passed/attention/failed maps directly).

### A12. Assumption register with a flip test - 8/10
**What.** A table of every engineering assumption that is a *default*, not a decision: BDK fork ends (`AUTO 0`),
`DECK 0`, `DXR 0`, `COLD 0` (hot vs cold-formed open), `SWAY 0`, qp 0.766 kPa (vs 1.0-1.2 coastal, open), UK NA
assumed, report-tool "safe defaults" (README "uses safe defaults if you have not filled it in"). For the governing
members only, run the twin model (A4) with each switch flipped one at a time and record which assumption can flip
PASS -> FAIL. The report leads with "These results hold only if: ...".
**Why.** Converts hidden assumptions into Wing's decision list with numbers attached. Prevents the classic
confident-wrong answer of a PASS that relies on an unagreed restraint (project-26016-ltb-check.md: "Wing has not
yet agreed these").
**Cost.** ~6 switches x 5 members = 30 tiny runs (~5 min PC), only after the big run ends.
**Feasible.** Yes with twins; flipping switches on the full model would cost 80+ min each - forbidden.

### A13. Order-of-magnitude priors ("predict before you look") - 8/10
**What.** Before reading any result, Haiku writes its *prediction* into the ledger from hand formulas: total
reaction from loads x areas, deck beam My ~ wL^2/8 from tributary width, column N from tributary area, deflection
~ 5wL^4/384EI, expected alpha_cr range. After reading, ratio actual/predicted outside 0.5-2 raises a flag.
**Why.** A prediction made before seeing the answer is an independent anomaly detector that does not need engineering
judgement at reading time; it catches units (x1000), wrong LC (reading 4101 MAXIMA instead of 101), wrong sign.
**Cost.** ~2 k tokens per check, no PC.
**Feasible.** Yes; formulas embedded in the skill.

### A14. Mirror test on the circular platform - 6/10
**What.** Using `cdb_nodes`, map each node to its mirror under the X->-X reflection (tolerance 5 mm); compare WL+X
(LC 21) vs WL-X (LC 22) reaction sums (equal and opposite in X) and, for ring/radial groups only, member forces of
mirrored pairs. Stairs (group 60) break the symmetry, so they are excluded and their wind is in separate LCs 25-28.
**Why.** The +X and -X wind cases are hand-built with different line lists (LC 21 on SLN 43-51...; LC 22 on SLN
38-42, 52-54...; check_v2.dat:5091-6085): a missing or extra line in one direction is invisible to SOFiSTiK but
shows as asymmetry. Inferred: the platform may not be exactly symmetric (column layout differs between levels,
project-26016-ltb-check.md "hinge pattern differs between levels") - use the reaction-sum level first, members
second, with a tolerance learned from LC 1 self-weight (which should be symmetric).
**Cost.** Few reads; no PC.
**Feasible.** Yes (`cdb_nodes`, `cdb_support_reactions`, `cdb_beam_forces`).

### A15. Dual-path extraction - 7/10
**What.** Governing values read two independent ways: the cdb DLL reader (`cdb_beam_forces`, `cdb_envelope`) and the
text output (BDK `ECHO SUM FULL` table in the .lst/.prt via `read_text_file`, or the SAF xlsx the report tool
reads). Disagreement > 1 % blocks.
**Why.** Guards against reader bugs, unit conversion and the sign flips between conventions (SAF uses IDEA signs:
Vy, Vz, Mx, My x -1, CONTRACT.md line 150).
**Cost.** Low tokens; no PC. BDK utilisation exists only in text (inferred: no cdb tool reads BDK results) - so the
second path for BDK is the twin (A4).
**Feasible.** Yes.

### A16. Incident replay exam for the skills (before deploying to Haiku) - 8/10
**What.** Build an offline exam: scripted tool-response transcripts from real incidents (RUN_LOG.md: 60-min limit hit,
"WAIT FOR LOCK ABORTED BY USER", dropped RC connection while sps.exe lives, 4 GB copy at 10 MB/s, server unavailable +
9999 INTERNAL ERROR in BE17, second Claude window locking a cdb). Feed each to Haiku with the skill and grade its next
action against the right one (e.g. "do not stop; check sps.exe; never rerun into the same cdb"). Ship only skills that
pass every replay.
**Why.** Tests the skill text itself, where Haiku's misreadings show up, at zero PC cost; every future incident becomes
a new exam question (the lessons are not just recorded but enforced).
**Cost.** ~5-10 k tokens per scenario per Haiku attempt; no PC.
**Feasible.** Yes: the lead dispatches Haiku with mocked outputs pasted in the prompt.

### A17. Pilot-then-scale run planning with a budget contract - 7/10
**What.** Before a long run, a *pilot* on a subset (e.g. BDK on 10 members, 3 combos) measures seconds/member/combo
and peak RAM; extrapolate to the full run; compare with `run_history.json` (v1.3.0) and RUN_LOG times (227 members
in 26 min; all-members run > 80 min near full RAM). Haiku writes a budget contract: expected end time, RAM ceiling,
`timeout_minutes` = 2.5 x estimate, abort criteria that never involve stopping the run.
**Why.** Wing: "document and plan these events to not waste running time". The pilot also surfaces CADINP errors in the
BDK block in one minute instead of after the 10-min model build.
**Cost.** One small run (~1-3 min); saves the 27+13 min lost on 17 Oct (RUN_LOG.md).
**Feasible.** Yes; `only_block_urs` on `run_calculation` runs one +PROG block of an existing database (server.py:311),
so a pilot BDK block can run against an existing cdb without rebuilding the model (needs a clone, v1.3.0
`clone_cdb`, to avoid touching a cdb in use).

### A18. Two-draft tournament on input writing only - 6/10
**What.** Two Haiku instances independently write the same .dat from the same spec; a normaliser expands both to
load atoms (A2) and BDK member/restraint tables; only the *semantic diffs* go to the lead, who rules on each.
**Why.** Disagreement localises spec ambiguity (e.g. restraint at a ring crossing) without the lead reading 77 k lines.
**Cost.** 2x writing tokens; no PC. Lower value because A2 + A6 already catch most mechanical defects; use only for
new models, not reruns.
**Feasible.** Yes.

### Ranking (top 6)
1. A2 combination algebra / load atoms (10)
2. A1 number receipts + lead re-read (10)
3. A9 coverage census (9)
4. A3 equilibrium + superposition closure on existing results (9)
5. A10 eigenmode globality index for alpha_cr (9)
6. A11 confidence scorecard with hard escalation (9) - the glue that consumes the rest
Next tier: A6 linter (9, cheap, near-obvious), A4 twins (9, needs PC time), A12 flip test, A16 replay exam.

---

## Part B - Red team: 10 ways a Haiku executor fails, or worse, is confidently wrong

Ordered by (likelihood x damage). "CW" = produces a confident wrong engineering answer.

### B1. "All members pass" with members silently not checked (CW)
BDK file excludes stubs < 0.3 m, treads, short rings (`RING3 0`), CHS; groups 0,1,2,6,7 are in no switch
(check_v2.dat:82-99, 71162-71166, 71279). BDK may also skip a member it cannot process with only a warning (inferred).
Haiku sees no FAIL lines and reports PASS for "all members".
**Counter:** A9 coverage census; PASS verdict illegal while any element is UNACCOUNTED; exclusions listed in the report.

### B2. alpha_cr read from a local mode; TH2 overwrites linear combos (CW)
Lowest buckling factor may be a stair member or shell panel (check_v2.dat:77300-77307). Haiku reports "alpha_cr = 14,
non-sway" or "alpha_cr = 2.1, needs TH3" from a local mode. If it switches on the TH2 block, results of 103-130/141-148
are overwritten and MAXIMA envelopes become stale (check_v2.dat:77316-77318 comment).
**Counter:** A10 globality index; skill rule: enabling any `-PROG` block = escalate; after a TH2 run, A3 superposition
must *fail* for those LCs (that proves which results are second-order) and MAXIMA must be rerun.

### B3. Reading a stale or wrong database (CW)
Three 26016 databases exist plus copies; the locked leftovers hold run-1 BDK results for 227 members only (RUN_LOG.md).
`_stale_warnings` only uses mtimes and same-session history (server.py:696-716).
**Counter:** A7 run-id stamp read back before any result is used; ledger records the cdb path + mtime per receipt.

### B4. Double-counted or orphan loads after concatenating files (CW)
check_v2.dat is a concatenation: the exported model's own SOFILOAD with `ACT` and LC 1-39... (lines 4192-4259+)
precedes the unified loads (63181). LCs the unified file does not redefine survive with their legacy content (inferred
from SOFILOAD replace-by-number behaviour, not verified). Overlapping wind primaries (21-24 vs 81-84/85-88) make double
counting easy.
**Counter:** A2 atom expansion over the *whole concatenated file*; list every LC defined twice and every LC defined
but used by no combo; A3 load closure against hand totals (SDL 887 kN).

### B5. Defaults presented as design decisions (CW)
Fork ends, no deck restraint, hot-finished curve a, non-sway, qp 0.766 kPa, UK NA assumed, report-tool safe defaults
for L_LT (B81 fails on defaults at 1.61 with the old section, sofistik-report-generator.md) - all unagreed with Wing.
Haiku writes "PASS (max 0.87)" with no caveat.
**Counter:** A12 assumption register at the top of every report; scorecard AMBER whenever a governing result depends
on an unconfirmed switch; flip test numbers.

### B6. Destructive "fixes" to run problems
Generic skills say "if stuck, stop and retry". Here that means: stopping BDK (leaves a lock inside the .cdb, RUN_LOG
rule 1), restarting the Claude app to load v1.3.0 tools (kills running calcs, MEMORY.md), clearing locks on a cdb a
live run uses, re-running into the same cdb, copying 4 GB at 10 MB/s, treating a dropped RC connection as a dead run.
**Counter:** A forbidden-actions list at the top of the execution skill, phrased as hard preconditions:
before `run_calculation`/`clear_cdb_lock`/`stop_calculation` call `dashboard_status` (+ `check_cdb_lock` on v1.3.0)
and confirm no sps.exe/bdk.exe uses the file; `stop_calculation` is never called by Haiku; app restart only by the lead
with Wing's typed OK. A16 replay exam proves Haiku obeys.

### B7. "0 errors" taken as "correct"
sps.exe exits 0 and modules print no totals line on clean runs (README "Confirmed"); disabled blocks (`-PROG BDK
urs:9002`, `-PROG ASE urs:9210`) do not run and do not complain; warnings (e.g. a beam's GDIV group differing from its
group range, CHANGELOG 1.1.0) are skipped; BDK limited lists (> 25 commas) are truncated silently (inferred: the memory
fact says "holds only about 25 values").
**Counter:** A6 linter before the run; after the run, a "programs that ran" check against the `+PROG` list
(`run_calculation` returns the programs run); every warning classified (known-benign table vs escalate); A3 closure.

### B8. Truncated tool output treated as the whole set (CW)
`cdb_node_results` max_rows 200, `cdb_support_reactions`/`cdb_nodes` 500, `read_text_file` 400 lines
(server.py:742-757, 222). On a 311-member, 47-combo model a "max" taken over the first page is wrong. Haiku context
also cannot hold a 77 k-line .dat.
**Counter:** skill rule: whenever a result says rows were cut, page or narrow by group; prefer `cdb_envelope` with the
governing LC returned; receipts store `max_rows` and row counts; A13 prediction flags a too-small max.

### B9. Sign, axis and LC-number confusion (CW)
Reactions = support on structure (pz -1 for +1 kN load); hogging My negative; SAF/IDEA signs differ (CONTRACT.md:150);
LC numbering zoo: primaries 1-88, combos 101-154, patterns 301-458, MAXIMA 4101+, eigen modes 2001-2110, buckling
9201+, BDK envelope 9100 (load audit + check_v2.dat). Uplift sign on inclined stair flights depends on wind direction
(MEMORY.md stairs). Haiku reads LC 4101 thinking it is combo 101, or reports uplift as compression.
**Counter:** an LC-number map embedded in the skill with a range-check function (reject reading a combo-range number
from a MAXIMA tool and vice versa); A3 sign checks on reaction sums; A14 mirror test; A15 dual path.

### B10. Fluent fabrication and summary drift (CW)
Haiku writes a report paragraph from memory of earlier tool outputs: rounds 1.04 to "about 1.0, OK", swaps member ids,
invents a governing combo, or cites the old group 25 section (UB 254 vs 457, project-26016-ltb-check.md discrepancy).
**Counter:** A1 receipts + lead spot re-read; report numbers generated by the report tool from data files, never typed
by Haiku; ratio thresholds applied by code (1.000 is FAIL-boundary, no rounding before the comparison); section of
each governing member re-read from `cdb_overview`.

---

## Notes for the lead (judge)
- Cheapest high-value bundle for the 3-skill limit: put A6 + A2 + B6 forbidden list in skill 1 (write + run),
  A7 + A3 + A9 + A10 + B8/B9 in skill 2 (read + check), A1 + A11 + A12 in skill 3 (report + escalate).
  A4/A12 twins and A17 pilots need PC time; schedule after the live 26016 run ends.
- The two parsers (A2 combo algebra, A6 linter) should be written once by a stronger model and pasted into the skill as
  code blocks, since Haiku may not see /mnt/project-files on the PC (BRIEF.md).
- Unverified items flagged "inferred" above: SOFILOAD replace-by-number semantics, mode-shape LCs readable for
  buckling, STO# key for `cdb_read_key`, BDK silently skipping members, comma-list truncation being silent, what
  groups 0/1/2/6/7 are. Each should become a canary question once the PC is free.
