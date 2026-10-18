# Proof tools (06_TOOLS_CONTRACT.md)

Stdlib-only Python scripts that turn saved SOFiSTiK inputs and saved MCP `cdb_*` results into verdicts.
Run every script as `python3 -I tools/<script> ... --workdir W`; `--help` prints the usage and the input shapes.

**Output contract (all scripts).** Each script prints one JSON object
`{"tool", "verdict": PASS|FAIL|ESCALATE|CANNOT_RUN, "checks": [{"id", "verdict", ...}], "notes", "time_utc", "inputs": {role: {path, sha256}}, ...}`
and appends the same object as one line to `W/proofs.jsonl`. The exit code is 0 PASS, 1 FAIL, 2 ESCALATE or
3 CANNOT_RUN. A usage error also exits 3 with a JSON object, never argparse's exit 2. No tolerance can be changed
from the command line. The overall verdict is the worst check, ranked PASS < ESCALATE < CANNOT_RUN < FAIL: a FAIL is
never hidden behind a check that could not run (review A-22).

**Run the tools with a Bash timeout of 300000 ms (5 min) or more.** mutation_drill.py on a 26016 file takes about
2 minutes; dat_lint.py / combo_check.py on a 26016 master take 10-40 s.

**Three scripts print one plain line before the JSON** (the skills grep that line; the JSON is the last line):
`expand_master.py` (`EXPANDED <n>` / `EXPAND_ERROR ...`), `transfer_check.py` (`DIFF ...`, `<name> <n> lines
compared`, `TRANSFER_OK` / `TRANSFER_BAD first=<file>:<line>`) and `run_history_tail.py` (`HIST ...` / `HIST none`).

**Saved tool results.** Haiku saves MCP results by hand, so `_common.unwrap()` accepts all of these shapes and nothing else:
- the bare result
- `{"result": ...}`
- `{"structuredContent": ...}`
- `{"content": [{"type": "text", "text": "<json>"}]}`
- `{"rows": [...]}`, the shape `server.py` uses to wrap list results
- any of the above with a UTF-8 BOM, re-indented, or inside a ```json fence

A missing field, or a field set to `null`, is never given a default. The script exits CANNOT_RUN (3) and names the field.

**Sign convention.** These sources set it:
- MCP README "Confirmed on SOFiSTiK 2027"
- `selftest.py`, ALL CHECKS PASSED on 17 Oct 2026

A reaction is the force of the support ON the structure. A +1 kN load in +Z gives `pz = -1`. The stored
`sum_reactions_kN` (CLC_CTRL m_rx/ry/rz) has the same sign. Equilibrium is therefore `R + F = 0`. The skill
proves this sign on every session with `canary_check.py` before reading project numbers.

Shared modules:
- `_common.py`: the output contract and the JSON loading described above.
- `_cadinp.py`: a CADINP reader. It covers blocks, `+PROG`/`-PROG`, STO#/LET#/DEL#/RCL, IF/ELSE/ENDIF,
  LOOP/ENDLOOP, arrays, expressions, generation lists `(a b step)` and comma lists. It also builds the SOFiLOAD,
  ASE, MAXIMA, BDK, AQB, SOFiMSHC and AQUA model that the checks use.

Inferred behaviour is marked [I]:
- A SOFiLOAD LC that is defined again replaces the earlier definition (the last one wins). The earlier lines are
  reported as superseded.
- MAXIMA `BASE b` writes LCs b+1 to b+99.
- Trigonometric functions use degrees.

Tests: `python3 -I tools/tests/run_tests.py` (56 tests, including the end-to-end scorecard test and the fault injections FI-1..FI-7 of review A in `test_fault_injections.py`). It needs no pytest; the `test_*` functions also run under pytest.
The real-file tests read the NUL/CR-stripped copies in `$TOOLS_REAL_DIR` and are skipped when those copies are absent.

---

## dat_lint.py (G1)
`dat_lint.py <file.dat> [--sources W/sources.tsv] [--uls "101-130,..."] [--upstream other.dat ...] [--no-include] --workdir W`

Static lint of the .dat. NUL and CR characters are counted and stripped in memory; the file itself is never
edited. Superseded LC definitions are skipped. The rules come from 03_proof_checks.md §3, which holds the evidence:

| Rule | What it checks |
|---|---|
| S1 | Hard-coded load value. Only `#name`, 0, 1 and -1 are allowed. |
| S2 | LC used but not defined. |
| S3 | Line longer than 255 characters (cadinp_1.pdf). |
| S4 | Operator word inside a variable name. |
| S5 | Comma list with more than 25 items. |
| S6 | SV inertia given without a unit. |
| S7 | Load atom counted twice after expanding the COPY tree, a COPY of a FACD LC, or a COPY cycle. |
| S8 | COPY NO/FACT is not a plain `#name` or a number. |
| S9 | IMP LC in a linear ASE run, or QUAD `TYPE DT`. |
| S10 | LC number written by two producers (SOFiLOAD, EIGE, MAXIMA BASE, LCST). |
| S11 | BDK/AQB LC list missing, or not equal to the ULS set. The ULS set is TYPE `(D)` without EQU in the title, or `--uls`. |
| S12 | SYS command or `$(...)` record name. |
| S14 | Undefined variable, or a CADINP structure error. |
| S15 | An `#INCLUDE` that cannot be found, or is nested deeper than 3 levels; with `--no-include`, any `#INCLUDE` line (its text was not linted). |

Every finding is a FAIL. On the real files, 26016_loads_unified.dat and 26016_check_v2.dat, the lint gives
**0 findings**. For check_v2 it notes 55,508 superseded records.

**#INCLUDE (native).** A master is linted with its includes expanded in memory, the server's rule
(sofistik_mcp/solver.py:56, 74, 289-297): `#INCLUDE` / `#INCL...`, looked up in `--sources` (sources.tsv
`<PC name><TAB><cloud path>`) first, then as `<name>` / `<name>.dat` next to the including file and next to the
main file, 3 levels deep. Findings then carry `"src": "<file>:<line>"` (line in the included file) next to `"line"`
(line of the expanded text). Linting the master with `--sources` and linting X from `expand_master.py` give the
same findings (test `test_dat_lint_native_include_and_src`). `--no-include` lints the file as written, as before,
but an `#INCLUDE` line is then an S15 FAIL, so a master can never PASS with its contents unread. `+APPLY` lines
are not expanded and are listed in a note.

