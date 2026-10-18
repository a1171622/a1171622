# 03 Proof-checking regime for the Haiku SOFiSTiK chain

Author: verification engineer / checker. 2026-10-18. Offline work only: no SOFiSTiK run was started.

## Status tags

Every check below has one of these tags:

- **[V-run]**: proven on real SOFiSTiK 2027 output (the MCP self-test or the benchmarks on NguyenPC3).
- **[V-off]**: proven today, offline, by a script run on the real project files. The scripts are in `/mnt/project-files/skills/_work/03_tools/`.
- **[P]**: a proposal. It is computable with the tools named, but nobody has run it yet.
- **[I]**: an inferred fact, not confirmed in a manual or a run.

---

## 0. Rules every check follows

These rules go in the skill as hard rules.

1. **Fail closed.** A check that cannot be computed counts as FAIL, not "skipped". Examples: a tool error, a `stale_results_warning`, a load case in `load_cases_missing`, or a value of None.
2. **Numbers, never just words.** Each check writes one line to `proofs.jsonl`:
   `{gate, check_id, object (LC/member), expected, got, tol, verdict, tool, args, source_of_expected}`.
   A PASS line without both numbers is invalid. The lead replays about 10 % of the lines at random with the same tool and the same arguments.
3. **Haiku never changes tolerances.** The tolerances are fixed in the skill. Haiku may not widen one, explain a miss away, delete a load or switch a check off to get a PASS. If it thinks a tolerance is wrong, it reports ESCALATE.
4. **No vacuous passes.** If the expected value is near zero, a PASS proves nothing. This happens with self-equilibrating loads, where the net sum is 0 and a doubled load still sums to 0 (see E3, C4). Such a check must also pass a measure that is not zero: gross load, member forces, or the positive control in M1.
5. **Independent source for "expected".** The expected value never comes from the result being checked. It comes from the generator table, the .dat evaluated in Python, a hand formula, a different SOFiSTiK record, or a second agent.
6. **Fail actions.** There are three, and each check names one:
   - **STOP**: write the proof line, stop the chain, report to the lead. No auto-fix.
   - **FIX-RERUN**: at most 2 attempts. Each fix is logged as a diff with the reason, and the whole gate is re-run. A third failure becomes STOP.
   - **ESCALATE**: carry on, but put the item at the top of the report and in the dashboard findings (`report_check` level `warn`/`fail`).
7. **Run-time safety comes before checking.** These rules are from `sofistik-long-runs.md` and `RUN_LOG.md` rules 1-7:
   - Checks only read the database. They never stop a running program.
   - Before any `cdb_*` read, confirm that the run which owns the .cdb has finished (`get_job_result` status, or `check_cdb_lock`).
   - A STOP on a long model never triggers an automatic re-run. A full 26016 chain is about 55 min, and BDK alone is 40 to 80+ min. Only the lead decides on a re-run.

---

## 1. Where the gates sit in the chain

| Gate | Stage | Purpose | Blocking? |
|---|---|---|---|
| G0 | Session start | Canary or benchmark: the tools, units and signs still behave as proven | yes, before any project run |
| G1 | Before the run (.dat) | Static lint: parametric, CADINP limits, units, LC bookkeeping, no double counting | yes, before `run_calculation` |
| G2 | After the run (protocol) | Run status, errors and warnings, completeness, stale results | yes |
| G3 | Model sanity (.cdb) | Sections, materials, geometry, supports, groups, LC inventory | yes |
| G4 | Equilibrium per basic LC | Applied loads against reactions, force and moment | yes |
| G5 | Combinations | Superposition proof, factors and FACD, no double counting, envelope coverage | yes |
| G6 | Analysis quality | alpha_cr, mode shape global or local, mesh density, second-order route | yes, for member checks |
| G7 | Member checks | BDK/AQB coverage, independent EN 1993-1-1 hand check of governing members | yes, for the report |
| G8 | Plausibility envelopes | Deflection/span, self-weight/volume, frequencies, holding-down | ESCALATE |
| G9 | Report integrity | Every number in the report traces to a proof line | yes, before delivery |
| M | Meta | Mutation drills, N-version, blind second agent | per skill release, and per project |

---

## 2. G0: canary and benchmark gates (trust the session before trusting results)

