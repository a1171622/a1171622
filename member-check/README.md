# Member check workflow: SOFiSTiK forces -> design code -> tables and pictures

The idea in one line: **SOFiSTiK does the analysis, this tool does the code check**, the same way the EN 1993
beam-column spreadsheet does it by hand, but for every member and every load combination at once. The design code is
a plug-in, so AS 4100 (or another code) can be added later without touching the rest.

```
 SOFiSTiK .cdb ──(MCP: cdb_beam_forces)──> forces.csv.gz ─┐
 SOFiSTiK .dat (sections, structural lines, BDK members) ──┼─> memcheck.run ──> members.csv, checks.csv, results.json
 engineer's choices (members_input.csv, optional) ─────────┘          │
                                                                      └─> memcheck.plots ──> utilisation_plan.png
                                                                                             assumptions_plan.png
                                                                                             bdk_comparison.png
```

## What is checked (EN 1993-1-1, UK NA)

The calculation in `memcheck/codes/en1993_1_1.py` is the EN 1993-1-1 beam-column spreadsheet
(`/mnt/project-files/beam-column-calc/EC3_beam_column_ULS.xlsx`) written as code. `tests/test_vs_workbook.py` fills
the real spreadsheet with 24 random cases, recalculates it and compares 58 values each: they agree to 1e-14.

- At every result station: 6.2.3/6.2.4 axial, 6.2.6 shear (with torsion 6.2.7(9)), 6.2.5/6.2.8 bending with shear,
  6.2.9 bending + axial (biaxial).
- Per buckling length: 6.3.1 flexural (y-y, z-z) and torsional buckling, 6.3.2.3 lateral-torsional buckling
  (rolled sections, UK NA, f with kc = 1/sqrt(C1)), 6.3.3 interaction eq. 6.61 / 6.62 (Annex B, as BDK MTHD 2;
  Annex A available).
- Hollow sections (SHS/RHS/CHS, EN 10210) are included, which the spreadsheet does not have.

## Buckling assumptions (the engineer's choices)

Defaults reproduce the BDK file of the model. They can be changed per member in a `members_input.csv`
(`--overrides`), one row per member, blank = default:

| column | default | meaning |
|---|---|---|
| `Ly_mode` | `member` | Lcr,y over the whole member (as BDK) or `segment` = between restraints |
| `k_y`, `k_z`, `k_LT` | 1.0 | factors on the buckling lengths |
| `zg_mm` | 0 | load height above the shear centre (+ = top flange load, destabilising) |
| `mcr_method` | `eigen` | `eigen` = Mcr from the real moment diagram and the restraints (like BDK / LTBeam); `formula` = SN003b with C1 (the spreadsheet) |
| `c1_method` | `diagram` | C1 from the real diagram, or `one` (C1 = 1, conservative) |
| `lt_at_lateral` | no | yes = a ring beam (sideways restraint only) also ends the LTB length |
| `sway` | no | yes = sway buckling mode: Cmy = Cmz = 0.9 (Table B.3) |
| `torsion_restrained` | no | yes = no LTB (continuous restraint, e.g. a deck fixed to the top flange) |

Restraints come from the BDK block of the .dat: `CY+DX` (a column: holds sideways movement and twist) ends an LTB
length; `CY` (ring beams only: holds sideways movement at the beam centre, twist free) is used as a support inside
the Mcr buckling solver (`memcheck/ltb.py`). The solver is checked against the published C1 tables in
`tests/test_ltb.py`.

## Limits (from the independent review, 2 Nov 2026)

- Class 4 sections are flagged (utilisation 9.99, "check by hand"), not designed: no effective properties yet.
- Torsion: St Venant shear stress only; warping (bimoment) stresses are not added. Fine where Mt is small.
- N, My and Mz are each the worst value over the buckling length, combined (conservative; BDK combines section by
  section, so it can be lower).
- kc uses C1 from the moment shape alone (slightly conservative where ring beams restrain the member).
- Joined lines are assumed to keep the same local z axis (true for the 26016 radials).

## How to run it (26016 v16 as the example)

1. Forces out of SOFiSTiK. In Claude, call the MCP tool `cdb_beam_forces` per load case (two calls per load case,
   because of the row limit: groups `11-15,21-24,60,61` and `25,31,35`). The results are saved as files, then
   `python scripts/harvest_mcp.py --src <saved results folder> --store forces/ --out forces.csv.gz`.
2. Only when SOFiMSHC split structural lines (lines numbered above the .dat ones): read CBEAM (`cdb_read_key`
   100/0) and the nodes (`cdb_nodes`), then `python scripts/make_beam_pos.py --dat model.dat --cbeam cbeam.json
   --nodes nodes.json --out beam_pos.json`.
3. Check: `python -m memcheck.run --dat model.dat --forces forces.csv.gz --erg model.erg --beam-pos beam_pos.json
   --out results/` (`--erg` only adds the BDK comparison columns).
4. Pictures: `python -m memcheck.plots --dat model.dat --results results/results.json --out results/
   --forces forces.csv.gz --beam-pos beam_pos.json --worked 263 --title "26016 v16"`.

Everything is plain Python 3 + numpy + matplotlib. Run times for 26016 (407 members, 43 combinations): about 80 s.

## Adding another code (AS 4100)

Write `memcheck/codes/as4100.py` with the same two functions as `codes/en1993.py`:
`station_checks(...)` (section capacity at each station) and `segment_checks(...)` (member capacity per buckling
length). The extractor, members, restraints, Mcr solver (AS 4100 uses it as Mo), tables and pictures stay the same.
Then `--code AS4100`. The stub lists the clauses to implement.

## Files

- `memcheck/codes/en1993_1_1.py` EN 1993-1-1 calculation (spreadsheet names), `codes/en1993.py` plug-in,
  `codes/base.py` the plug-in interface, `codes/as4100.py` stub
- `memcheck/sofistik.py` reads the .dat (sections, lines, BDK members), forces, BDK/AQB results from the .erg
- `memcheck/members.py` members, positions, restraints, force diagrams; `memcheck/ltb.py` Mcr solver
- `memcheck/run.py` the run; `memcheck/plots.py` the pictures
- `projects/26016_v16/` results of the first run (tables + pictures + COMPARISON.md)