**Is `--uls` needed for S11 on a 26016 master?** Not for S11 to run, but pass it anyway. Measured on a master
`#INCLUDE 26016_check_v2.dat` (scratch copy, `--sources`): without `--uls` the ULS set is derived from the .dat as
the 47 TYPE `(D)` LCs without EQU in the title (101-130, 135-139, 141-148, 151-154); every BDK CTRL group's LC list
and the AQB list equal it, and S11 PASSES. With `--uls "101-130,135-139,141-148,151-154"` S11 also PASSES; with
`--uls "101-130,135-139,141-148,151-153"` S11 FAILS on 7 lists ("extra [154]"). The derived set is circular: an
LC missing from the .dat AND from every list, or a ULS combination typed `(R)`, would not be seen. So the skills
pass `--uls <member_lcs>` from the brief header; without it the note "S11 intended ULS set derived from the .dat"
is printed. A master that `#INCLUDE`s both 26016_loads_unified.dat and 26016_check_v2.dat gives 4 S10 findings:
both files hold the same MAXIMA COMB 1-4 BASE 4100-4400 block (loads_unified:7534, check_v2:70676), so check_v2
alone is the master's content.

## expand_master.py (replaces the inline script E)
`expand_master.py <master.dat> <out_expanded.dat> <sources.tsv> [--workdir W]`

Prints `EXPANDED <n>` (lines written to X) and then the JSON line. Same behaviour as script E: one level only;
the master is read as strict UTF-8 and sources with bad bytes replaced; CR is removed; X ends with one newline.
On the scratch 26016 master the output is byte-identical to script E (85,367 lines). The `#INCLUDE` name is looked
up in sources.tsv as written, then by base name, then with `.dat`, then ignoring case.