| ID | How it is computed | Pass tolerance | On fail | Status |
|---|---|---|---|---|
| **K1 Tool health** | `sofistik_status` returns the SOFiSTiK path and the work folders. The tool list includes `run_calculation`, `cdb_support_reactions`, `cdb_load_cases`, `cdb_envelope`. | present | STOP | [V-run] the server answered with 27 tools in the self-test |
| **K2 Canary cantilever** | Write the self-test file (embed `selftest/selftest_cantilever.dat` verbatim in the skill) as `_canary/canary_<date>.dat` in its own folder and database. Run it, then read the values listed after this table. | tip uz within ±1 % of 9.29 mm (bending part `P L³/3EIy` = 9.286 mm, plus a small shear part); pz exactly −1.000 and −2.000; My −6/−12 kNm within ±0.1 %; N, Vy, Mt, Mz below 1e-6 | STOP. The session's reader, units or sign rules cannot be trusted. Send `selftest_report.txt` to the lead. | [V-run] self-test ALL CHECKS PASSED 17 Oct; README "Confirmed on SOFiSTiK 2027". I recomputed the bending part: 9.286 mm. |
| **K3 Sign-convention canary** | Inside K2: `+PZZ` load gives `pz = −1` at the support, a cantilever along +X gives `ury < 0`, and the support My is negative (hogging). Haiku must write these three signs into `proofs.jsonl` before it interprets any project reaction. | exact sign | STOP | [V-run] README lines "Support reactions are the force the support puts on the structure..." |
| **K4 Module benchmark, per analysis type used** | Run only the benchmark(s) for the modules this session will use (list after this table). Run them only when no project run is active and the RAM gate allows; they are seconds-long models. | BE1 ±0.1 %; BE13 ±0.1 %; BE25c 40 el ±0.5 % (10 el would be +0.8 %: this is the known ASE mass discretisation, not a fail); BE17 within 1 % on uz, phix, Mb, Mt (uy is a known +6-7 %) | STOP for that module. The other modules stay usable. | [V-run] `BENCHMARK_RESULTS.md` |
| **K5 BDK load-height benchmark** | Before BDK results on beams loaded by AREA loads are believed: `26016/ltb/26016_ltb_benchmark.dat` (own database). Compare the BDK Mcr with the hand values. | ±5 % to the hand value for the load position BDK actually uses. Record which position that is (shear centre or top flange). | ESCALATE. If BDK ignores the load height, the governing UB LTB checks must be re-done by hand with zg = +h/2 (G7-H3). | [P]. The file exists and has not been run. I re-derived the hand Mcr: 111.8 to 112.1 kNm with C1 1.127 to 1.13 against the file's 112.4 (C1 1.132), so the header values are sound [V-off]. |
| **K6 Version pin** | `run_calculation` reports the programs and their versions. The SOFiSTiK build must equal the benchmarked one (2027-0.0.139). | equal | Different build: re-run K2 and K4 before trusting | [P] |

What K2 reads:

- `cdb_node_results` LC 1 node 7: uz and ury;
- `cdb_support_reactions` LC 1 and 2: `sum_kN.pz` and `sum_stored_by_sofistik_kN`;
- `cdb_beam_forces` LC 1: My at the support and at the tip;
- `cdb_envelope` over `1-2`: the governing LC must be 2, with values twice LC 1.

Benchmarks for K4, by the module they prove:

- linear frame or truss: BE1, 69.11 mm;
- eigenvalue buckling (alpha_cr): BE13, Pcr 38.553 kN;
- eigenfrequencies: BE25c with 40 elements, f1 1.2832 Hz;
- TH2/TH3 and warping: BE17 (24 mm bow, CM 490000).

Why K2 runs every session: v1.2.0 and v1.3.0 differ in their locking and timeout behaviour. A Claude app restart reloads the server, and the PC can change (NguyenPC vs NguyenPC3). A wrong reader with every downstream check green is the worst failure mode. Every check after this gate depends on K2/K3.

---

## 3. G1: static checks on the .dat (no SOFiSTiK needed)

Tool: `03_tools/dat_lint.py`, a prototype. Haiku runs it locally on the PC (`py`) or, if Python is not allowed there, applies the same rules by reading the file with `read_text_file`.

