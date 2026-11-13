# 26016 v19m - ULS member force envelopes (WinGRAF pictures + table)

Model: `26016-member-check\v19m\26016_check_v19m` (v19 + Mz release at the 18 Level 1 r 8.5 ring ends), run 13 Nov 2026.
Everything here was read from a **copy** of the database (`v19m\envelopes\26016_env_v19m.cdb`); the original v19m .cdb was not opened for writing and nothing was re-analysed. No sps.exe was running when I started.

Standalone PDF (A4, cover, 2 table pages, one picture per page with a caption line): `26016_v19m_ULS_envelopes.pdf` (30 pages, 17 MB). Not added to the report.

## 1. Load cases and how the envelope was built

The envelopes **already existed** in the model database, so no new MAXIMA run was needed. They come from the model's own `+PROG MAXIMA urs:7` (excerpt: `maxima_comb3_excerpt.dat`):

- `COMB NO 3 EXTR NONL BASE 4300 TYPE DESI` "ULS envelope (EQU 131-134 apart)": the 43 ULS STR combinations **101-130, 135, 141-148, 151-154**, each `LC NO n TYPE AG1 FACT 1.00`. AG1 = one alternative group: exactly one combination at a time, no factors, no adding. Each envelope value is therefore the value of one complete combination.
- `SUPP COMB 3 EXTR MAMI ETYP AUTO`: max and min of every result type.
- `COMB NO 4 ... BASE 4400 TYPE RARE`: the same for SLS characteristic 201-221.

| quantity | ULS max / min LC | SLS max / min LC |
|---|---|---|
| N | 4321 / 4322 | 4421 / 4422 |
| Vy | 4323 / 4324 | 4423 / 4424 |
| Vz | 4325 / 4326 | 4425 / 4426 |
| Mt | 4327 / 4328 | 4427 / 4428 |
| My | 4329 / 4330 | 4429 / 4430 |
| Mz | 4331 / 4332 | 4431 / 4432 |

Two points differ from the brief:
- The model has 47 ULS combinations = 43 STR (above) + 4 EQU (131-134). EQU is not in the envelope (correct for member design).
- The combinations are **linear** (ASE `SYST PROB LINE`, COPY-built load cases), not second-order PLC cases. PLC 102 / 119 are only used for the alpha_cr buckling runs (6.94 / 7.31).

## 2. Sanity check (envelope vs scan of the 43 combinations)

At **every result station of every beam** (4759 beams) I compared the MAXIMA value with the largest / smallest value read directly from the 43 combination load cases. Largest difference: N 0.0 kN, Vy 1.3e-6, Vz 9.9e-6, Mt 9.9e-6 kNm, My 2.4e-9 kNm, Mz 4.0e-9 kNm (float rounding). SLS: same, largest 8.5e-6. **They match.**

Members asked for (`sanity_check.json`):

| member | My max (LC) | My min (LC) | N max (LC) | N min (LC) | MAXIMA |
|---|---|---|---|---|---|
| SLN 56, group 25 (see note), UB 254 | 136.825 (119) | -163.623 (153) | 45.878 (123) | -16.876 (108) | identical |
| SLN 227, L1 ring r 8.5, 340-360 deg, group 15 | 22.492 (102) | -0.000 (107) | 28.012 (124) | -11.574 (109) | identical |
| column SLN 37, group 13, SHS 150x10 | 5.698 (118) | -2.073 (112) | 25.396 (107) | -151.843 (120) | identical |
| internal stair upper flight stringer (analysis lines 1454-1463, group 60, RHS 200x100x6) | 6.480 (106) | -4.446 (121) | 38.503 (152) | -3.605 (110) | identical |

Note: the brief called SLN 56 "a Level 1 r 8.5 ring beam near 340 deg". In v19m SLN 56 is the **Level 2 outer ring r 12** (group 25, the member with AQB 1.075). The L1 r 8.5 ring segment at 340-360 deg is SLN 227, so I checked both. RESULTS_v19m.md gives SLN 56 node-end My -163.17 for LC 120 (the governing BDK case); the envelope minimum -163.62 is from LC 153.