| Check | Verdict |
|---|---|
| E1_expanded | PASS; a name not in sources.tsv, or an unreadable file: `EXPAND_ERROR <reason>`, nothing written, CANNOT_RUN (3) |
| E2_no_nested_include | ESCALATE when a source has its own `#INCLUDE` (not expanded; the skill's `incl` gotcha check routes it to STOP S-BRIEF) |
| E3_no_apply | ESCALATE when M or a source has a `+APPLY` line (the server would include that file; X does not) |

## transfer_check.py (replaces the inline script V)
`transfer_check.py <raw_dir> <sources.tsv> [--workdir W]`

Compares every `<raw_dir>/xfer__<k>__<PC name>.txt` (read_text_file `text`, lines `N: content`) with line N of the
cloud copy named in sources.tsv (trailing blanks ignored). Prints `DIFF <name> line <i>` (at most 50),
`<name> <n> lines compared` per file, then `TRANSFER_OK` or `TRANSFER_BAD first=<name>:<line>` (`first=none` when
nothing was compared, `first=<name>:missing` when the cloud copy cannot be read). Verdict T1_transfer PASS / FAIL.
One change from script V: `lines compared` counts distinct line numbers, so overlapping windows no longer inflate it.

## run_history_tail.py (replaces the inline script H)
`run_history_tail.py <tail.txt> "<file name of dat>" [--workdir W]`

Reads the saved tail of `run_history.json` (entries written by dashboard.py:293-295, newest last). Prints the same
line as script H: `HIST same file minutes=<m|none> peak_gb=<g|none>`, else `HIST earlier version ...` (same name
without its `_vN` suffix), else `HIST none`. minutes = newest clean run (status `ok` / `ok with warnings`,
dashboard.py:311) seconds/60; peak_gb = max peak_ram_mb of the last 3 runs of that kind /1024, rounded up to 0.1.
A full PC path is reduced to its base name; case is ignored. Verdict PASS (a lookup); unreadable tail:
`HIST error ...`, CANNOT_RUN.

## holding_down.py (G8, review A-10)
`holding_down.py <load_cases.json> <env_support.json> [--sw-lc 1] --workdir W`

The gravity reaction sign comes from the self-weight LC's `sum_reactions_kN` Rz, not from an assumption. An uplift
is the `pz` extreme of `cdb_envelope(what="support")` with the opposite sign: ESCALATE with `uplift_kN`,
`uplift_lc`, `uplift_node` (report only: holding-down bolts are not checked by any tool), else PASS. CANNOT_RUN
when the self-weight LC is missing, its sum is 0, or gravity is not along Z.

## combo_check.py (G5)
`combo_check.py <file.dat> <load_cases.json> --expected <expected.json> [--families '{"25": "W"}'] --workdir W`

`load_cases.json` is the saved `cdb_load_cases` result:
`{"rows": [{"lc", "title", "kind", "kind_name", "action", "factor", "dead_load_factors": [fx, fy, fz], "sum_reactions_kN": [rx, ry, rz], "has_results": [...]}], "cdb", "stale_results_warning"?}`
(results.py `load_cases`). `--expected` is optional on the command line, but without it mixed combinations with
forces of their own and C5 give ESCALATE; the skills always pass it.

**C1 forward superposition.** For each COPY-built combination c:

`pred_c = Σ fact·R_src + (FACD_c / FACD_ref)·R_ref [+ R_own]`

- `fact` is evaluated from the .dat with its own variables, LOOPs and IFs.
- `ref` is the pure self-weight LC: it has FACD, no loads and no COPY.
- Tolerance per component: `|R - pred| <= 0.1 % · Σ|parts| + 0.05 kN`.
- **Mixed combinations** (own load records + COPY, review A-02; 26016 LC 21-24, 136-139, 222-223): `R_own = 0`
  when every own record is force-free (temperature DT/DTXY, line moments); otherwise `R_own = -(F_c - Σ f·F_src)`
  from expected.json; neither possible gives ESCALATE "not superposition-checked". G4 is no longer claimed to
  prove them.

**C3** the norm of `dead_load_factors` equals |FACD| to within 1e-4. A stale warning is a FAIL.

**C4 EN 1990 + UK NA factors** (review A-05), per classed combination: class from TYPE ((D) + EQU in the title =
EQU, (D) = STR 6.10, (R), (F), (P)); action family from the copied LC's TYPE or title, or `--families`.

| Class | G | Variable |
|---|---|---|
| STR | 1.35 / 1.25 / 1.0 | 1.5, 1.5·ψ0, 0 |
| EQU | 1.10 / 0.90 | 1.5, 1.5·ψ0, 0 |
| (R) | 1.0 | 1.0, ψ0, 0 |
| (F) | 1.0 | ψ1, ψ2, 0 |
| (P) | 1.0 | ψ2, 0 |

ψ (UK NA Table NA.A1.1): imposed Cat A-E ψ0 0.7 (E 1.0), roof QH 0.7/0/0, wind 0.5/0.2/0, snow 0.5/0.2/0,
temperature 0.6/0.5/0. FAIL: factor outside the set, FACD 0, or two variable families at their full leading
factor. ESCALATE: unknown action family.

**Intended factors (review N-01, FI-6).** Set membership cannot tell a favourable from an unfavourable G, so C4
also compares with the INTENDED factor:
- (a) a G factor stated in the title (`107 ULS 1.0G+W`, `131 EQU 0.9G+W`) must equal FACD and every G COPY factor;
- (b) with `--expected` holding `combination_factors` (`{"<combo>": {"facd", "copies": {"<lc>": factor}}}`, written
  by make_expected_26016.py from the generator's combination table), FACD and every COPY factor must equal the
  intended value (1e-3) and the copied LCs must be the intended set. A copied LC that the .dat writes as the
  combination's own force-free records (26016 temperature 91/92 in 136-139 and 222-223) is listed under
  `not_compared`.

Each C4 line carries `intended_compared`. On 26016 all 74 classed combinations equal their intended factors.
FI-6 (`STO#GINF 1.35`, `STO#GEQU 1.1`) now FAILs C4_107-110 and C4_131-134, with or without `--expected`.
Without (b), a C4 PASS means only "allowed EN 1990 + UK NA values"; the FOR WING wording must not say more.

**C5 self-equilibrating parts** (review A-05): a copied atom with |F| < 0.5 % of its gross, or a force-free own
record, is ESCALATE "not proven by reactions" (26016: 49 combinations).

TH2/TH3 combinations get ESCALATE, because non-linear results cannot be superposed.

**Blind spot:** a self-equilibrating load that is doubled does not change the reaction sums. The mutation drill
shows this as BLIND; C5 flags every such combination as ESCALATE.

## equilibrium_check.py (G4)
`equilibrium_check.py <load_cases.json> <expected.json> --workdir W`

`expected.json` = `{"load_cases": {"<lc>": {"F_kN": [fx, fy, fz], "gross_kN", "gross_kN_xyz": [gx, gy, gz], "kind": "applied"|"selfweight_estimate", "title"}}, "not_expected": {"<lc>": reason}, "selfweight_lcs": [1], "combinations": [...]}`

**Per-component tolerance** (review A-06). For each component j the reference is `ref_j = gross_kN_xyz[j]`
(Σ over objects of |F_j|), so a lateral shortfall cannot hide behind a large vertical load:

| Kind | PASS | ESCALATE | FAIL |
|---|---|---|---|
| applied | `\|R_j + F_j\| <= 0.1 % ref_j + 0.05 kN` | up to 1 % ref_j + 0.05 kN | anything larger |
| selfweight_estimate | `<= 1 %` | `<= 2 %` | anything larger |

`gross_kN_xyz` is required: an expected.json made before this round gives CANNOT_RUN; regenerate it with
make_expected_26016.py. Summary field `worst_pct_of_ref`.

**Vacuous rule.** When |F| < 0.5 % of gross, or gross is 0, the result is ESCALATE "not proven by reactions".
**Self-weight** LCs in `selfweight_lcs` get a note, not a default ESCALATE (review B09).

**Fail closed:**
- An expected LC missing from the .cdb is a FAIL.
- A calculated LC that has node results but no expected value, and is not a combination, gets ESCALATE.
- Combinations found in the rows are listed in `delegated_to_combo_check`; the scorecard is RED when one of them
  has no `C1_<lc>` line in combo_check (A-02).

### make_expected_26016.py: expected.json for 26016
`make_expected_26016.py <26016 .dat with the unified loads> <out.json> [--generator /mnt/project-files/26016/audit/generator] --workdir W`

How it computes the totals:
- It runs the generator's record table (`gen_unified.py lc_records`, the source that `write_dat.py` turned into the .dat).
- It sums each record with its geometry, the same way `generator/totals.py` does, for every generator LC.
- Projected loads (PXP/PYP/PZP) use the projected length or area.
- Moments and temperatures add no force.
- Gross is the sum of |force vector| per object; `gross_kN_xyz` is the sum of |F_j| per object and component;
  `selfweight_lcs` = [1].
- `combination_factors`: per generator combination (74) the intended FACD and COPY factor of every copied LC
  (gen_unified.py COMBOS, GROUPS and the EHF rule of `combo_records`), evaluated with the same parameter set.

Guard: every STO# value in the .dat must equal the generator parameter set. Any difference gives CANNOT_RUN.
For example, the legacy defaults in the shipped .dat are refused.

Result: 193 LCs, matching 26016_load_audit.md Appendix A (LC 2 Fz -886.6; 11 -2160.7; 21 Fx 277.2 / Fz 993.4;
23 Fy -287.7; 501 6.56; 17 gross 450.1). LC 1 (self-weight) is listed in `not_expected`; the self-weight
estimate is a separate route.

## canary_check.py (G0)
`canary_check.py <selftest_results.json> --workdir W`

The input is ONE merged object. Each key holds the raw saved result of one call on `selftest_cantilever.cdb`:

| Key | Call |
|---|---|
| `g0_node_lc1` | `cdb_node_results(load_case=1, nodes="7")` |
| `g0_support_lc1` | `cdb_support_reactions(load_case=1)` |
| `g0_support_lc2` | `cdb_support_reactions(load_case=2)` |
| `g0_beam_lc1` | `cdb_beam_forces(load_case=1)` |
| `g0_env_1_2` | `cdb_envelope(load_cases="1-2", what="beam")` |
| `g0_load_cases_1_2` | `cdb_load_cases(load_cases="1-2")` (new, required, review A-24) |

The hand values come from selftest.py: HEA 200, Iy 3692 cm4, E 210000, L 6 m, P = +1 / +2 kN in +Z.

| Check | Expected |
|---|---|
| Tip deflection | uz = +9.29 mm ±1 % |
| Tip rotation | ury < 0, \|ury\| = 2.3216 mrad ±1 % |
| Supports | only node 1 has a reaction; pz = -1 / -2 kN ±0.5 %; \|my\| = 6 / 12 kNm |
| Reaction sums | sum_kN.pz and the stored rz have the same sign as the node reactions |
| cdb_load_cases (K2/K3) | LC 1 and 2 are kind 0/1 (calculated) with `sum_reactions_kN` = [0, 0, -1] / [0, 0, -2] (x, y ≤ 1e-3, z ±0.5 %) |
| Beam My along the span | \|My\| = P(L - x) at every station |
| Beam My at the support | My(beam 1, x 0) = -6 kNm ±0.1 % |
| Beam Vz | \|Vz\| max = 1 kN |
| Other components | N, Vy, Mt, Mz ≤ 1e-3 |
| Envelope | found [1, 2]; \|My\| 12 kNm from LC 2 |

A tool error, a stale warning or a truncated result is a FAIL.

## coverage_census.py (H1)
`coverage_census.py <file.dat> <checked_members.json> --workdir W`

`checked_members.json` = `{"source", "bdk_checked": [BDK MEMB ID], "aqb_checked_slns": [SLN], "excluded": {"<SLN>": "reason"}, "aqb_only_reasons"?: {"<SLN>" or "G<group>": "reason"}}`.
`member_check.py collect` writes this file.

Each SOFiMSHC SLN that has an SNO is put in one class:
- BDK
- AQB_ONLY
- EXCLUDED, which needs a non-empty reason
- UNACCOUNTED, which is a FAIL

An SLN without an SNO is NOT_A_MEMBER. A BDK member in the .dat that has no result is a FAIL (silent omission).
A result for an ID that the .dat does not define gets ESCALATE.

**H1_aqb_only_reason** (review A-04): an AQB-only SLN has NO member-buckling check. Each one needs a reason in
`aqb_only_reasons` (by SLN or by group `G<n>`), else ESCALATE with the SLNs listed per group. The lead's reasons go
into the `--excluded` file of `member_check.py collect`, which copies them into checked_members.json. Summary field
`aqb_only_no_buckling_check`.

On 26016_check_v2 with a complete synthetic result set: 379 SLNs in BDK members (311 members), 122 AQB-only,
2 not members, 0 unaccounted.

## receipts.py (A1 / M4)
- `receipts.py add --value V --unit U --tool T --args '<json>' --cdb C --cdb-mtime M --raw W/raw/x.json --path <json.path> --workdir W`
  - `--path` is **required** (review A-18), e.g. `overall.N.min.value` or `rows.3.sum_reactions_kN.2`: the value
    must equal the number at that path of the raw file, else FAIL. (Before: anywhere in the file.)
  - Stores the path, the SHA-256 of the raw file and `mcp_call` (the exact call, e.g.
    `cdb_load_cases(cdb_path="...", load_cases="2")`) in `W/receipts.jsonl`, and prints the receipt id `rN`.
- `receipts.py audit --n 5 --workdir W`
  - Picks N receipts at random. Each `recall` entry has `mcp_call` (the exact MCP call the lead re-makes), the
    `path` and a `then` line (`receipts.py verify --id rN --raw <re-call>.json`); a note per entry says
    `LEAD RE-CALL ...` (review L10).
  - FAILs when a raw file has changed or the value is no longer at its path.
  - Gives ESCALATE when the mtime is missing.
- `receipts.py verify --id rN --raw <re-call>.json --workdir W`
- `--help` prints the usage.

## scorecard.py (A11)
`scorecard.py W [--ledger FILE]`

Reads `W/proofs.jsonl`. For each tool, the last line counts. For `member_check`, every line since the last `pick` counts.

**Mandatory gates:**
- canary_check
- G2_protocol
- A7_run_identity
- equilibrium_check
- mutation_drill
- combo_check
- R6_member_lcs
- G6_alpha_cr
- coverage_census
- member_check
- G8_plausibility
- A12_assumptions
- receipts (audit)

**Grades:**

| Grade | Exit | When |
|---|---|---|
| RED | 1 | A gate is missing, a gate is FAIL or CANNOT_RUN, the proofs used a genuinely different .dat or .cdb (input families below), or a line cannot be read. Also (A-09): a pick (member, lc) without a hand line, a hand FAIL, `stats.n_eta_gt_1` > 0 (or missing), no pick line; (A-02) a combination in equilibrium's `delegated_to_combo_check` without a `C1_<lc>` line. |
| AMBER | 2 | Any ESCALATE (a hand line "not hand-checkable" counts as ESCALATE), a pick without an LC, or the assumptions are not agreed. |
| GREEN | 0 | None of the above. GREEN needs the ledger (`--ledger W/LEDGER.md`, or any file in W whose name contains "ledger" in any case) to say `assumptions_agreed: yes` AND an `A12_assumptions` PASS line. |

The scorecard exits 3 when there are no proofs.

**Gate names.** `member_check alpha` writes tool `member_check_alpha`; the scorecard counts it as the G6_alpha_cr
gate (a P-PROOF line with tool `G6_alpha_cr` is still accepted).

**Input families** (final check M1). Legitimately related inputs are one family; a genuinely different one is RED:
- **.dat:** dat_lint records the master M (`dat`) and, when it expanded `#INCLUDE`s, the checksum of the expanded text
  (`dat_expanded`, byte-identical to expand_master.py's X); expand_master records `master` and `expanded`.
  Checksums recorded in one proof line are linked, so M (dat_lint) and X (combo_check, mutation_drill, collect,
  coverage_census) are one family. A .dat linked to none of them is RED.
- **.cdb:** every `load_cases` input (`W/raw/load_cases.json`, `W/raw/buckling_lcs.json`, ...) is grouped by the
  `cdb` path the server adds to every result (server.py `_cdb_call`). Two .cdb paths are RED. The file must still
  have the recorded checksum, and an LC that appears in two files must have the same stored values; otherwise the
  .cdb changed between the reads, which is RED.

**End-to-end test** (`tests/test_end_to_end.py`): every proof line comes from running the scripts on fixtures
(the five script-less gates through the skills' P-PROOF echo), with a calibrated copy of the tools. It gives AMBER
when the assumptions are not agreed, GREEN when they are, and RED when combo_check reads another .cdb's load cases,
when the load cases of the same .cdb change between reads, or when coverage_census reads another .dat.

## mutation_drill.py (M1-M3)
`mutation_drill.py <file.dat> --workdir W --expected expected.json [--seed 1] [--only NAMES]`

Run it with a **Bash timeout of 300000 ms** or more (review B15). `--expected` is passed to every combo_check run
(mixed combinations, C5) and is needed for the equilibrium_check mutants; without it those rows are n/a.

The drill writes all mutants to `W/mutants/` and never touches the given file. It runs every checker as a
separate `python3 -I` process on a clean baseline and on each mutant.

**Caught** means one of these:
- the target check gets a worse verdict than in the baseline
- for dat_lint, the count for the rule goes up

**BLIND** means the fault changes the reaction sums by less than the tolerance. This is the documented G4/G5 blind
spot; C5 flags those combinations ESCALATE "not proven by reactions".

**Verdict:**
- PASS when all baselines are as expected and every applicable mutant that is not BLIND is caught.
- FAIL when any mutant is missed.

**Catch matrix** on the real files (NUL/CR-stripped scratch copies), `--expected` from make_expected_26016.py
(with `gross_kN_xyz`), 18 Oct 2026 after the fix round:

| Checker | Faults injected | loads_unified | check_v2 |
|---|---|---|---|
| dat_lint | S1 S2 S3 S4 S5 S7 (double atom) S7 (COPY of FACD) S8 S9 S10 S11 S12 S14 | 12/12 (S11 n/a: no BDK) | 13/13 |
| combo_check | double atom, psi x0.8, dropped COPY, sign flip, FACD x1.1, combination missing, stale, **mixed own+COPY x1.5 (FI-4)**, **non-EN 1990 factor 1.2 (C4)**, **favourable G variable set to 1.35 (FI-6, C4_107)**; doubled self-equilibrating atom | 10/10 + BLIND | 10/10 + BLIND |
| equilibrium_check | LC x1.05, sign flip, LC missing, stale, **lateral component 2 % short (FI-3)** | 5/5 | 5/5 |
| canary_check | pz sign, uz +5 %, ury sign, extra support, envelope LC, stale, truncated, **LC-sum sign (A-24)** | 8/8 | 8/8 |
| coverage_census | BDK member dropped, AQB SLN dropped, empty exclusion reason, unknown BDK ID, **AQB-only without reason (A-04)** | n/a | 5/5 |
| receipts | value not in raw, **value at the wrong JSON path (A-18)**, raw edited after receipt | 3/3 | 3/3 |
| scorecard | gate missing, one ESCALATE, ledger not agreed, two .dat versions, **picks not hand-checked (FI-5)**, **members over 1.0 (FI-5)** | 6/6 | 6/6 |
| member_check | AQB off by 0.2, over capacity, wrong section area, elements out of order, **AQB-only buckling ignored (FI-1)**, **top-flange load ignored (FI-2)**, pick LC outside set | 7/7 | 7/7 |

Totals (round 2, 18 Oct 2026): **51/51** caught on loads_unified (2 n/a), **57/57** caught on check_v2, 0 missed, 1 BLIND each (the
doubled self-equilibrating atom). Both drills ran in parallel in about 2 minutes.

## member_check.py (G6 alpha_cr, H1 collect, G7 picks and hand-checks)
Seven subcommands (`--help` and the module docstring give every option):
- `alpha` (G6), `mesh` (G6_mesh, A-07), `calibrate-alpha`, `calibrate-bdk` (A-23)
- `collect` (H1), `pick` and `hand` (G7)

`member results` below gives the commands for alpha and collect. Where the data lives in the CDB is read from
`calibration.json`. Only the lead edits that file, and `--calibration <other file>` is refused (CANNOT_RUN) unless
`TOOLS_TEST=1` is set by the tests (review A-16 / L12). While a source there says UNCALIBRATED, `alpha` and
`collect` exit CANNOT_RUN, and the skill stops S7-UNCALIBRATED.

**mesh / alpha --beam-map** (A-07, round 2). `member_check.py mesh W/raw/beam_map.json --dat <X> [--compression-forces F.json ...] [--all-members] --workdir W`
counts elements per structural line from the ends_only beam map, over SLNs with a section that are **in
compression** (default): from `--compression-forces` (cdb_beam_forces results of the primary combinations, SYST
PLC; rows with N < 0) when given, else from the beam map's own N values (its one LC; noted in `mesh_basis`). With
neither, G6_mesh is ESCALATE "compression members unknown ... (fail closed)". The short 0.66-1.04 m ring chords that
are only in bending therefore no longer block alpha_cr. `--all-members` measures every SLN (the old behaviour).
`eigen_el_per_span` = the smallest count; PASS ≥ 8, else ESCALATE "alpha_cr NOT PROVEN".
`alpha ... --beam-map W/raw/beam_map.json [--dat <X>] [--compression-forces ...] [--all-members]` adds the same
G6_mesh check; without `--beam-map` G6_mesh is ESCALATE (never a silent PASS).

**calibrate-bdk** (A-23). `member_check.py calibrate-bdk --bdk W/raw/bdk_p*.json --prt '{"<member>": [value, "<column>"], ...}' --workdir W`:
at least 5 members and at least 2 different governing ECHO SUM columns (n-y, m-y, nm-y ...), else CANNOT_RUN;
PASS when exactly one record field matches every member within 0.01, and it prints the block for the lead.

**pick**

`member_check.py pick W/member_results.json W/raw/env_uls_beam.json --seed <run_id> --workdir W`

`env_uls_beam.json` is a `cdb_envelope(what="beam")` result. The script reads `overall.N.min {value, lc, sln}`
and `load_cases_found` from it.

What it picks, in this order (keyed by (member, lc); a member can be picked twice under two LCs):
1. the top 3 members by `eta_bdk`, the top 3 by `eta_aqb`
2. **every member with eta ≥ 0.9 (BDK or AQB)** (F-EX2)
3. the member that holds the SLN of N min, under **its own LC** (`overall.N.min.lc`), before the random picks (A-13)
4. 1 member per section, chosen with `random.Random(sha256(run_id))`

Cap 20: only random picks are ever dropped by it. When the mandatory picks (1-3) alone exceed 20, all are kept
and `G7_picks_over_cap` ESCALATEs (exit 2) with `picks_over_cap`; `G7_high_eta_picked` FAILs if a member with
eta ≥ 0.9 is missing from the list (cannot happen by construction; it is the guard).

Output:
- `picks[]`, each with `member, sln, section, lc, eta_bdk, eta_aqb, reason`
- `stats`: `n_members, eta_max, eta_min, n_eta_gt_1, lc_outside_set` and `members_gt_1`
- `n_mandatory`, `n_eta_ge_0_9`, `random_dropped_by_cap`

It gives ESCALATE when `lc_outside_set` is not empty or a pick has no LC. The scorecard is RED when
`n_eta_gt_1` > 0 or a pick has no hand line (A-09).

**hand**

`member_check.py hand W/raw/g7_<m>_<lc>.json W/raw/overview.json W/member_results.json --member M --lc LC [--extra-forces W/raw/g7_<m>_<lc2>.json ...] --workdir W`

Inputs:
- `g7_<m>_<lc>.json` is a `cdb_beam_forces` result: `rows[{beam, sln, x, N, Vy, Vz, Mt, My, Mz}]` and `lc`.
  `--extra-forces` adds the same member under its other LCs: eta_bdk (an envelope over all member LCs) is then
  compared with the hand envelope (A-14); `lcs_hand_checked`, `all_member_lcs_checked`, `per_lc` are reported.
  Comparing an envelope eta with fewer LCs than the member's LCs is ESCALATE, not PASS.
- `overview.json` is a `cdb_overview` result: `sections[{nr, title, A_cm2, Iy_cm4, Iz_cm4}]`.
- A forces file with `truncated` true, or with rows ≥ its `max_rows`, is CANNOT_RUN.

**Building the member.** The rows of the member's SLNs are joined in SLN order, then by beam number, with x
offset by the element lengths [I: the forces carry no geometry].
- A jump in My at a joint larger than 5 % of max|My| + 0.5 kNm gives exit 3.
- The section comes from `sofrep.sections.from_name`. Its area must agree with the CDB `A_cm2` within 3 %, else exit 3.
- When the CDB has Iy < Iz, the forces are rotated to the major axis, the same way as the sofrep cdb_reader.

**Design.** The script runs `sofrep.codes.ec3.design_member` with:
- the UK NA and γM0 = γM1 = 1.0
- L_y = the member length
- L_z = L_LT = the longest span between BDK `CVL CY FIX` points [I]
- load height (A-03): from calibration.json `ltb_load_height`. Until that item is CALIBRATED with rule
  `shear_centre`, hand 6.3 = **max(shear centre, top flange)** (`load_height_rule: "max"`; both values reported as
  `hand_bdk_shear_centre`, `hand_bdk_top_flange`).

**Comparison:**
- `hand_aqb` is the maximum ratio of the 6.2 checks. It must match `eta_aqb` within ±0.05.
- `hand_bdk` is the maximum ratio of the 6.3 checks. It must match `eta_bdk` within max(0.10, 10 %).
- **No eta_bdk (AQB-only member, A-01, N-02):** the hand 6.3 value governs (`G7_bdk_hand_only`): > 1.1 FAIL,
  > 0.9 ESCALATE, else PASS **only when every member LC was hand-checked**; otherwise ESCALATE "give
  --extra-forces for all member LCs" (FI-7: 0.398 at LC 102 alone, 2.249 at LC 145). Without a hand 6.3 value
  the result is CANNOT_RUN, never PASS.

| Exit | Meaning |
|---|---|
| 0 | PASS |
| 2 | Either eta lies in 0.9-1.1, the routes disagree, they differ on PASS/FAIL, or not every member LC was checked. |
| 1 | The SOFiSTiK value and the hand value are both > 1.1, or the hand-only 6.3 value is > 1.1. |
| 3 | Not hand-checkable. A FAIL in another check outranks it (A-22). |

The full MemberDesign is saved to `W/hand/<m>_<lc>.json`. The sofrep path defaults to
`/mnt/project-files/reports/sofistik_report`; set `--sofrep` or `SOFREP_PATH` to change it.

---

## member results

**Status: read it from `calibration.json`, never from this README.** `calibration.json` (next to the scripts) is
the only authoritative status of every calibrated item: `alpha_cr`, `bdk`, `aqb`, `ltb_load_height` and
`server_lifetime`, each with `"status": "UNCALIBRATED" | "CALIBRATED"`. The skills read it there (results-proof S7a
`CAL` lines, run-and-fix S3 `LIFETIME`), e.g.
`python3 -I -c "import json,sys;c=json.load(open(sys.argv[1]));[print('CAL',k,v.get('status')) for k,v in c.items() if isinstance(v,dict)]" T/calibration.json`.
The lead updates only calibration.json after the first-clean-run checks below; this README is not edited for it.
At the time of writing (18 Oct 2026) every item was UNCALIBRATED. Everything below comes from the manuals and from
the vendored `sofistik_daten.py`; none of it had yet been seen in a SOFiSTiK 2027 .cdb written by this project.

### alpha_cr (G6): where it comes from

**How 26016 defines the buckling cases.** ASE `EIGE n ETYP BUCK LC m` computes buckling eigenvalues of the
primary LC (ase_1.pdf §2.16 "Buckling Eigenvalues", pp. 2-96/2-97, pdf 104-105):
- `LC` is the "load case number of the smallest eigen mode shape". The default is 2001, and the modes are stored as
  LC m, m+1, ... (EIGE table, p. 3-97, pdf 203).
- `LMIN AUTO` returns the first positive eigenvalues.
- CTRL BUCK default storage (p. 3-5, pdf 111).

26016 (`26016_check_v2.dat`, ltb/26016_buckling_alphacr_ase.dat) has six eigen runs:

| Buckling LCs | Primary LC |
|---|---|
| 9201-9220 | 102 |
| 9221-9240 | 119 |
| 9241-9260 | 145 |
| 9261-9280 | 146 |
| 9281-9300 | 147 |
| 9301-9320 | 148 |

Each run has 20 modes and is parsed as 6 x `EIGE 20 ETYP BUCK`. These are `buckling_lcs`.

**How the modes are stored.** Each mode is a load case with key 12/LC, class `CLC_EIGE`, kind 4 (vendored
sofistik_daten.py:3334-3361). The record holds:
- `m_nr_mode`
- `m_plc` (the primary LC)
- `m_omega`, documented only as "circular frequency omega = 2*PI*f [rad/sec]"

The manual does not say whether a BUCK run puts the factor λ itself, or something derived from it, into `m_omega`.
**Not established.**

**What the MCP tools can read:**
- `cdb_load_cases(load_cases="9201-9320")` already reads 12/LC for kind 4. It returns `mode`,
  `frequency_Hz = m_omega/2π` and `period_s` (results.py `load_cases`).
- `cdb_read_key(kwh=12, kwl=<lc>, class_name="CLC_EIGE")` returns the raw `m_omega`, `m_plc` and `m_ityp`.

**How alpha_cr_min is produced.** The skill (S7a) runs these steps after calibration:
1. `cdb_load_cases(cdb_path=<cdb>, load_cases="<buckling_lcs>")`, saved as `W/raw/buckling_lcs.json`.
2. `python3 -I T/member_check.py alpha W/raw/buckling_lcs.json --buckling-lcs "<buckling_lcs>" --workdir W`

This outputs `alpha_cr_min` (the lowest positive λ over all modes of all those LCs), `alpha_cr_lc` and
`alpha_cr_mode`. The verdict is PASS for ≥ 10 and ESCALATE for < 10. While UNCALIBRATED, it outputs
`"alpha_cr_min": "UNCALIBRATED"` and exits 3.

**First clean run must check.** This is read-only on an existing .cdb, so it can be done without starting a run:
1. On the BE13 benchmark .cdb (`C:\Sofistik workflow\benchmarks`, be13_buckling_bar.dat, LC 101-104, known
   factors 38.553 / 38.553 / 154.215 / 154.215, sofistik-benchmarks/BENCHMARK_RESULTS.md:15, 71):
   - call `cdb_load_cases(load_cases="101-104")`
   - save the result
   - run `member_check.py calibrate-alpha <saved> --workdir W`
2. The script tests the rules λ = 2πf ("omega"), (2πf)², f and 1/(2πf). It must report exactly one rule within 0.5 %
   of all four factors, and it prints the block to paste into calibration.json.
3. Also call `cdb_read_key(12, 101, "CLC_EIGE")` once and keep it as evidence (raw `m_omega`).
4. If no rule matches, the factor is not in `m_omega`. The rest of the CLC_EIGE record and the ASE .prt
   eigenvalue table must then be compared by hand. Stay UNCALIBRATED until then.
5. Mesh: the eigen run needs ≥ 8 (better 10+) elements per span. Otherwise the factors are too high.

### BDK utilisation (H1/G7)

**How BDK saves results.** `CTRL ... LCST n` is "Loadcase number for results" (bdk_1.pdf CTRL table, pp. 3-10/3-11,
pdf 26-27). For 26016, n = 9100 for all 311 members. BDK saves the **envelope of the maximum utilisation per member**
under LCST for WinGRAF / Result Viewer (p. 3-13, pdf 29); the manual does not name the CDB key. The utilisations of
each combination are not stored. The governing LC per member appears only in the .prt/.lst ECHO SUM table, which has
columns n-y, n-z, m-y, m-z, nm-y, nm-z and Check (p. 4-8, pdf 44).

**Where the key is believed to be [I]:**
- key 127/LCST, class `CDSLN_DES` ("127/LC:Z! Ultimate/Plastic Design results", vendored sofistik_daten.py:10064)
- `m_nr` = design element (member) ID
- utilisation in `m_scbn` ("utilisation level (10) buckling / torsional buckling")

Evidence:
- the shipped example `design_eccs_119_example_1.dat` reads `@KEY 'DSLN_DE0' 951 1` and output column @27
  (reports/sofistik_report/sofistik/AQB_NOTES.md §3.2)
- reports/sofistik_native/research/B_design_checks.md:176-178, 348

**What the MCP tools can read:**
- `cdb_read_key(kwh=127, kwl=9100, class_name="CDSLN_DES", max_records=10, skip=0|10|...)` can read the key:
  32 pages for 311 members at the 20 KB hand-save limit (2 pages of 500 only if the harness saves to files).
- `cdb_load_cases` does not flag it, because its `has_results` only checks keys 24/102/152/162/210
  (results.py:259-261).
- `cdb_read_key` returns only the first 24 values of an array field. The CDSLN_DES fields are scalars.

**First clean run must check:**
1. `kexist` of 127/9100 is 2.
2. `record_count` ≥ 311.
3. The set of `m_nr` equals the 311 MEMB IDs.
4. For 3 members, `m_scbn` (and `m_tcf`) equals the "Check" value in the BDK ECHO SUM table of the .prt, to 0.01.
   Record which field matches in calibration.json `bdk.eta_field`.

### AQB utilisation (H1/G7)

**How AQB saves results.** AQB saves design results "for all combinations (COMB) with an explicit LCST given and for
all single load cases with one of the above types assigned" (aqb_1.pdf p. 3-47, pdf 107; LC/COMB LCST p. 3-3,
pdf 63 and p. 3-54, pdf 114). The utilisation is saved as the **total utilisation** (p. 3-63, pdf 123). In 26016,
AQB runs `BEAM TYPE BEAM` on the 47 ULS LCs (101-130, 135-139, 141-148, 151-154). The results are therefore under
each (D) LC number, not under an LCST.

**Where the key is believed to be [I]:**
- key 107/LC, class `CBEAM_DES` ("107/LC:Z! Ultimate/Plastic Design results", vendored sofistik_daten.py:10019)
- `m_nr` = beam element
- `m_tcf` = "total utilisation level (all effects)"

Evidence:
- reports/sofistik_report/sofistik/AQB_NOTES.md §3.1
- the sofrep CDB reader reads the same record (reports/sofistik_report/sofrep/readers/cdb_reader.py:86, 365-374).
  That is code evidence, not run evidence.

**What the MCP tools can read.** `cdb_read_key(kwh=107, kwl=<lc>, class_name="CBEAM_DES", max_records=500, skip=k)`
can read it, but it has one record per beam station. With ~1,000 or more beams that is hundreds of 10-record pages
per LC, times 47 LCs: impractical by hand (see "Commands after calibration"). Read only the LCs that are needed and
ESCALATE the rest until the server can export results to a file.

**First clean run must check:**
1. 107/101 exists.
2. `m_nr` values are beam numbers that appear in `cdb_beam_forces`.
3. For 3 beams, `m_tcf` equals the AQB utilisation table in the .prt.
4. Whether `m_tcf` is an elastic (σv/fy) or a plastic ratio [I: this decides whether the ±0.05 comparison with the
   6.2 hand check is like-for-like].

### LTB load height (A-03): `ltb_load_height`
**Status: see calibration.json `ltb_load_height.status` (UNCALIBRATED on 18 Oct 2026).** BDK may or may not model the load height (EZA). Until the LTB benchmark
(26016/ltb/26016_ltb_benchmark.dat: a simply supported UB under top-flange load) shows that BDK's eta matches the
sofrep **shear-centre** value, `hand` uses max(shear centre, top flange) for hand 6.3. The lead records the rule in
calibration.json `ltb_load_height.rule` (`shear_centre` or `max`) with the evidence.

### Server lifetime (L9): `server_lifetime` = SERVER_LIFETIME
**Status: see calibration.json `server_lifetime.status` / `value` (UNCALIBRATED on 18 Oct 2026).** Not known: does a run started by `run_calculation` survive the end of the agent session
that started it? Calibration test (lead only; it starts a run, so never while another run is live on the PC):
**a run of 60-120 s, end agent, new agent `get_job_result(job_id)` + `dashboard_status`.**

The run must be longer than run_calculation's own wait: the call waits up to 40 s for the result before it answers
`status: "running"` with a `job_id` (sofistik_mcp/server.py:70 `WAIT_S = 40`, :140-147). The cantilever canary
finishes in a few seconds, inside the call, so it returns no job_id and proves nothing (review A round 2, N7). Use
a run of about 60-120 s, e.g. the BE25c 40-element eigen benchmark or a canary with a LOOP that repeats the
analysis.
1. In an agent session, start that run with `run_calculation`; note the `job_id` of the `running` answer.
2. End that agent session at once, before the run finishes.
3. In a NEW agent session call `get_job_result(job_id)` and `dashboard_status()`.
4. The job is finished with its result, and the .cdb/.prt are written -> `value: "PERSISTENT"`; the run was killed
   -> `value: "DIES_WITH_AGENT"`. Set `status: "CALIBRATED"` with the evidence.
5. The server keeps jobs in memory ("Jobs are forgotten when Claude restarts", server.py:451). If
   `get_job_result` answers "No job ..." but `dashboard_status` / run_history.json show the run finished ok, the
   RUN persisted and only the job record was lost: record that in `evidence`, because the skill must then find
   the result through the dashboard and run_history, not through the job_id.

Until it is CALIBRATED with PERSISTENT, sofistik-run-and-fix stops any run with an estimate above 10 min with
STOP S-CALIB (the skill reads the status with
`python3 -I -c "import json;d=json.load(open('T/calibration.json')).get('server_lifetime',{});print('LIFETIME',d.get('status','MISSING'),d.get('value'))"`;
a run is allowed only on `LIFETIME CALIBRATED PERSISTENT`).

### Commands after calibration (S7b)
**Hand-save limit.** Haiku saves every MCP result by hand, and one saved file must stay at or below about
**200 rows / 20 KB** (the skills' rule). The commands below are sized for that limit.

1. **Beam map:** do NOT read it here. Use `W/raw/beam_map.json` from S7a of sofistik-results-proof
   (cdb_beam_forces `ends_only=true`, `max_rows=121`, beam windows of 60 (about 18 KB a page), merged by P-MERGE).
2. **BDK pages:** `cdb_read_key(cdb_path, kwh=127, kwl=9100, class_name="CDSLN_DES", max_records=10, skip=0|10|20|...)`
   until `skip` reaches `record_count`; save each page as `W/raw/bdk_p<skip>.json`. 26016: 311 members = 32 reads.
3. **AQB pages** for each member LC: `cdb_read_key(cdb_path, kwh=107, kwl=<lc>, class_name="CBEAM_DES", max_records=10, skip=...)`,
   saved as `W/raw/aqb_<lc>_p<skip>.json`.
4. Run collect:
   `python3 -I T/member_check.py collect --dat <dat_local> --bdk W/raw/bdk_p*.json --aqb W/raw/aqb_*.json --beam-map W/raw/beam_map.json [--excluded W/excluded.json] --workdir W`
   - It writes `W/member_results.json` and `W/checked_members.json`.
   - It refuses incomplete pages: the sum of records must equal `record_count`.
   - `W/excluded.json` = `{"excluded": {"<SLN>": reason}, "aqb_only_reasons": {"<SLN>" or "G<group>": reason}}`.

**Bulk member-result extraction is impractical by hand: STOP S7-NEEDS-EXPORT.** CBEAM_DES has one record per
beam station, so AQB on 26016 (about 1,000 or more beams, several stations each, 47 ULS LCs) is tens of thousands
of records: at 10 records per read that is thousands of reads. The results skill therefore estimates the reads
before any marathon (S7b step 2: first page of the BDK key and of the AQB key, `READS = ceil(bdk/10) + n_LC x
ceil(aqb/10)`) and, when `READS` is above 300, stops with **STOP S7-NEEDS-EXPORT** ("bulk member results need MCP
export to file; lead decides"; expected on 26016, not a failure). It never collects a partial set. Only when the
estimate is at most 300 does it read every page; going over 300 reads after all is STOP S-PAGECAP. BDK alone (32
reads on 26016) is feasible, but S7b needs both. **Recommendation for MCP 1.4:** a server-side result export (the
full record set of a key to a file in the cloud folder, returning only its path, sha256 and record_count, plus a
summary such as max `m_tcf` per element and LC), so that collect reads one file instead of thousands of hand-saved
pages.

`member_results.json` contains:
- `member_lcs` and `lcst`
- `members[{member, slns, section, section_nr, material, group, cy_fix_from_start_m, eta_bdk, lc_bdk, eta_aqb, lc_aqb, source}]`

`lc_bdk` is always null, because BDK stores only the envelope, so `pick` uses `lc_aqb` [I]. A member that is only
checked by AQB gets the ID `S<sln>`.