| ID | Check | How | Tolerance | On fail | Status |
|---|---|---|---|---|---|
| **S1 Parametric** | Every load value in SOFiLOAD `AREA/LINE/BEAM/NODE/QUAD/POIN ... TYPE xx <val>` (or `PA/P1 <val>`) contains a `#name`. Pure geometry multipliers (direction cosines, tributary fractions) may follow the parameter, e.g. `#BAR*0.3401`. Literals allowed only: 0, 1, −1. | regex | 0 findings | FIX-RERUN: move the number into an `STO#` with a comment and a clause | [V-off] 0 findings on `26016_loads_unified.dat` (7,986 lines). It correctly flags the non-parametric benchmark `be17` line 84 (10.0) and the canary. |
| **S2 LC defined before use** | Every `COPY NO n` and every LC in an ASE/BDK/AQB/MAXIMA list must be defined in SOFiLOAD in the same .dat or in the stated upstream .dat. `COPY NO #N` inside `LOOP#K` is not statically resolvable, so it goes to S7. | set difference | none missing | FIX-RERUN | [V-off] for literal COPY. Loops: see S7. |
| **S3 Line length** | No line over 255 characters, comments included. CADINP's limit; the server also scans `SYS` past 255 characters. | `len(line) ≤ 255` | 0 | FIX-RERUN: split with a LOOP or a generation list, never `$$` for lists | [V-off] |
| **S4 Variable names** | `STO#/LET#/DEL#` names must not contain DIV, SIN, COS or SQR. TAN, EXP, LOG, ABS, MOD, ATN and POW are blocked as well. | substring | 0 | FIX-RERUN: rename (the 26016 precedent: NDIV became NPART) | [V-off]. Operators DIV/SIN/COS/SQR: `sofistik-bdk-cadinp-facts.md`. The extra words are [I], a cautious extension. |
| **S5 List length** | No comma list with more than 25 items. Use `LC (101 130 1)` or a counted LOOP. | count commas | ≤ 25 | FIX-RERUN | [V-off] (rule from `sofistik-bdk-cadinp-facts.md`) |
| **S6 Explicit units** | `SV/SVAL IY/IZ/IT/IYZ` must carry `[cm4]` or `[mm4]`; the default is m4. Lengths in mixed-unit blocks carry `[m]` or `[mm]`. Every `EZA/EYA` carries a unit. | regex | 0 | FIX-RERUN | [V-off] regex. Gotcha from `project-sofistik-benchmarks.md` (BE17). |
| **S7 Combination table** | The .dat is generated from a Python table, one source of truth: `{combo: [(lc, factor_expr)], FACD}`, in the style of `gen_unified.py`. Checks run on the expanded table: each basic LC at most once per combo; LC 1 never COPYed (self-weight only via FACD); at most one wind direction; never both a whole-wind case and its own building blocks (21 with 81); building blocks TYPE '-' (no action), so no automatic superposition adds them twice; every MAXIMA `ACT` restates GAMU/PSI. | Python assertions | 0 | STOP if found after the run; FIX-RERUN before it | [V-off] `check_v2.py` today: "default: no duplicates, one wind direction per combo, never 21+81 together; 74 combos". The legacy run differs only at 202-205 and 210-213, the two deliberate exceptions in audit section 4. |
| **S8 COPY FACT literal trap** | `COPY NO` and `FACT` items take only a plain `#name` or a number. No expressions and no `IIF`; precompute with `STO#`. | regex: after FACT, `^#\w+$` or a number | 0 | FIX-RERUN | [V-off] rule: audit section 7 "COPY NO and FACT accept text". The regex is [P]. |
| **S9 Forbidden LC types** | No `TYPE 'IMP'` in LCs used by a linear ASE or MAXIMA run. QUAD uniform temperature is `DTXY`, not `DT`. | regex | 0 | FIX-RERUN | rule [V] in the manual per `project-26016-load-audit.md`; regex [P] |
| **S10 Result-number clash** | Collect every result LC number written by MAXIMA, ASE EIGE (mode LCs), BDK `LCST` and the EIGE BUCK LCs. Compare with the basic and combination numbers and with any other .dat writing into the same .cdb. | set intersection | empty | FIX-RERUN | [V-off] the class of bug is real: MAXIMA 2101+ overwrote eigen modes 2101-2110 (audit section 2.2) |
| **S11 Restate per block** | Each BDK member group restates the full `CTRL` and the LC list (CTRL persists item-wise). Each AQB/BDK LC list equals the intended ULS set: 101-130, 135-139, 141-148, 151-154. EQU 131-134 are excluded. | set equality against the table | equal | FIX-RERUN | rule [V] in the manual (`sofistik-bdk-cadinp-facts.md`); [P] as automation |
| **S12 Safety scan** | No `+SYS`, `*SYS` or `$(...)`-built record names. The server refuses them anyway. | regex | 0 | FIX-RERUN | [V-run] server rule in README |
| **S13 Upstream consistency** | Load totals of each basic LC, computed in Python from the .dat after parameter evaluation, must equal the generator's own totals (`totals.py`). Two routes to the same number before SOFiSTiK sees it. | ±0.1 % | | STOP | [V-off] reference totals listed under Appendix A |

---

## 4. G2: run protocol gates

| ID | How | Pass | On fail | Status |
|---|---|---|---|---|
| **R1 Status** | `run_calculation` / `get_job_result` `status` | `ok`, or `ok with warnings` (then R2) | `errors`, `not finished`, `timed out` or `stopped`: STOP. Never read results; never stop and re-run on your own. | [V-run] statuses: README |
| **R2 Warning allow-list** | `read_calculation_messages(.prt)` gives every warning with the line before it. Each warning text must match the skill's allow-list (known benign, with reason). Any warning with "singular", "instab", "mechanism", "no stiffness", "not converged" or "negative eigenvalue" is a hard fail. | all warnings allow-listed | not allow-listed: ESCALATE, with the input line. A hard word: STOP. | [P] (allow-list to be built from the first clean 26016 run) |
| **R3 All programs finished** | `unfinished_programs` is empty. The `programs` list equals the PROG list of the .dat, including `urs` numbers. | equal | STOP | [V-run] field in `messages.py` |
| **R4 Freshness** | No `stale_results_warning` on any `cdb_*` read. Record the .dat SHA-256 and the .cdb mtime in the proof header; .cdb mtime > .dat mtime. | none | STOP | [V-run] server feature (README) |
| **R5 LC inventory** | One `cdb_load_cases` call (cheap). Every LC in the combination table, ASE list, BDK/AQB lists and envelopes exists; `has_results` contains "nodes" and "beams"; kind 0/1 for calculated LCs, 2 for MAXIMA, 4 for eigen. | none missing, kinds right | STOP | [V-run] fields in `results.load_cases` |
| **R6 Coverage of envelopes** | For every `cdb_envelope` call: `load_cases_missing` and `load_cases_without_data` are empty, and `eigen_load_cases_skipped` holds only intended eigen LCs. A `superposition_load_cases` entry must not be mixed with its own source LCs. | empty | STOP | [V-run] fields in `results.envelope` |

---

## 5. G3: model sanity (.cdb against intent)

