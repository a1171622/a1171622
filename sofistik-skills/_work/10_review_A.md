# 10 Independent review A (adversarial engineering check) of the 3 SOFiSTiK skills + tools

Reviewer A, 2026-10-18. Read-only: no skill or tool was edited and no SOFiSTiK run was started.
Scope: sofistik-cadinp-author, sofistik-run-and-fix, sofistik-results-proof SKILL.md; tools/README.md,
calibration.json, *.py. Evidence: project memory (silo), 26016 audit, 26016_check_v2.dat (NUL/CR-stripped copy),
BE13 benchmark input, MCP server source (stale logic), and my own fault injections against copies.

Test suite: `python3 -I tools/tests/run_tests.py`: **28 passed, 0 failed, 0 skipped**. The suite passes, but it does
not cover the paths in A-01, A-02, A-03 and A-09 below.

Scratch evidence (all files in my scratchpad, inputs are copies):
`/tmp/claude-0/-home-claude-a1171622/ae4f7651-d223-504c-bd74-163a55754ecc/scratchpad/fi1` (hand-check),
`.../fi3` (equilibrium), `.../fi4` (combo_check on check_v2), `.../fi5` (scorecard).

## Fault injections (5 run, 5 got through)
| FI | Fault injected | Tool result | Should be |
|---|---|---|---|
| FI-1 | AQB-only member, UB 254x146x43, 8 m unrestrained, AQB eta 0.50. Hand 6.2 = 0.48, **hand 6.3 = 1.148 (top flange 1.30)** | `member_check hand` **PASS, exit 0** (only G7_aqb compared) | FAIL or ESCALATE |
| FI-2 | BDK member, eta_bdk 0.86. Hand at the shear centre 0.894, **hand with top-flange load 1.007** | **PASS, exit 0** | ESCALATE |
| FI-3 | LC 21 (Fx 277.2, Fz 993.4, gross 1270.6). Lateral reaction 6 kN short (2.2 % of the wind) / 25 kN short (9 %) | PASS / ESCALATE | FAIL for 9 % of the lateral load |
| FI-4 | check_v2: combinations **136 and 137 reaction sums x1.5** (all other LCs consistent) | `combo_check` **PASS, exit 0**, 80/80. The note says they are "proved by equilibrium_check (G4)", but G4 skips them | FAIL |
| FI-5 | proofs.jsonl: all gates PASS, `pick` with 7 picks and `stats.n_eta_gt_1 = 3`, only 1 hand line | `scorecard --ledger` **GREEN, exit 0** | RED (picks not hand-checked, members > 1.0) |

---

## Findings

### A-01 BLOCKER: the hand-check never looks at the member-buckling (6.3) result of an AQB-only member
- **Where:** tools/member_check.py:555-573. Also sofistik-results-proof/SKILL.md:305 ("hand exit 0 -> PASS for that member").
- **What is wrong:** A pair is compared only when SOFiSTiK has a value for it. `eta_bdk` is None for every AQB-only
  member (122 SLNs in 26016). So `hand_bdk` is computed and then thrown away, and the member is reported PASS on the
  6.2 cross-section check alone. The same happens when sofrep returns no 6.3 ratio for a BDK member: only the AQB
  pair is compared and the result is still exit 0.
- **Evidence:** FI-1. The output has `hand_bdk 1.1478`, `hand_bdk_top_flange 1.2987`, verdict PASS, exit 0. The
  members in question are ring beams (r 1.9 / r 3.0, RING3 0), deck UB 457 and roof UB 254 chords and 50 stair
  SLNs (my census of check_v2: groups 15/25/35/60 hold 122 SLNs outside BDK). The hand-back then calls them
  "checked by AQB only", with "an independent EN 1993-1-1 hand check".
