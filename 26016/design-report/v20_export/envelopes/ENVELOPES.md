# 26016 v20 - ULS member force envelopes (WinGRAF pictures + table)

Model: `26016-member-check\v20\26016_check_v20` = v19m + qp 0.500 kPa for all wind + My hinges at 12 external stair stringer ends (run 13 Nov 2026, exit 0, 0 errors).
Read from a COPY (`v20\envelopes\26016_env_v20.cdb`); nothing re-analysed. Same recipe, views, scales logic and file names as the v19m envelopes.
Standalone PDF: `26016_v20_ULS_envelopes.pdf` (A4, cover, 2 table pages, one picture per page with a caption).

## Load cases

Model MAXIMA COMB 3 (EXTR NONL, TYPE DESI, BASE 4300): the 43 ULS STR combinations 101-130, 135, 141-148, 151-154 as exclusive alternatives (TYPE AG1, factor 1.00). Beam envelope LCs: N 4321/4322, Vy 4323/4324, Vz 4325/4326, Mt 4327/4328, My 4329/4330, Mz 4331/4332 (max/min); SLS 201-221: 4421-4432. EQU 131-134 not included.

## Sanity check (MAXIMA vs scan of the 43 combinations)

Largest difference at any station of any beam: N 0.0e+00, Vy 2.1e-07, Vz 7.3e-06, Mt 1.0e-05, My 1.8e-09, Mz 4.2e-09 (kN / kNm). They match.

| member | My max (LC) | My min (LC) | N max (LC) | N min (LC) | MAXIMA |
|---|---|---|---|---|---|
| SLN 56 (named in the brief: group 25, L2 outer ring r 12) | 136.867 (121) | -163.760 (153) | 38.594 (123) | -9.365 (108) | identical |
| SLN 227 (L1 ring r 8.5, 340-360 deg, group 15) | 22.492 (102) | -0.000 (107) | 22.175 (124) | -6.102 (109) | identical |
| column SLN 37 | 3.719 (118) | -1.358 (112) | 9.682 (107) | -145.815 (120) | identical |
| internal stair upper-flight stringer, z 6.28-8.05 m, y about -9.4 (analysis lines 1454-1463, group 60) | 6.018 (151) | -5.783 (152) | 42.249 (152) | -0.401 (110) | identical |

## Pictures (`png/`, 300 dpi; print 170 mm wide, result text about 2.6 mm)

Red = max envelope LC, blue = min envelope LC. Floor My/Vz/N in a steep isometric (My acts in the vertical plane; a true top view had to rotate the diagram into the plan and flips side with member direction), Mz of Level 1 in true plan. Columns per storey (SEL by element). Scale = 1 cm on the 25.5 cm WinGRAF sheet.

