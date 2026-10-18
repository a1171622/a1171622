# SOFiSTiK skills for a Haiku executor (v2, 18 Oct 2026)

Three skills let a small Claude model (Haiku) run the SOFiSTiK chain by itself. A stronger Claude acts as the lead:
it sends the work, reads Haiku's hand-back and decides anything that needs judgement.

| Skill | States | What Haiku does | Risk |
|---|---|---|---|
| `sofistik-cadinp-author` | S0-S2 | Builds a small master .dat that `#INCLUDE`s approved files already on NguyenPC3, stamps it with a run ID, lints it and checks the PC copy line by line | none (nothing runs) |
| `sofistik-run-and-fix` | S0, S3-S5 | Pre-run gate (busy PC, locks, RAM, time limit, approval), canary run, the run itself, waiting, fixing syntax errors only with a cited source | PC time |
| `sofistik-results-proof` | S0, S6-S9 | Proves the results before reading them, then the member checks, a GREEN/AMBER/RED scorecard and a plain-language hand-back | read-only |

They share one numbered state machine and one ledger file (`W/LEDGER.md`), so any agent can pick up where another stopped.

## The proof checks (scripts in `tools/`, 56 tests pass)
Haiku does no arithmetic in its head; every number comes from a tool or a script and carries a receipt the lead can re-check.

- **G0 canary:** the self-test cantilever must give its hand values (9.29 mm tip, signs, reaction sums) before anything is trusted.
- **G1 lint:** CADINP traps from our own incidents (25-item lists, 255-char lines, DIV/SIN in names, COPY FACT expressions, units, result-number clashes, load counted twice).
- **G2 protocol / A7 run stamp:** errors, every warning escalated, and a run ID in a load-case title proves the .cdb is from this run.
- **G4 equilibrium:** reactions vs applied load per load case and per direction (0.1 % pass, 1 % fail).
- **G5 combinations:** each combination's reactions must equal the factored sum of its load cases, and each factor must be the intended EN 1990 + UK NA value (favourable G in uplift and EQU).
- **G6 alpha_cr:** at least 10 for non-sway; below 10 goes to you, Haiku never starts a second-order run; the eigen mesh must have 8+ elements per member in compression.
- **Coverage census:** every member is BDK-checked, AQB-only with a reason, or excluded with a reason; never "all pass" with a member unaccounted.
- **G7 hand checks:** every member at 0.9 or above, the top 3, one random per section and the largest compression member, by an independent EC3 calc. 0.9-1.1 always goes to an engineer.
- **Mutation drill:** before trusting the checkers, faults are planted in a copy of the .dat (57 kinds on 26016) and every checker must catch its own.

## What still has to happen on the PC (calibration, in `tools/calibration.json`)
Until these are CALIBRATED the skills stop safely instead of guessing:
1. **Server lifetime:** does a run survive the agent that started it? Needs a run of 1-2 min.
2. **alpha_cr storage:** read the BE13 benchmark .cdb (known 38.553 kN) once.
3. **BDK and AQB result keys:** read 5+ members from the first clean 26016 run.
4. **LTB load height:** run the 26016_ltb_benchmark.dat.
5. **run_timeout_minutes** in the server's settings.json must be 0 (no limit).

## Known limits
- Reading every member's BDK/AQB result page by page is thousands of tool calls on 26016, so the skill stops with S7-NEEDS-EXPORT. The fix is an "export results to file" tool in MCP server 1.4.
- Hand-saved tool results are a copying risk; the lead re-calls a random sample of receipts.
- Open engineering assumptions stay PROVISIONAL (scorecard AMBER at best) until you agree them: BDK restraint switches, hot-finished vs cold-formed hollow sections, load height on deck beams, wind basis.

## How it was built and checked
Design record in `_work/`: failure catalogue (70 items), Haiku design, proof regime, new ideas and red team, the lead's decisions, two review rounds and a final check. Haiku sat three blind exams built from real incidents (35 of 36 right; the one miss was fixed and re-tested).
