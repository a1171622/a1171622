# Lead's decisions (judge), 2026-10-18 ~02:10Z

Inputs judged: 01_failure_catalogue.md, 02_haiku_design.md, 03_proof_checks.md (+03_tools), 04_novelty_redteam.md.
Lead's own verification of contested claims:
- CONFIRMED: server.py:330-332 (1.3.0) - timeout_minutes can only SHORTEN settings.json run_timeout_minutes.
  install.bat keeps an existing settings.json, so after the 1.3.0 install the 60 min limit may survive.
- CONFIRMED: dat_lint.py gives 0 findings on 26016_loads_unified.dat and catches 5/5 injected faults.
- REJECTED: 04 A2's claim that wind combos double count (75 = 81+25+85; 21 = 81+uplift; no combo 101-299 COPYs
  both 21-24 and 81-84 - lead scanned check_v2.dat). The load-atom checker idea stays (it is a good lint), the example goes.
- REJECTED: back-solving combo factors (03 item 10 shows the LC basis is rank deficient). Forward superposition only.

## D1 Architecture (adopt 02 option C)
Three self-contained skills, one global state machine S0-S9 joined by a run ledger:
1. `sofistik-cadinp-author`   S0-S2  write/assemble the .dat from approved templates, lint offline. Harmless.
2. `sofistik-run-and-fix`     S0,S3-S5 pre-flight gate, run, wait, classify errors, cited fix, bounded re-run. Costly.
3. `sofistik-results-proof`   S0,S6-S9 prove results (equilibrium, superposition, coverage, canary), extract
                               member checks, scorecard, hand back. Read-only.
Wind and IDEA StatiCa OUT of v1 (untested / need Wing's input). A hook only.
Hard length cap 450 lines per SKILL.md; first 40 lines = identity, NEVER list, state index, "read the ledger first".

## D2 Where things run (answers 02 Q1-Q3, Q6)
- Haiku runs as an agent of a CLOUD thread (lead dispatches it). It reaches SOFiSTiK through
  `mcp__remote-devices__sofistik__*` (server hosted by the Claude desktop app on NguyenPC3, confirmed
  2026-10-18 by the meshing thread). Ending Haiku's session does NOT end the run (inferred: the server
  process belongs to the desktop app). Still: Haiku records job_id in the ledger; any agent resumes with
  get_job_result(job_id). A desktop-app restart DOES kill runs -> never restart.
- ALL arithmetic proof work runs in Python in the cloud container (Bash), never in Haiku's head:
  Haiku saves raw tool JSON to the project folder, then runs the checker scripts. Rule: "every number you
  report comes from a tool result or a script output, quoted with its receipt".
- Supporting scripts cannot ship inside a skill (only SKILL.md is delivered). They live in
  /mnt/project-files/skills/tools/ (and the repo). If the folder is missing -> STOP T-MISSING.
- Target server 1.3.0, with an explicit 1.2.0 branch (no lock tools -> any lock = STOP).
- Timeout: read sofistik_status.run_timeout_minutes. 0/"no limit" OK. Non-zero and < 2x estimate -> STOP
  (only Wing/lead edits settings.json). Pass timeout_minutes only as a SAFETY cap >= 3x estimate.

## D3 Proof regime (adopt 03 G0-G9 + M1-M4, fail closed)
Mandatory gates in v1: G0 canary (self-test cantilever values) once per session before trusting anything;
G1 lint (dat_lint.py) before every run; G2 protocol (errors 0, every warning on the allow-list or escalated);
G4 equilibrium per basic LC; G5 forward superposition per linear combo; coverage census (04 A9); G7 member
hand-check of top 3 + 1 random per section via report tool ec3.py; G8 plausibility; G9 receipts.
Tolerances fixed in the skill; Haiku may never widen them. Anything 0.9-1.1 utilisation, alpha_cr < 10,
unaccounted members, or a check that cannot run -> escalate, never PASS.

## D4 Novel devices adopted
- Number receipts (04 A1): every reported number has {tool, args, cdb path, cdb mtime}; lead re-calls 3-5 at random.
- Coverage census (A9): no "all pass" while any element is UNACCOUNTED.
- Run-identity stamp (A7): run_id written into a load case title, read back from the .cdb -> stale-DB proof.
- Confidence scorecard (A11): objective signals -> GREEN / AMBER / RED, posted via report_check.
- Mutation drills (A5/M1): each checker proven to catch an injected fault (on copies only) before it is trusted.
- Assumption register (A12/B5): every default not agreed by Wing is labelled PROVISIONAL in the hand-back.
- Predict-before-look priors (A13): Haiku writes the expected order of magnitude BEFORE reading a result.
- Incident replay exam (A16): before release, Haiku agents sit scenario exams built from real incidents.
Deferred: mirror test (A14, platform not exactly symmetric), two-draft tournament (A18), eigen globality index (A10: needs mode-shape read test).

## D5 Open gaps carried as STOP codes until calibrated on the first clean 26016 run
- Where BDK/AQB utilisations live (CDB keys or .lst tables): tools engineer researches the manuals now.
- Warning allow-list: empty in v1 -> every warning is escalated with its text.
- Run-time estimates: plan 90-120 min / 17 GB for 26016 all-members BDK (RUN_LOG + 01 K09).