- **Fix:**
  - For any member, if `hand_bdk` > 0.9 (or > eta_aqb + 0.05) and no BDK value exists, return ESCALATE
    "member buckling not checked by SOFiSTiK; hand 6.3 = x". Return FAIL when it is > 1.1.
  - If BDK has a value but `hand_bdk` is None, return CANNOT_RUN, never PASS.
  - Add a test with the FI-1 data.

### A-02 BLOCKER: nothing checks the "mixed" combinations 136-139 (member-check ULS), 21-24 and 222-223, yet combo_check reports PASS
- **Where:** tools/combo_check.py:75-77 and 135-137. tools/equilibrium_check.py:117-119 (combinations are excluded).
- **What is wrong:** combo_check skips a combination that has its own load records plus COPY, and only writes a note.
  The note says G4 proves these sums. G4 does not: they are listed in `expected.json["combinations"]` (all of 101-223),
  and equilibrium_check skips anything in that list without saying so. So the temperature combinations 136-139,
  which are in the BDK/AQB set, have no proof of their G, Q or T factors at all. In the unified file
  (lines 6560-6589) the temperature is written directly as `#DTP*#GQT` because COPY FACT does not scale temperature.
  That is exactly where a factor error would hide.
- **Evidence:** FI-4. On the real check_v2, the 136/137 sums x1.5 give PASS, 80/80 passed, worst_rel 2.7e-5.
- **Fix:**
  - For mixed combinations, predict `sum(fact x R_src) + R_own`, where `R_own = -F_own` comes from the generator
    (make_expected can total the own records of each LC). Or return ESCALATE "not superposition-checked", never a
    silent note.
  - Make equilibrium_check FAIL, or at least ESCALATE, for any `combinations` entry that combo_check did not check.
  - Correct the note text in combo_check.

### A-03 MAJOR: the top-flange load-height result is computed and then ignored (unconservative LTB)
- **Where:** tools/member_check.py:528-534 and 549-551 (`h_bdk_top` is only reported). sofistik-results-proof/SKILL.md:297-298 and 337-339.
- **What is wrong:** The deck beams carry their load on the top flange. The skill itself says Mcr may be 20-30 %
  too high (unconservative) until the LTB benchmark proves otherwise. The tool computes the destabilising-load case
  and then passes the member on the shear-centre value.
- **Evidence:** FI-2. Shear centre 0.894, top flange 1.007, verdict PASS.
- **Fix:**
  - Until the 26016_ltb_benchmark proves BDK takes EZA load height into account, use
    max(shear-centre, top-flange) for deck/roof beams (groups 15/25/35) in the margin and FAIL tests.
  - At minimum, return ESCALATE when `h_bdk_top` > 0.9.

### A-04 MAJOR: the coverage census counts an AQB-only member as accounted for, with no reason required
- **Where:** tools/coverage_census.py:54-55. sofistik-results-proof/SKILL.md:270 and 378.
- **What is wrong:** AQB runs on "all beams", so any member left out of BDK (by mistake, an IF switch or a forgotten
  group) silently becomes AQB_ONLY. It is never UNACCOUNTED. This defeats the "silent omission" guard for exactly
  the members that need 6.3: compression members and laterally unrestrained beams. With A-01 on top, such members
  are reported as checked.
- **Evidence:** census of check_v2: 122 AQB-only SLNs (rings r 1.9/3.0 x3 levels, 50 stair SLNs incl. 8 RHS
  stubs). None of them carries a reason.