| ID | How | Tolerance | On fail | Status |
|---|---|---|---|---|
| **MS1 Sections** | `cdb_overview` → `sections[]` A_cm2, Iy_cm4, Iz_cm4, It_cm4 against the catalogue values written in the skill (UB 254x146x43 A 54.8, Iy ≈ 6544, Iz 677, It 23.9; UB 457x191x89 A 114, Iz ≈ 2089; SHS 150x150x10 A ≈ 54.9; HEA 200 A 53.8, Iy 3692 in the canary). | ±2 % (rounded radii) | > 2 %: STOP. A factor of 10^n means a unit error (S6). | [V-run] for HEA 200 in the self-test. Catalogue numbers are [I] SCI tables; confirm against AQUA once. |
| **MS2 Material** | `cdb_overview` materials: titles equal the spec (26016: S 275, from `model.dat` line `STEE 3 S '275'`). E 210000 N/mm² read in K2. | exact | STOP | [V-off] (model.dat) |
| **MS3 Geometry box and gravity** | `cdb_overview` → `bounding_box_m` against the drawing extents (26016: x, y ±12 m, z 0 to about 12.2 m). Gravity `GDIR NEGZ`, so with Z up the self-weight must act in −Z (E2 proves it). | ±0.05 m | STOP | [P] |
| **MS4 Supports** | `cdb_support_reactions` LC 1: `supports_with_reaction` equals the number of supports in the .dat. Every support carries some pz under G. | equal | STOP: a missing support means a mechanism or a load path change | [P] |
| **MS5 Group mapping** | `cdb_beam_forces` with `groups=` for each design group. The result must have no `beams_with_unknown_group` and no `beams_where_group_range_differs`. Beam count per group equals the generator count (26016: 103 SHS, 234 UB 254, 72 UB 457, 30 RHS 250x150, 20 RHS 50x50 lines). | exact | STOP (otherwise the member checks run on the wrong members) | [V-run] group rules in the self-test; the counts are [V-off] from model.dat SNO |
| **MS6 Mesh density** | Count beams per structural line from `cdb_beam_forces` rows (`sln`). Eigen or frequency runs: ≥ 8 elements per span, ≥ 4 per half-wave of the highest mode used. | rule | below the rule: FIX-RERUN with a finer `SDIV`/`HMIN` (eigen models only; never re-mesh 26016 without the lead) | [V-run] BE25: 10 el +0.8 % f1 and +7.6 % f3; 40 el +0.05 % |

---

## 6. G4: equilibrium proofs per basic load case

**Sign rule** [V-run]. Reactions are the force of the support on the structure: +1 kN load in +Z gives `pz = −1`. With Z up, `PG` positive means down, so applied `Fz = −PG·A`. The proof is therefore:

&nbsp;&nbsp;&nbsp;&nbsp;**R + F = 0**, per component. LC 2 applies Fz = −886.6 kN, so R_z must be +886.6 kN.