## 3. Pictures (`png/`, 300 dpi, sheet 25.5 x 30 cm, print at 170 mm wide)

All result pictures: envelope max load case in **red**, min load case in **blue**, drawn together (WinGRAF `LC max ; BEAM ... AND LC min ; BEAM ...`). Labels only where |value| > the threshold in the table (the largest local extremes; small values near zero are suppressed). Result text height 0.375 cm on the sheet = 2.6 mm when printed 170 mm wide (checked on the PNG). Lines thickened from 1 to 3 px after export. The scale "1 cm = x" is on the WinGRAF sheet; the PNG is 22.5 cm wide, so at 170 mm print 1 sheet-cm = 7.6 mm. Units in each legend line and in the PDF caption.

Views: ISO = `VIEW DIRE X 1 Y 1.4 Z -2.6` (steep isometric), 3D = `X 1 Y 1.4 Z -0.8` (as W1/W4), PLAN = `X 0 Y 0 Z -1 AXIS NEGY` (true top view, X right, Y up), EXT = `X -1 Y 0.35 Z -0.45` (external stair from outside, as W8).

**Plan or isometric for floor My:** I tried both for Level 1 (and Level 2). My and Vz act in the vertical plane; in a true top view they have to be rotated into the plan (`DTYP PP`), and then the diagram flips side with each member's direction, so a sagging and a hogging moment look the same. The isometric keeps the diagrams vertical and reads correctly, so all floor My, Vz, N pictures use ISO. Mz acts about the vertical axis and is drawn in true PLAN.

| file | view | groups | quantity | scale 1 cm = | labels above | envelope max / min (largest labelled values) |
|---|---|---|---|---|---|---|
| P00_key_beam_groups.png | 3D | all beam groups, coloured, legend at top | group no. | - | - | - |
| P01_L1_My.png | ISO | 15 | My kNm | 50 | 37 | 43.35 / -81.45 |
| P02_L1_Vz.png | ISO | 15 | Vz kN | 50 | 35 | 76.97 / -76.70 |
| P03_L1_N.png | ISO | 15 | N kN | 200 | 66 | 109.33 / -71.62 |
| P04_L2_My.png | ISO | 25 | My kNm | 200 | 127 | 233.68 / -363.75 |
| P05_L2_Vz.png | ISO | 25 | Vz kN | 100 | 66 | 146.23 / -109.44 |
| P06_L2_N.png | ISO | 25 | N kN | 100 | 37 | 62.26 / -55.38 |
| P07_RF_My.png | ISO | 35 | My kNm | 50 | 33 | 73.98 / -60.84 |
| P08_RF_Vz.png | ISO | 35 | Vz kN | 20 | 14 | 30.99 / -31.30 |
| P09_RF_N.png | ISO | 35 | N kN | 100 | 44 | 72.75 / -67.43 |
| P10_L1_Mz_plan.png | PLAN | 15 | Mz kNm | 5 | 3.1 | 10.07 / -10.41 |
| P11_L1_ring85_Mz_plan.png | PLAN | 15, r 8.5 ring only (18 SLN, SEL by element) | Mz kNm | 1 | 0.6 | 1.87 / -1.83 |
| P12_V_G-L1_N.png | 3D | 11,12,13,14 (ground-L1 members) | N kN | 200 | 239 | 56.84 / -398.98 |
| P13_V_G-L1_My.png | 3D | same | My kNm | 10 | 3.2 | 7.08 / -7.08 |
| P14_V_G-L1_Mz.png | 3D | same | Mz kNm | 10 | 4.9 | 8.20 / -10.93 |
| P15_V_L1-L2_N.png | 3D | 13 (upper), 21, 23, 24 | N kN | 200 | 158 | 59.71 / -264.01 |
| P16_V_L1-L2_My.png | 3D | same | My kNm | 10 | 10 | 21.91 / -22.58 |
| P17_V_L1-L2_Mz.png | 3D | same | Mz kNm | 10 | 7.2 | 10.91 / -15.96 |
| P18_V_L2-RF_N.png | 3D | 31 | N kN | 200 | 40 | 66.78 / -60.00 |
| P19_V_L2-RF_My.png | 3D | 31 | My kNm | 10 | 11 | 21.21 / -23.63 |
| P20_V_L2-RF_Mz.png | 3D | 31 | Mz kNm | 10 | 9 | 20.05 / -14.96 |
| P21_S_int_N.png | 3D | 60, 61 | N kN | 50 | 49 | 57.75 / -51.58 |
| P22_S_int_My.png | 3D | 60, 61 | My kNm | 20 | 10 | 16.69 / -22.58 |
| P23_S_int_Vz.png | 3D | 60, 61 | Vz kN | 20 | 17 | 37.47 / -28.53 |
| P24_S_ext_N.png | EXT | 62 | N kN | 100 | 55 | 64.98 / -62.71 |
| P25_S_ext_My.png | EXT | 62 | My kNm | 20 | 11 | 20.93 / -24.77 |
| P26_S_ext_Vz.png | EXT | 62 | Vz kN | 20 | 13 | 27.85 / -15.62 |