| file | groups | quantity | scale 1 cm = | labels above | envelope max / min |
|---|---|---|---|---|---|
| P00_key_beam_groups.png | all beam groups | key | - | - | - |
| P01_L1_My.png | 15 | MY kNm | 50 | 39 | 45.19 / -85.67 |
| P02_L1_Vz.png | 15 | VZ kN | 50 | 34 | 76.35 / -75.97 |
| P03_L1_N.png | 15 | N kN | 200 | 66 | 109.19 / -57.9 |
| P04_L2_My.png | 25 | MY kNm | 200 | 127 | 233.65 / -363.8 |
| P05_L2_Vz.png | 25 | VZ kN | 100 | 66 | 145.99 / -109.44 |
| P06_L2_N.png | 25 | N kN | 100 | 37 | 62.45 / -33.18 |
| P07_RF_My.png | 35 | MY kNm | 20 | 20 | 44.67 / -41.12 |
| P08_RF_Vz.png | 35 | VZ kN | 10 | 8.7 | 19.08 / -19.28 |
| P09_RF_N.png | 35 | N kN | 100 | 33 | 54.53 / -53.4 |
| P10_L1_Mz_plan.png | 15 | MZ kNm | 5 | 3.5 | 11.22 / -11.64 |
| P11_L1_ring85_Mz_plan.png | 15 | MZ kNm | 1 | 0.6 | 2.07 / -2.03 |
| P12_V_G-L1_N.png | 11, 12, 13, 14, 21, 23, 24, 31 | N kN | 200 | 239 | 37.71 / -398.77 |
| P13_V_G-L1_My.png | 11, 12, 13, 14, 21, 23, 24, 31 | MY kNm | 10 | 2.6 | 4.62 / -5.79 |
| P14_V_G-L1_Mz.png | 11, 12, 13, 14, 21, 23, 24, 31 | MZ kNm | 10 | 5.5 | 8.35 / -12.24 |
| P15_V_L1-L2_N.png | 11, 12, 13, 14, 21, 23, 24, 31 | N kN | 200 | 158 | 29.6 / -263.75 |
| P16_V_L1-L2_My.png | 11, 12, 13, 14, 21, 23, 24, 31 | MY kNm | 10 | 10 | 20.94 / -22.34 |
| P17_V_L1-L2_Mz.png | 11, 12, 13, 14, 21, 23, 24, 31 | MZ kNm | 10 | 7.1 | 10.64 / -15.86 |
| P18_V_L2-RF_N.png | 11, 12, 13, 14, 21, 23, 24, 31 | N kN | 200 | 36 | 45.29 / -59.9 |
| P19_V_L2-RF_My.png | 11, 12, 13, 14, 21, 23, 24, 31 | MY kNm | 10 | 11 | 21.15 / -23.68 |
| P20_V_L2-RF_Mz.png | 11, 12, 13, 14, 21, 23, 24, 31 | MZ kNm | 10 | 8.6 | 19.03 / -14.96 |
| P21_S_int_N.png | 60, 61 | N kN | 100 | 57 | 67.49 / -50.94 |
| P22_S_int_My.png | 60, 61 | MY kNm | 20 | 10 | 16.8 / -22.38 |
| P23_S_int_Vz.png | 60, 61 | VZ kN | 20 | 17 | 38.25 / -32.46 |
| P24_S_ext_N.png | 62 | N kN | 50 | 46 | 49.23 / -54.52 |
| P25_S_ext_My.png | 62 | MY kNm | 10 | 4.7 | 9.55 / -10.41 |
| P26_S_ext_Vz.png | 62 | VZ kN | 10 | 6.7 | 13.83 / -14.88 |

## Group extremes v19m -> v20 (My and N, kNm / kN)

| group | My max | My min | N max | N min |
|---|---|---|---|---|
| 11 | 3.1 -> 4.15 | -4.71 -> -5.79 | 55.71 -> 18.46 | -294.02 -> -290.58 |
| 12 | 2.03 -> 1.8 | -0.0 -> -0.0 | 56.84 -> 37.71 | -84.07 -> -76.52 |
| 13 | 7.08 -> 4.62 | -7.08 -> -4.63 | 26.53 -> 10.62 | -267.77 -> -264.77 |
| 14 | 1.04 -> 0.73 | -1.29 -> -1.05 | -7.86 -> -20.72 | -398.98 -> -398.77 |
| 15 | 43.35 -> 45.19 | -81.45 -> -85.67 | 109.33 -> 109.19 | -71.62 -> -57.9 |
| 21 | 21.91 -> 20.94 | -22.58 -> -22.34 | 59.71 -> 29.6 | -228.0 -> -229.63 |
| 23 | 3.38 -> 2.21 | -2.46 -> -1.66 | -3.4 -> -6.26 | -144.73 -> -146.11 |
| 24 | 6.03 -> 3.9 | -6.03 -> -4.07 | 1.75 -> -5.26 | -264.01 -> -263.75 |
| 25 | 233.68 -> 233.65 | -363.75 -> -363.8 | 62.26 -> 62.45 | -55.38 -> -33.18 |
| 31 | 21.21 -> 21.15 | -23.63 -> -23.68 | 66.78 -> 45.29 | -60.0 -> -59.9 |
| 35 | 73.98 -> 44.67 | -60.84 -> -41.12 | 72.75 -> 54.53 | -67.43 -> -53.4 |
| 60 | 16.69 -> 16.8 | -22.58 -> -22.38 | 57.75 -> 67.49 | -22.11 -> -24.07 |
| 61 | 0.0 -> 0.0 | -0.0 -> -0.0 | 3.8 -> 0.34 | -51.58 -> -50.94 |
| 62 | 20.93 -> 9.55 | -24.77 -> -10.41 | 64.98 -> 49.23 | -62.71 -> -54.52 |

Kingpost: shell elements, no beam diagram. Table with Vy, Vz, Mt, Mz and governing beam / x / LC: env_table_ULS.csv / .json (SLS: env_table_SLS.*).

Inputs: `26016_env_wing.dat` (WinGRAF + PLBCONVERTER, from scripts/make_wing.py), scripts/harvest_env.py, storey_ext.py, finalize.py, make_md.py; envelope LCs from the model run (maxima_comb3_excerpt.dat in the v19m envelopes, unchanged).