| ID | How | Tolerance | On fail | Status |
|---|---|---|---|---|
| **E1 Force equilibrium** | Expected F: the generator or S13 totals (Fx, Fy, Fz) per basic LC. Got: `cdb_support_reactions(lc)` → `sum_kN` (px, py, pz), and also `sum_stored_by_sofistik_kN` (that is SOFiSTiK's `CLC_CTRL m_rx/ry/rz`). Fast route for all LCs at once: one `cdb_load_cases` call, field `sum_reactions_kN`. Tolerance basis: `ref = max(Σ|F_i|, 1 kN)`, the gross load, not the net. | \|R+F\| ≤ 0.5 % of ref + 0.05 kN: PASS. 0.5 to 2 %: ESCALATE with a cause (arcs approximated as chords in `geo.py`; load area partly outside the elements). Over 2 %: STOP. | as left | Method [V-run]: the self-test checks the stored sum against the node sum, and BE1's reactions sum to the 3 × 88.96 kN applied. Expected totals [V-off] (Appendix A). |
| **E2 Self-weight** | Got: LC 1 `sum_reactions_kN[2]`. Expected: Σ(A_cm2 from `cdb_overview` × 1e-4 × L) × γ_steel (78.5 kN/m³) + Σ(shell area × t × 78.5). L comes from the SLN geometry in the .dat. Also `dead_load_factors` of LC 1 must point to −Z. | ±2 % | > 2 %: STOP (a missing group, a wrong section or a wrong density). 1 to 2 %: ESCALATE. | [V-off] estimate for 26016 beams only: **889.1 kN** (tables A, chord lengths). The EHF G part implies ΣG = 6.6 × 300 = 1980 kN, so SW ≈ 900.7 kN incl. plates: the two routes agree within 1.3 %. The 78 shell plates (t 20) are not yet totalled [P]. |
| **E3 Gross check for self-equilibrating LCs** | For LCs whose net applied load is zero: barriers 17/18 (450 kN of line load, net 0, verified), temperature 91/92, and possibly 15/16 (net 2.6 kN). The net E1 is vacuous here (rule 0.4), so: (a) the net reaction must be ≈ 0, within 0.5 % of the gross; (b) the member route must show the load is really there. For the outward ring load, `cdb_beam_forces` on the r 12 ring chords should give N > 0 (tension), of the order of q·r = 3 × 12 = 36 kN, shared with the radials. For temperature +ΔT on a restrained ring, the column base reactions are non-zero but sum to zero. | (a) as E1; (b) sign exact, magnitude 0.3 to 1.2 × q·r | Sign wrong or N ≈ 0: STOP (load missing or wrong direction) | [P]. LC 17/18 net 0.0 is [V-off] (`totals.py`). The q·r band is [I]. |
| **E4 Moment equilibrium** | For LCs with an eccentric resultant: the canopy uplift at d/4 (21-24: "1,987 kNm per case"), wind lateral, barrier torsion. Expected moment about the origin from the .dat (resultant × lever, or Σ r × F per record). Got: Σ(node xyz × reaction) + Σ(mx, my, mz) from the rows of `cdb_support_reactions` (all nodes) and `cdb_nodes` coordinates. The server does not sum moments, so this is done in Python. | ±2 % of Σ\|M_i\| | > 2 %: STOP. This catches a load on the wrong side or a wrong eccentricity, which E1 cannot see. | [P]. The 1,987 kNm reference is [V-off] (audit section 4). |
| **E5 EHF ratio** | `R_x(501..504) / R_z(G cases)` must equal φ = 1/300. The Q part (505..508) is checked against R_z(11+12+13+14). | ±1 % | STOP | [V-off] expected values: Q part 15.78 kN = (2160.7 × 2 + 154.0 + 259.3)/300, the generator gives 15.8; G part 6.6 kN |
| **E6 Direction fingerprint** | Each wind LC's resultant direction matches its title: 21 is +X, so `sum_kN.px` is negative (a reaction opposing the +X load) and its magnitude is 277.2 kN. 23/24 are ∓Y. A pair of opposite LCs gives sums of opposite sign and equal magnitude. | sign exact, \|Δ\| ≤ 0.5 % | STOP (swapped directions would put the imperfection and the wind in different directions) | [V-off] expected 277.2 / 287.7 kN |

---

## 7. G5: combination proofs

The 26016 combinations are COPY-built load cases solved by linear ASE (`SYST PROB LINE`, and every basic LC is in the ASE list [V-off]). Superposition is therefore exact, and the combination's response must equal the factored sum of its parts.

| ID | How | Tolerance | On fail | Status |
|---|---|---|---|---|
| **C1 Resultant superposition (all combos, one call)** | `cdb_load_cases` gives `sum_reactions_kN` for every LC. For each combo c: `R_c` must equal `FACD_c · R_1 + Σ f_b · R_b` over the intended table (generator). FACD_c is read back from `factor`/`dead_load_factors`. | per component \|Δ\| ≤ 0.1 % of Σ\|f_b R_b\| + 0.05 kN | STOP | [V-off] the forward check in load space is exact: residual 0.0 on all 74 combos (`combo_superposition_proto.py`) |
| **C2 Nodal-vector superposition** | For the governing combos plus 3 picked at random: the full reaction vectors (`cdb_support_reactions` rows, every node, px..mz). The test is the forward residual ‖R_c − Σ f_b R_b‖ / ‖R_c‖. | ≤ 0.1 % | STOP | [P] on the cdb. Method [V-off]: residual 0 when clean. |
| **C3 FACD and title** | `cdb_load_cases` per combo: `dead_load_factors` and the title against the table (101-106, 111-130, 135-154 use 1.35; 107-110 use 1.0; 131-134 use 0.9; SLS 1.0). | exact | STOP | rule [V-off] (`check_v2.py` compares FACD) |
| **C4 Member-force superposition** | The same as C2 on `cdb_beam_forces` for one beam per group (ends_only). It must include an r 12 ring chord and a stair stringer. This is the only route that sees self-equilibrating parts (barriers, temperature) and torsion. | ≤ 0.1 % of the norm | STOP | [P] |
| **C5 Double counting cannot hide** | No separate test. C1 + C2 + C4 together prove each combo equals its intended table, and S7 proves the table has no duplicates. Together these prove "no LC counted twice", on the input and on the output. | — | — | Mutation proof [V-off]; table after this one |
| **C6 Envelope integrity** | For each MAXIMA result LC (4101+): every governing LC is one of the intended combos (R6). The envelope max at the governing node equals that combo's own value (`cdb_support_reactions` of that LC). | equal within 0.1 % | STOP | [P] |
| **C7 Pattern bookkeeping** | The deck LL in 151-154 adds up to the full decks of 102: 1.5 × 2 × 2160.7 = 6482.1 kN [V-off] | ±0.1 % | STOP | [V-off] arithmetic; [P] on the cdb |

Mutation evidence for C1/C2. Injected into the real 26016 combination table offline:

| Injected fault | Forward residual | Caught? |
|---|---|---|
| LC 2 (SDL) counted twice in 102 | 13.2 % | yes |
| LC 81 added to 103, so the lateral wind is counted twice | 9.3 % | yes |
| ψ0,W 0.6 instead of 0.5 in 103 | 2.4 % | yes. The smallest signal, which is why the tolerance is 0.1 %, not 1 %. |
| LC 17 (barrier) counted twice in 102 | 38 % in load space, **0 % in reaction sums** | in load space yes; with reactions only C4 sees it |
| LC 14 dropped from 102 | 36 % | yes |

**Do not invert.** Solving the factors back by least squares ("fingerprinting") is unreliable. The 145 basic LCs span only rank 133, because 15 = −16, 17 = −18, 91 = −92, 501 = −502 and so on. An injected extra LC 81 came back as 0.733/0.767 split across LCs 21/81. So the skill checks *forward*, against the intended table, and never infers the factors from the results. [V-off]

---

## 8. G6: analysis-quality gates (sway sensitivity, mesh)

| ID | How | Tolerance | On fail | Status |
|---|---|---|---|---|
| **A1 alpha_cr read** | The buckling LCs (26016: 9201, 9221, 9241, 9261, 9281, 9301 from `SYST PLC n; EIGE 20 BUCK LC m LMIN AUTO`). `cdb_load_cases` gives the kind and value. If the eigenvalue is not decoded, read the ASE eigenvalue table in the .prt via `read_text_file`. | present for each PLC | missing: STOP | [P]. The read route is proven on BE13: factors 38.553 / 38.553 / 154.215 / 154.215 [V-run]. |
| **A2 Global or local mode** | For each of the 20 modes: `cdb_node_results` on the mode LC (normalised). Let n₂₀ be the share of nodes with \|u_h\| ≥ 0.2·max. A global sway mode has n₂₀ ≥ 25 % and most nodes on a level moving the same way. A local mode has n₂₀ < 5 % and is concentrated in one group (stair RHS 50x50, a kingpost shell). alpha_cr is the lowest *global* factor. | rule | all 20 local: ESCALATE (raise the number of modes, or FIXT the local parts, per the file's own note) | [P]. The rule is from the `26016_check_v2.dat` comment block; the n₂₀ metric is my proposal. |
| **A3 Independent alpha_cr (Horne)** | EN 1993-1-1 5.2.1(4)B: α_cr = (H_Ed/V_Ed)·(h/δ_H,Ed) per storey. H from EHF LC 501 (the stored sum), V from `sum_reactions_kN[2]` of the PLC, δ the storey drift from `cdb_node_results` of LC 501 at the levels (z 4.054 / 8.055 / roof). | the same verdict band (< 3, 3 to 10, ≥ 10) as A1; numbers within a factor 1.5 | different band: ESCALATE. Horne only applies to beam-and-column frames with small beam axial force, so a ring frame with rakers may legitimately differ [I]. | [P] |
| **A4 Route decision** | α_cr ≥ 10: first order is fine and BDK runs as built. 3 ≤ α_cr < 10: enable the `-PROG ASE urs:9210` TH2 block, then BDK with `#SWAY 1`, then re-run MAXIMA (TH2 overwrites the linear results). α_cr < 3: full TH3 with imperfections (lead decision). | logic | 3 to 10 or < 3: ESCALATE to the lead. **Do not start the re-run yourself**: it costs about an hour of PC time. | rule [V] in the manual (EN 1993-1-1 5.2.1(3)); file logic [V-off] |
| **A5 TH2 sanity, if used** | The TH2 combo moments must be ≥ the linear ones, with an amplification of about 1/(1−1/α_cr) within ±15 % for the sway-dominated members. | ±15 % | ESCALATE | [P] (amplification formula [I], EN 1993-1-1 5.2.2(5)B) |

---

## 9. G7: member-check sanity (BDK / AQB against an independent hand calculation)

| ID | How | Tolerance | On fail | Status |
|---|---|---|---|---|
| **H1 Coverage** | Read the BDK `ECHO SUM FULL` table from the .lst/.prt (one line per member). The member count equals the intended list (26016: 311 members, 8 stubs < 0.3 m skipped on purpose). AQB has a result for every beam in the groups. | exact | STOP (a silent omission is the classic member-check error) | [P]. Count [V-off] from RUN_LOG and the LTB memory. |
| **H2 Governing pick** | Pick the top 3 members by utilisation from BDK and from AQB, plus 1 random member per section type, plus the member with the largest \|N\| in compression. | — | — | [P] |
| **H3 Hand check, EN 1993-1-1** | For each pick: forces from `cdb_beam_forces(lc=governing combo, beams=…)`, all stations. The Python template in the skill computes classification (Table 5.2), 6.2.5, 6.2.6, 6.2.8, 6.2.9.1 (AQB route), and 6.3.1 χ, 6.3.2.2/6.3.2.3 χ_LT,mod with Mcr from the 3-factor formula (C1 from the moment diagram, k = kw = 1, zg = 0 and +h/2), then 6.3.3 eq 6.61/6.62 with Annex B kyy, kzy (BDK route). UK NA: λ_LT,0 0.4, β 0.75, curve by h/b from NA Table NA.1, γM0 = γM1 = 1.0. The tested tool `reports/sofistik_report/sofrep/codes/ec3.py` is the second route. | AQB against hand: \|Δη\| ≤ 0.05. BDK against hand: \|Δη\| ≤ 0.10 or 10 %. Both routes must give the same PASS/FAIL. | Disagreement: ESCALATE with both calculations. η within 0.9 to 1.1 on either route: ESCALATE as "marginal, engineer to judge". | [P]. Reference numbers [V-off]: UB 254x146x43, 6 m, UDL 10 kN/m: Mcr 112 kNm, χ_LT,mod 0.606, Mb,Rd 94.3 kNm (`26016_ltb_benchmark.dat` header, re-derived to 0.6 %). |
| **H4 Restraint assumptions stated** | Every BDK result is reported with the active `STO#` switches (JOIN, AUTO, DXR, DECK, SWAY, COLD) read from the .dat. A result whose assumptions Wing has not agreed is labelled PROVISIONAL. | present | missing: FIX (report only) | [V-off] switches exist in `26016_check_v2.dat` |
| **H5 Load height** | If K5 shows BDK ignores the load height, the UB LTB utilisations for top-flange loading come from H3 with zg = +h/2. Mcr drops about 20-30 %; for UB 457 over 5.5 m it goes from 515 to 371 kNm. | — | — | [V-off] numbers from the LTB summary; route [P] |
| **H6 What BDK does not check** | The report must list it: torsion from the barrier on the r 12 rings (3.3 kNm/m), tread flats, connections. These need a separate hand or IDEA check. | listed | missing: FIX | [V-off] from the LTB summary |
| **H7 AS 4100 (secondary)** | Same pattern with `sofrep/codes/as4100.py`: φMb = αm αs φMs (5.6.1), φNc (6.3), combined 8.4. Combinations to AS/NZS 1170.0 4.2.2: 1.35G; 1.2G+1.5Q; 1.2G+Wu+ψc Q; 0.9G+Wu, with ψc 0.4 for floors (Table 4.1 [I]). | same tolerances | ESCALATE | [P] |

---

## 10. G8: plausibility envelopes (catch a wrong but self-consistent model)

| ID | How | Band | On fail | Status |
|---|---|---|---|---|
| **P1 Deflection/span** | `cdb_envelope(what='node', load_cases=SLS 201-223)` gives max \|uz\| per span (nodes from `cdb_nodes`). The limits are project values, set in the skill header for Wing to confirm: span/360 for imposed load on floors and span/200 overall are typical UK practice [I]; cantilever L/180. The beam can be checked by hand: 5wL⁴/384EI for simply supported, wL⁴/185EI for propped. | limit, and hand within ±30 % | over the limit: ESCALATE (a design issue). The hand calc off by more than a factor 2: STOP (model issue). | [P] |
| **P2 Self-weight/volume** | E2 restated as a ratio, which must equal 78.5 kN/m³ ± 2 %. Also SW/plan area for a sanity order of magnitude. | ±2 % | STOP | [V-off] ≈ 889-901 kN |
| **P3 Frequency** | For any eigen run: f1 against the hand value f = (π/2L²)√(EI/m) for the governing deck beam; ≥ 8 el/span. | ±10 % | ESCALATE | [V-run] method on BE25 |
| **P4 Holding down/EQU** | `cdb_envelope(what='support', load_cases='131-134')`. min pz < 0 means the support must pull the structure down: report it as a holding-down force, never as a model error. | report | ESCALATE | [P] |
| **P5 Ratio checks** | ULS 102 Rz / SLS 201 Rz should be between 1.35 and 1.5. Wind combo base shear / ΣW_lateral should equal the combo factor (e.g. 1.5 for 107-118). | exact to the factors | STOP | [P] |
| **P6 Utilisation distribution** | Number of members with η > 1, and the histogram. All η < 0.05, or every member the same, means the loads did not reach BDK (wrong LC list). | sanity | STOP | [P] |

---

## 11. G9: report integrity

| ID | How | On fail |
|---|---|---|
| **T1 Traceability** | Every number in the report has a `proofs.jsonl` line (LC, member, tool). The report tool's CONTRACT already demands formula, substitution, result and clause with equation number. | STOP delivery |
| **T2 Gate summary page** | The report opens with a table of all gates (G0-G8), with verdicts and the ESCALATE items first. | STOP delivery |
| **T3 Stale-data check** | The `sofistik_report` README notes its 26016 run used the old group 25 section. The report's input .cdb hash must equal the one checked in G2-G8. | STOP delivery |

---

## 12. Meta-verification: checking the checks

### M1 Mutation drills (positive controls)

A check that never fails proves nothing. For each skill release, and once per project, inject known faults into a *copy*. Each mutant gets its own .dat and .cdb, on the canary or a small model, never on the project database. The gate named in the table must fail.

| Mutant | Expected to fail | Evidence |
|---|---|---|
| Hard-coded load value | S1 | [V-off] caught |
| Variable named NDIV | S4 | [V-off] caught |
| 300-character line | S3 | [V-off] caught |
| COPY of an undefined LC | S2 | [V-off] caught |
| 26-item comma list | S5 | [V-off] caught |
| SDL twice / extra wind block / ψ0 0.6 / dropped LL / barrier twice in a combo | S7, C1/C2 (barrier: C4 only) | [V-off] all five caught in load space (table in section 7) |
| Canary `IY` without `[cm4]` | MS1 and K2 (tip deflection off by 10⁸) | [P] |
| Canary load sign flipped (`PZZ −1`) | K3, E6 | [P] |
| Canary support removed at one node | MS4, R2 (singular) | [P] |
| SLS combo with a wrong FACD | C3 | [P] |

Prototype run: `python3 -I 03_tools/dat_lint_mutants.py` → "new findings: 1" for each of the five static mutants. Zero false positives on the real 7,986-line unified file.

### M2 N-version routes for each key quantity

| Quantity | Route 1 | Route 2 | Route 3 |
|---|---|---|---|
| Applied load per LC | generator table | .dat evaluated in Python (S13) | SOFiSTiK stored reaction sum (E1) |
| Self-weight | Σ A·L·γ (E2) | EHF G part × 300 (E5) | LC 1 reaction |
| Combination content | generator table (S7) | resultant superposition on the cdb (C1) | nodal and member superposition (C2/C4) |
| α_cr | ASE EIGE BUCK (A1) | Horne 5.2.1(4)B (A3) | — |
| Member utilisation | BDK | AQB (cross-section part) | hand / `sofrep ec3.py` (H3) |
| Reader correctness | canary hand calc (K2) | benchmark manual values (K4) | `sum_kN` against `sum_stored_by_sofistik_kN` (E1) |

### M3 Blind second agent

A second Haiku instance gets **only** the .dat and the code basis. It does not get the first agent's numbers or proofs. It recomputes the S13 totals, the expanded combination table (S7) and the H3 hand checks for the same members. The lead diffs the two. Any difference above the gate tolerance is ESCALATE.

This is the protocol the 26016 audit used: designer, then two independent reviewers, then the reviewer's own script. It found 4 HIGH issues that the designer pass missed (audit section 7) [V-off].

### M4 Replay audit by the lead

The lead re-executes a random 10 % of the `proofs.jsonl` tool calls with the same arguments, and every line with verdict ESCALATE. A mismatch means the agent's log is untrustworthy, so the whole session is rejected.

---

## 13. Known blind spots (say them, do not hide them)

1. **Reaction sums are blind to self-equilibrating loads.** Barriers, temperature and EHF pairs net to zero. E3 and C4 cover this with member forces.
2. **Local support axes.** The server notes that rotated supports may report reactions in local axes (not verified). If a model has rotated supports, E1/E4 need a transform, or must be done on the unrotated ones only [I].
3. **Springs and elastic bedding.** A force carried by a spring element, rather than a nodal support, may not appear in the node reactions [I]. E1 then fails falsely. List the spring elements and add their forces.
4. **MAXIMA and TH2 results are not superposable.** C1/C2 apply only to linear runs. After a TH2 re-run, use A5 instead and re-run R5/R6.
5. **BDK load height.** Not modelled (K5 open).
6. **Shell results** only through `cdb_read_key` (README limits). The kingpost plates are not member-checked by this regime.
7. **Code values** (UK NA ψ, deflection limits, AS/NZS ψc) are not in the manuals available here. Where they are marked [I], the skill must show them as CONFIRM parameters.

---

## Appendix A: verified reference values (26016, `26016_loads_unified.dat` default parameters, [V-off] 2026-10-18)

From `python3 -I generator/totals.py`. Global Z up, applied loads; the expected reaction is the negative of each value.

| LC | Fx | Fy | Fz [kN] |
|---|---|---|---|
| 2 SDL | 0 | 0 | −886.6 |
| 3 stair handrail | 0 | 0 | −13.7 |
| 4 0.2 kPa | 0 | 0 | −179.0 |
| 11 / 13 LL L1 / L2 | 0 | 0 | −2160.7 each |
| 12 roof LL Cat H | 0 | 0 | −259.3 |
| 14 stair LL | 0 | 0 | −154.0 |
| 15 / 16 stair barrier | ±2.6 | ∓0.5 | 0 |
| 17 / 18 deck barrier | 0 | 0 | 0 (450 kN gross: E3 applies) |
| 21 / 22 W ±X + uplift | ±277.2 | 0 | +993.4 |
| 23 / 24 W ∓Y + uplift | 0 | ∓287.7 | +993.4 |
| 25 stair W +X | 28.5 | −1.0 | +30.6 |
| 81 / 82 lateral ±X | ±277.2 | 0 | 0 |
| 85 roof down | 0 | 0 | −66.2 |
| 301 / 321 / 341 span patterns | 0 | 0 | −4.6 / −54.1 / −61.3 |
| 501 / 505 / 509 EHF | 6.6 / 15.8 / 32.5 | 0 | 0 |

Legacy values: 21 gives Fx 180.5 and 23 gives Fy 189.8. The rest are unchanged.

`check_v2.py`: legacy differs only at 202-205 and 210-213 (deliberate). Default: 74 combos, no duplicates, one wind direction per combo, never 21 + 81 together.

## Appendix B: tools written for this design (prototypes, in `/mnt/project-files/skills/_work/03_tools/`)

- `dat_lint.py`: S1-S6 static rules.
- `dat_lint_mutants.py`: M1 static mutants, 5 of 5 caught.
- `combo_superposition_proto.py`: the C1/C2 forward check, the inverse-fingerprint rank demonstration and the 5 combination mutants.
- `selfweight_estimate.py`: E2 beam self-weight from the model.dat SLN lengths. The section areas are hard-coded catalogue values [I]; on the PC use `cdb_overview` A_cm2.