Scales: one scale per quantity within each set (the three column storeys share N 200 kN/cm, My and Mz 10 kNm/cm; each floor level has its own scale because L2 My is 4.5 times L1 My). Columns were split into three storey pictures (the single 3D picture was unreadable); each storey's scale and label threshold come from that storey's own envelope (`scripts/storey_ext.json`).

Not drawn: (f) kingpost / central mast - it is shell (QUAD) elements, not a beam group, so there is no beam N / My diagram. Groups 1, 2, 6, 7 are the shell groups.

## 4. Table

`env_table_ULS.csv` / `.json` (and `env_table_SLS.*`): one row per beam group: group, description, sections (from the SLN input), number of beam elements and analysis lines, then for N, Vy, Vz, Mt, My, Mz the envelope max and min, each with the beam element, its analysis line (SLN), x [m from beam start], the governing combination (found by scanning the 43 combinations, MAXIMA does not store it) and the value read back from the MAXIMA load case at the same station (equal in every row).

## 5. Things that look odd (for Wing to judge)

- **Group 15 Vy +/-50.1 kN** (weak-axis shear) on a 0.25 m radial stub, beam 100841, r 11.75-12.0 m at 20 deg, LC 122. It sits next to the radial SLN 184 that carries Mz 10.07 kNm (RESULTS_v19m). Same pattern at L2: Vy 27.2 kN on stub beam 140775, r 11.4-12.0 at 260 deg, LC 119. Probably the V-raker apex / connection offset at the r 12 ring; worth a look at those nodes.
- **Group 61 landing posts**: My, Mz, Vz all 0.0 (pinned posts, axial only) - as modelled.
- **Group 14 columns**: N max is -7.9 kN, i.e. always in compression; group 14 holds the largest compression -399.0 kN (LC 135).
- WinGRAF draws the member lines in the dark base-line colour of the result layers; I could not get them light grey with `COLO C12`/`DSGN GFRB`. They are thin and do not hide the diagrams.
- WinGRAF warning 873 (diagram direction parallel to the view) on some plan / storey sheets: members that run along the view direction show no diagram there; their values are in the table.

## 6. Input files

- `maxima_comb3_excerpt.dat` - the MAXIMA input that built the envelope LCs (from the model run, read only).
- `26016_env_wing.dat` - the WinGRAF + PLBCONVERTER batch input for all 27 pictures (generated by `scripts/make_wing.py`).
- `scripts/harvest_env.py` (table + sanity check), `scripts/storey_ext.py` (storey extremes), `scripts/make_wing.py`, `scripts/finalize.py` (thicken lines, names, PDF), `scripts/ring85_ranges.json`, `scripts/storey_ranges.json` (element ranges for SEL).
- Run order: `py -3.11 harvest_env.py`, `py -3.11 storey_ext.py`, `py -3.11 make_wing.py`, `sps.exe -B0 26016_env_wing.dat`, `py -3.11 finalize.py`.