- **Fix:** Treat AQB_ONLY like EXCLUDED: it needs a lead-written reason per SLN or group (for example "short chord
  0.66 m, LTB negligible"). Otherwise return ESCALATE with the list. Put the count and the reason in the hand-back
  as "no member-buckling check".

### A-05 MAJOR: the self-equilibrating blind spot and the combination factors have no proof, but the hand-back claims there is one
- **Where:** tools/README.md:95 and 229-231; combo_check.py:19-21; equilibrium_check.py:18-19;
  sofistik-results-proof/SKILL.md:197-198 and 376.
- **What is wrong:**
  - The scripts send the barrier (17/18), temperature (91/92) and EHF blind spot to an "E3/C4 member-force proof".
    No script or skill state implements it (grep finds only references).
  - combo_check is forward from the .dat. It proves that SOFiSTiK did what the .dat says. It does not prove that the
    gamma and psi values are right for EN 1990 Table A1.2(B) with the UK NA (psi0 Cat C 0.7, Cat H 0.7, wind 0.5,
    T 0.6; gamma_G 1.35/1.0; gamma_Q 1.5; EQU 1.10/0.90/1.5).
  - Despite both gaps, FOR WING says "Each combination is the intended sum of its load cases".
- **Fix:**
  - (a) Add an independent factor table to expected.json, taken from the audit (per combination: action -> gamma x
    psi). Have combo_check compare the .dat COPY factors with it.
  - (b) Implement C4 (beam forces of one member in 135/136 against the factored sum of its building blocks), or
    keep ESCALATE.
  - (c) Reword FOR WING: "combinations match their definition in the input. Factors were checked against <table>.
    Barrier and temperature parts are not proven".

### A-06 MAJOR: the equilibrium tolerance is taken against the total gross, so a component can be short by up to about 9 % and still pass
- **Where:** tools/equilibrium_check.py:93-102.
- **What is wrong:** `ref = gross` (the sum of |force| over all objects) is used for every component. For a wind case
  the vertical uplift dominates the gross. That hides errors in the lateral component, which is the one that matters
  for sway, bracing and alpha_cr.
- **Evidence:** FI-3. LC 21: 6 kN (2.2 % of the lateral wind) gives PASS, 25 kN (9 %) gives ESCALATE, and only above
  25.5 kN is it FAIL. The generator totals are exact sums of the same geometry, so a linear FE reaction sum should
  agree to about 0.01 %.
- **Fix:** Use a per-component reference `ref_j = sum |F_j| per object` (add `gross_kN_xyz` to expected.json).
  Tighten PASS to 0.1 % + 0.05 kN, and ESCALATE to 0.5 %. After the first clean run, record the observed residuals
  as calibration evidence.

### A-07 MAJOR: the alpha_cr mesh rule rests on an unverified number from the brief
- **Where:** sofistik-results-proof/SKILL.md:253 and 104; sofistik-cadinp-author/SKILL.md:76 and 153 ("26016 values
  in Reference": there is no such value in the Reference).
- **What is wrong:** `eigen_el_per_span` is typed into the header and never measured. Too coarse a mesh gives
  buckling factors that are too high (unconservative), and that is exactly how "alpha_cr >= 10 -> non-sway" could be
  wrong. A Haiku given no value would invent one or stop.
- **Fix:** Measure the mesh. The beam_map (`cdb_beam_forces ends_only`) already gives the beams per SLN. Add a
  `member_check.py mesh` step that prints the minimum elements per SLN for the members that carry compression in the
  PLCs. Fail closed when it is below 8. Take the value out of the brief.

### A-08 MINOR: the alpha_cr PASS is worded for all 47 combinations, but only 6 primary load cases are analysed
- **Where:** sofistik-results-proof/SKILL.md:254 and 377; member_check.py:145.
- **What is wrong:** The PLCs are 102, 119 (+X only) and 145-148. The skill prints "non-sway, first-order BDK valid"
  for all member combinations, including 120-130, 136-139 and 151-154. For 26016 the maximum-gravity cases are
  covered, so the risk is small. The statement is still broader than the evidence.
- **Fix:** Write the PLC list into the G6 proof and into FOR WING ("for combinations 102, 119, 145-148").
  Return ESCALATE if a member LC with a higher total vertical load than every PLC exists. load_cases `dead_load_factors`
  and sums give this.

### A-09 MAJOR: the scorecard can give GREEN with hand-checks missing and with members over 1.0
- **Where:** tools/scorecard.py:95-116; sofistik-results-proof/SKILL.md:333.
- **What is wrong:**
  - The scorecard does not check that every pick has a hand line, so 1 of 7 checked still gives GREEN.
  - It does not read `stats.n_eta_gt_1`. Members over 1.0 count only through Haiku's own G8 P-PROOF line, which is
    ESCALATE (AMBER), not RED.
  - A member failing at 1.3 that is not in the top 3 BDK/AQB picks stays AMBER at worst.
- **Evidence:** FI-5 gives GREEN, exit 0.
- **Fix:** In the scorecard:
  - Return RED if `set(hand members) != set(picks)`.
  - Return RED if `stats.n_eta_gt_1 > 0` (report only; a failing structure is RED).
  - Recompute G8 from the files instead of trusting the P-PROOF verdict.

### A-10 MAJOR: the holding-down rule and the reaction text assume a Z-up model
- **Where:** sofistik-results-proof/SKILL.md:330 and 408 (compare 123).
- **What is wrong:** "pz < 0 means the support must pull down" and "gravity gives positive pz" are true only for
  Z up (26016: `SYST ... GDIR NEGZ`, check_v2 line 72). SOFiSTiK's usual default is GDIR POSZ, as in BE13
  (`GDIR POSZ`). In a Z-down model every gravity reaction is negative. The skill would then report the largest
  gravity reaction as a "holding-down force" and miss real uplift (pz > 0). The convention itself (force of the
  support on the structure, +Z load -> pz -1) is correct per project-sofistik-mcp memory.
- **Fix:** Read GDIR from the .dat (the SYST record), or take the sign of the LC 1 reaction. Define "uplift" as a
  reaction with the opposite sign to the self-weight reaction. Replace the 26016 example in line 408 with that rule.

### A-11 MAJOR: the plain-language hand-back for Wing overstates what was proven
- **Where:** sofistik-results-proof/SKILL.md:368-381.
- **What is wrong:**
  - "The loads add up within x %": self-weight LC 1 is never checked (A-17), and self-equilibrating LCs are vacuous.
  - "Each combination is the intended sum": see A-02 and A-05.
  - "Sway check ... non-sway": see A-07 and A-08.
  - "n by AQB only" does not say that these members have no buckling check: see A-01 and A-04.
  - "an independent EN 1993-1-1 hand check": it shares BDK's restraint, Lcr and load-height assumptions. Its LC is
    AQB's governing LC, not BDK's (A-14).
  - The "not checked" line leaves out: AQB-only member buckling, combinations 136-139/222-223, holding-down and
    anchorage under EQU (A-12), horizontal SLS, and pattern LL with wind.
  - After a STOP (for example S7-UNCALIBRATED), the template still invites the utilisation sentences.
- **Fix:** Rewrite FOR WING with the scope stated for each claim, as in the fixes above. Add a STOP variant that
  contains no result numbers except the gates that passed.

### A-12 MINOR: EQU 131-134 is correctly kept out of member design, but the holding-down capacity is never checked or listed
- **Where:** sofistik-results-proof/SKILL.md:330 and 368; cadinp-author:168.
- **What is wrong:** Keeping EQU out of the STR member set agrees with EN 1990 A1.3.1 and Table A1.2(A) (UK NA
  1.10/0.90/1.5; the audit's 0.9G + 1.5W is right). The anchorage, base and tension-column load path still has to
  resist the EQU uplift, and the skill reports it only as "info".
- **Fix:** Add "holding-down bolts/anchorage under EQU 131-134 (max uplift <v> kN [r..])" to "not checked" and to
  FOR WING.

### A-13 MINOR: the largest-compression pick is hand-checked under the wrong load case and can be cut off
- **Where:** member_check.py:410-413 (`lc_compression` is set but `lc` stays lc_aqb, and the list is cut at 20 after
  the random picks); SKILL.md:291-293 uses `<lc>`.
- **Fix:** Use `lc_compression` for that pick's forces. Add the compression pick before the random picks.

### A-14 MINOR: the BDK comparison is an envelope against a single LC
- **Where:** member_check.py:575-577; README:464.
- **What is wrong:** `eta_bdk` is BDK's envelope over 47 LCs, while the hand value is for the AQB-governing LC only.
  Agreement within max(0.10, 10 %) is then partly coincidence. The tolerance is acceptable only because of the
  0.9-1.1 band.
- **Fix:** Hand-check every member LC for the picked member. That is 47 cheap `cdb_beam_forces` reads, or one
  envelope read per member. Compare the maximum with `eta_bdk`. Or take BDK's governing LC from the .prt ECHO SUM.

### A-15 MINOR: the commands after calibration need cdb_read_key, which results-proof does not allow
- **Where:** README:448-456 against sofistik-results-proof/SKILL.md:45-47.
- **Fix:** Add cdb_read_key (read-only) to the allowed list for S7b. Otherwise Haiku must either break the list or
  STOP.

### A-16 MINOR: Haiku can get past "UNCALIBRATED" with a calibration file of its own
- **Where:** member_check.py:76-79 and 613 (a non-default `--calibration` gives only ESCALATE, and P-SCRIPT continues
  on ESCALATE); the results-proof NEVER list does not forbid editing calibration.json.
- **What is wrong:** The rules "omega" and "omega2" differ by a power, so a guessed rule can turn alpha 4 into 16.
- **Fix:** Make a non-default calibration path CANNOT_RUN unless an env var such as `TOOLS_TEST=1` is set. Add
  "never edit tools/calibration.json" to NEVER. Optionally store the sha256 of calibration.json in the README.

### A-17 MINOR: AMBER becomes the normal result, which teaches readers to ignore it
- **Where:** scorecard.py:37 (glob `*ledger*` is case-sensitive, but the ledger is `W/LEDGER.md`, and the skill calls
  the scorecard without `--ledger`, SKILL.md:324); make_expected lists LC 1 in `not_expected`, so G4 is always
  ESCALATE.
- **What is wrong:** SKILL.md:197 claims "Self-weight LC 1 within 2 %", which no script does.
- **Fix:** Match the glob case-insensitively, or pass `--ledger W/LEDGER.md`. Implement E2 (A_cm2 x length x 78.5
  from cdb_overview) or correct the skill text.

### A-18 MINOR: a receipt does not tie the number to its meaning
- **Where:** receipts.py:96-97.
- **What is wrong:** Any occurrence of the value anywhere in the raw file is accepted. A wrong quote that happens to
  equal another number in the file gets a valid receipt.
- **Fix:** Require `--path` (for example `overall.N.min.value`) and check the value at that path.

### A-19 MINOR: cadinp-author overrides the lead's member LC set
- **Where:** sofistik-cadinp-author/SKILL.md:168.
- **What is wrong:** Any member_lcs other than the hard-coded 26016 list is replaced by that list. This blocks
  legitimate new ULS combinations (for example pattern LL with wind).
- **Fix:** Refuse only EQU, SLS, MAXIMA and eigen numbers. Accept a lead-approved superset and record it.

### A-20 MINOR: the "Order of parts" puts the optional TH2 block after BDK
- **Where:** cadinp-author:249-253; check_v2 77356 (`-PROG ASE urs:9210` after BDK 71268, before AQB 77365).
- **What is wrong:** If the lead enables it in the same file, BDK checks first-order forces while AQB checks TH2
  forces, and the MAXIMA envelopes go stale.
- **Fix:** State that a TH2 re-run belongs before BDK and AQB, and that MAXIMA must be re-run after it.

### A-21 MINOR: the G8 deflection check is a crude global number but is presented as a deflection check
- **Where:** SKILL.md:331 and 369.
- **What is wrong:** It takes the absolute maximum |uz| at any node over SLS 201-223 (including G and column
  shortening) and compares it with one limit. There is no span-relative check and no horizontal (H/300) check.
- **Fix:** Call it "global plausibility" in the hand-back. List the span deflection and the horizontal sway under
  "not checked".

### A-22 MINOR: the exit-code semantics differ between the skill and the scorecard
- **Where:** member_check.py (hand), _common.RANK (CANNOT_RUN ranks above FAIL), SKILL.md:308.
- **What is wrong:** For hand exit 3 the skill says "ESCALATE, go on", but the scorecard turns it RED. Because
  CANNOT_RUN ranks above FAIL, a FAIL check followed by an `nc()` reaches the skill as exit 3 ("not hand-checked").
- **Fix:** Use one rule. FAIL should outrank CANNOT_RUN inside a single member check.

### A-23 MINOR: the BDK calibration on 3 members can lock onto a partial utilisation field
- **Where:** README:410-415; calibration.json bdk.how.
- **Fix:** Pick the calibration members so that the governing ECHO SUM column differs between them (n-y, m-y, nm-y).
  Require equality to 0.01 on at least 5 members.

### A-24 MINOR: the canary does not cover the data the proofs actually use
- **Where:** canary_check.py.
- **What is wrong:** It proves the support, node, beam and envelope readers and the pz sign. G4 and G5 read
  `cdb_load_cases.sum_reactions_kN` (CLC_CTRL), and alpha uses the kind-4 eigen rows. Neither is canaried. Horizontal
  components and their signs are not either.
- **Fix:** Add `cdb_load_cases(load_cases="1-2")` on the canary and check `sum_reactions_kN = [0, 0, -1/-2]`. Add an
  inclined or lateral load to the self-test later.

## Checked and found sound (no finding)
- The UK NA factors in the audit and the skills: wind psi0 0.5 (not 0.6), Cat H psi0 0.7 with psi1 = psi2 = 0,
  T psi0 0.6, 6.10 with gamma_G 1.35/1.0, EQU 0.9G + 1.5W.
- MAXIMA ACT restating the factors (gotcha 7).
- EQU 131-134 kept out of the member set.
- alpha_cr bands. The lowest positive factor over all modes is a sound lower bound, so local modes only make the
  result conservative. 10 matches EN 1993-1-1 5.2.1(3), and the < 3 TH3 note matches 5.2.2(5)B.
- The reaction sign convention (R + F = 0, +Z load -> pz -1) matches the project memory and the self-test.
- TH2 combinations are not superposed (ESCALATE).
- While UNCALIBRATED, `alpha` and `collect` refuse (exit 3 -> S7-UNCALIBRATED -> STOP). That is fail-closed, subject
  to A-16.
- The BE13 calibration route uses the same `SYST PLC` / `EIGE n BUCK LC m LMIN AUTO` storage as 26016.
- The hand-vs-AQB tolerance of 0.05 and the 0.9-1.1 marginal band are reasonable.
- The run-and-fix gate rules: never stop or retry, the lock rules, and the timeout rule that only shortens.

## Re-verification (reviewer A, after the 12_TRIAGE fixes)
Re-checked against the current skills and tools. Nothing was edited. The test suite gives **51 passed, 0 failed**.

### My fault injections on the current tools
| FI | Before | Now | Status |
|---|---|---|---|
| FI-1 AQB-only member, hand 6.3 = 1.30 | PASS exit 0 | **FAIL exit 1** (`G7_bdk_hand_only` "hand 6.3 = 1.299 > 1.1") | fixed |
| FI-2 top flange 1.007, shear centre 0.894 | PASS | **ESCALATE exit 2** (max of the two is used, marginal) | fixed |
| FI-3 LC 21 lateral reaction short by 1 kN / 6 kN / 25 kN | PASS / PASS / ESCALATE | **ESCALATE / FAIL / FAIL** (per-component `gross_kN_xyz`) | fixed |
| FI-4 check_v2, combinations 136/137 x1.5 | PASS | **FAIL exit 1** (`C1_136`, `C1_137` FAIL, R_own = 0 for force-free temperature) | fixed |
| FI-5 picks not hand-checked + 3 members > 1.0 | GREEN | **RED exit 1**. Without `--ledger` it is also RED; the ledger is now found case-insensitively | fixed |

### Two new fault injections
| FI | Fault | Result | Status |
|---|---|---|---|
| FI-6 | check_v2 copy with `STO#GINF 1.35` (G "favourable" factor in the uplift combinations 107-110) and `STO#GEQU 1.1` (EQU 131-134 with G at 1.1 instead of 0.9). Both make uplift and holding-down unconservative. Reactions are consistent with that .dat, as a real run would give. | `C4_107` **PASS**, `C4_131` **PASS**, `factor_findings []` | **got through** |
| FI-7 | AQB-only member S12, hand-checked only at its AQB-governing LC 102 (bending). A second member LC 145 has N = -400 kN. | One LC: **PASS exit 0** (hand 6.3 = 0.398). With `--extra-forces` for LC 145: FAIL (2.249). The skill asks for extra forces only when exit 2 contains "give --extra-forces", so this PASS stands | **got through** |

### Status of A-01 to A-24
| ID | Status | Evidence |
|---|---|---|
| A-01 | **PARTLY** | member_check.py:675-687: the hand 6.3 value now governs (FI-1 FAIL). But the hand-only branch PASSes on a single LC: `all_lcs` is ignored there, unlike the BDK branch (route_verdict, :520-533). See FI-7 and the new finding N-02 |
| A-02 | CLOSED | combo_check.py:22-24 and 196-215 (mixed combinations: R_own from expected or force-free, else ESCALATE). scorecard.py:150-155 turns RED for any delegated combination with no C1. FI-4 |
| A-03 | CLOSED | member_check.py:510-518 and 640-644 (max of shear centre and top flange until `ltb_load_height` is CALIBRATED). FI-2 |
| A-04 | CLOSED | coverage_census.py:9, 42, 102-111 (AQB-only without a lead reason gives ESCALATE). SKILL.md S7b census exit 2 |
| A-05 | **PARTLY** | The self-equilibrating parts now ESCALATE (combo_check C5). The factor check C4 (combo_check.py:120-170) only tests that each factor belongs to the allowed set: G {1.35, 1.25, 1.0} for STR, {1.1, 0.9} for EQU. It cannot tell favourable from unfavourable, so it misses FI-6. See the new finding N-01 |
| A-06 | CLOSED | equilibrium_check.py:15-23, `TOL` 0.1 %/1 % per component. FI-3 |
| A-07 | CLOSED | member_check.py mesh_count (about line 692). SKILL.md:296 and 304 (`G6_mesh` measured from the beam map; below 8 gives NOT PROVEN) |
| A-08 | CLOSED | SKILL.md:305 and 425 (wording limited to the listed primary combinations) |
| A-09 | CLOSED | scorecard.py:108-145. FI-5 |
| A-10 | CLOSED | holding_down.py:10-14 and 39-67 (gravity sign from the LC 1 reaction). SKILL.md G8 table and the load-case map note |
| A-11 | **PARTLY** | SKILL.md:420-431 is now scoped for each claim, has a not-checked list and a STOP version. One sentence still overstates: "The combinations match the input file and its EN 1990 + UK NA factors". After FI-6 it can only say "factors are allowed EN 1990 + UK NA values", not that they are the right ones for each combination |
| A-12 | CLOSED | holding_down.py + SKILL.md:416-418 ("holding-down bolts/anchorage under EQU" listed as not checked) |
| A-13 | CLOSED | member_check.py:437-450 (compression pick under its own LC, before the random picks, never capped) |
| A-14 | **PARTLY** | route_verdict `governing_lc_checked` plus the `--extra-forces` route close it for BDK members. The hand-only (AQB-only) branch is not covered: FI-7 |
| A-15 | CLOSED | SKILL.md:45-47 (cdb_read_key allowed in S7b) |
| A-16 | CLOSED | member_check.py:102-109 and 835-843 (CANNOT_RUN unless TOOLS_TEST=1). SKILL.md:23 NEVER |
| A-17 | CLOSED | scorecard.py:41 (case-insensitive ledger search). SKILL.md:241 and 418 (self-weight disclosed when it is not checked) |
| A-18 | CLOSED | receipts.py:6, 11, 106 (`--path` required and the value is checked at that path) |
| A-19 | CLOSED | cadinp-author SKILL.md:176-177 (STOP S-CONFIRM, never rewritten) |
| A-20 | CLOSED | cadinp-author SKILL.md:16, 146 and 174 (no TH2 in Haiku's templates; an active TH2 block gives STOP) |
| A-21 | CLOSED | results-proof G8 table ("one global number, not a span or sway check") and the not-checked list |
| A-22 | CLOSED | scorecard.py:111-114. SKILL.md S7c ("FAIL outranks a check that could not run") |
| A-23 | CLOSED | README.md:383 (5 members, 2 or more different governing columns, else CANNOT_RUN) |
| A-24 | CLOSED | canary_check.py:13, 23 and 40 (`g0_load_cases_1_2` sums) |

### New findings
**N-01 MAJOR, combo_check.py:120-170 (C4)**
- **Problem:** The factor check is set membership only. An uplift (STR) combination with G at 1.35, or an EQU
  combination with G at 1.10, PASSes. Both are the classic unconservative holding-down errors (FI-6). The FOR WING
  sentence "combinations match ... EN 1990 + UK NA factors" then overstates.
- **Fix:**
  - Give expected.json an intended factor per (combination, action family), written by the generator from the audit
    table, and compare exactly (1e-3).
  - At minimum: a combination whose title or class contains "uplift" or EQU, or that has W with an upward
    resultant, must have G at the inferior value (1.0 STR, 0.9 EQU). Otherwise FAIL.
  - Reword FOR WING to "factors are allowed EN 1990 + UK NA values" until the exact comparison exists.

**N-02 MAJOR, member_check.py:675-687, plus results-proof SKILL.md:341-343**
- **Problem:** For an AQB-only member, the hand 6.3 check runs only at the AQB-governing LC (the worst cross-section
  case), which is usually not the buckling-governing LC. `G7_bdk_hand_only` PASSes on that single LC (FI-7: PASS
  0.398, while LC 145 gives 2.249).
- **Fix:** In the hand-only branch, PASS only when `all_lcs` is true. Otherwise return ESCALATE with
  "give --extra-forces for all member LCs", which the skill's step 2c already handles.
- **Also:** AQB-only members that are not picked get no buckling check at all. That is disclosed in FOR WING and by
  the census ESCALATE, so it is acceptable as long as the disclosure stays.

**N-03 MINOR, equilibrium_check.py `TOL` 0.1 %/1 %**
- **Problem:** FAIL above 1 % now gives STOP S6-EQUIL. These tolerances have not been seen against a real 26016 run.
  If SOFiLOAD distributes area or projected loads slightly differently from the generator totals, every run will
  STOP. That is safe, but it could waste PC time.
- **Fix:** Record the residuals of the first clean run as calibration evidence before relying on the 1 % FAIL.

**Note, not a finding**
- `G6_mesh` counts beams per SLN. The short ring chords of 0.66-1.04 m will probably have fewer than 8 elements, so
  alpha_cr may never PASS on 26016. That is conservative.
- **Suggestion:** limit the mesh check to SLNs in compression in the primary combinations (`--forces`), which the
  function already supports. The skill should pass it.

### Verdict
- 19 of 24 findings are closed, 4 are partly closed (A-01, A-05, A-11, A-14), and none is still fully open.
- FI-1 to FI-5 now FAIL, ESCALATE or RED as they should.
- Two new MAJOR findings, N-01 and N-02, both shown by fault injection. No new BLOCKER.
