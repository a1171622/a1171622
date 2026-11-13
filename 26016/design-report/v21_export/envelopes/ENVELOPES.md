# 26016 v21 - ULS member force envelopes (WinGRAF pictures + table)

Model: `26016-member-check\v21\26016_check_v21` = v20 + drawing 970027-S01-ST sections (stair RHS 160x80x5, L2 radials UB 457x191x98, landing supports SHS 80x80x6.3) (run 13 Nov 2026, exit 0, 0 errors).
Read from a COPY (`v21\envelopes\26016_env_v21.cdb`); nothing re-analysed. Same recipe, views, scales logic and file names as the v20 envelopes.
Standalone PDF: `26016_v21_ULS_envelopes.pdf` (A4, cover, 2 table pages, one picture per page with a caption).

## Load cases

Model MAXIMA COMB 3 (EXTR NONL, TYPE DESI, BASE 4300): the 43 ULS STR combinations 101-130, 135, 141-148, 151-154 as exclusive alternatives (TYPE AG1, factor 1.00). Beam envelope LCs: N 4321/4322, Vy 4323/4324, Vz 4325/4326, Mt 4327/4328, My 4329/4330, Mz 4331/4332 (max/min); SLS 201-221: 4421-4432. EQU 131-134 not included.

## Sanity check (MAXIMA vs scan of the 43 combinations)

Largest difference at any station of any beam: N 0.0e+00, Vy 4.4e-07, Vz 7.3e-06, Mt 8.5e-06, My 4.0e-09, Mz 5.3e-09 (kN / kNm). They match.

| member | My max (LC) | My min (LC) | N max (LC) | N min (LC) | MAXIMA |
|---|---|---|---|---|---|
| SLN 56 (named in the brief: group 25, L2 outer ring r 12) | 135.969 (121) | -164.267 (153) | 37.116 (123) | -9.523 (108) | identical |
| SLN 227 (L1 ring r 8.5, 340-360 deg, group 15) | 22.492 (102) | -0.000 (107) | 22.239 (124) | -5.979 (109) | identical |
| column SLN 37 | 3.719 (118) | -1.358 (112) | 9.693 (107) | -145.203 (120) | identical |
| internal stair upper-flight stringer, z 6.28-8.05 m, y about -9.4 (analysis lines 1454-1463, group 60) | 4.938 (151) | -7.410 (152) | 39.871 (152) | -1.954 (110) | identical |

## Pictures (`png/`, 300 dpi; print 170 mm wide, result text about 2.6 mm)

Red = max envelope LC, blue = min envelope LC. Floor My/Vz/N in a steep isometric (My acts in the vertical plane; a true top view had to rotate the diagram into the plan and flips side with member direction), Mz of Level 1 in true plan. Columns per storey (SEL by element). Scale = 1 cm on the 25.5 cm WinGRAF sheet.

| file | groups | quantity | scale 1 cm = | labels above | envelope max / min |
|---|---|---|---|---|---|
| P00_key_beam_groups.png | all beam groups | key | - | - | - |
| P01_L1_My.png | 15 | MY kNm | 50 | 40 | 48.6 / -89.11 |
| P02_L1_Vz.png | 15 | VZ kN | 50 | 36 | 79.83 / -79.63 |
| P03_L1_N.png | 15 | N kN | 200 | 65 | 108.83 / -57.77 |
| P04_L2_My.png | 25 | MY kNm | 200 | 131 | 237.68 / -374.44 |
| P05_L2_Vz.png | 25 | VZ kN | 100 | 67 | 149.68 / -111.1 |
| P06_L2_N.png | 25 | N kN | 100 | 38 | 62.7 / -33.33 |
| P07_RF_My.png | 35 | MY kNm | 20 | 20 | 44.67 / -41.13 |
| P08_RF_Vz.png | 35 | VZ kN | 10 | 8.7 | 19.08 / -19.29 |
| P09_RF_N.png | 35 | N kN | 100 | 33 | 55.58 / -54.11 |
| P10_L1_Mz_plan.png | 15 | MZ kNm | 5 | 2.9 | 9.61 / -9.75 |
| P11_L1_ring85_Mz_plan.png | 15 | MZ kNm | 1 | 0.6 | 2.13 / -2.08 |
| P12_V_G-L1_N.png | 11, 12, 13, 14, 21, 23, 24, 31 | N kN | 200 | 242 | 37.4 / -403.71 |
| P13_V_G-L1_My.png | 11, 12, 13, 14, 21, 23, 24, 31 | MY kNm | 10 | 2.7 | 4.84 / -6.04 |
| P14_V_G-L1_Mz.png | 11, 12, 13, 14, 21, 23, 24, 31 | MZ kNm | 10 | 5.7 | 8.44 / -12.63 |
| P15_V_L1-L2_N.png | 11, 12, 13, 14, 21, 23, 24, 31 | N kN | 200 | 161 | 29.45 / -268.76 |
| P16_V_L1-L2_My.png | 11, 12, 13, 14, 21, 23, 24, 31 | MY kNm | 10 | 10 | 20.53 / -22.7 |
| P17_V_L1-L2_Mz.png | 11, 12, 13, 14, 21, 23, 24, 31 | MZ kNm | 10 | 6.6 | 10.51 / -14.67 |
| P18_V_L2-RF_N.png | 11, 12, 13, 14, 21, 23, 24, 31 | N kN | 200 | 36 | 45.7 / -60.05 |
| P19_V_L2-RF_My.png | 11, 12, 13, 14, 21, 23, 24, 31 | MY kNm | 10 | 11 | 21 / -23.75 |
| P20_V_L2-RF_Mz.png | 11, 12, 13, 14, 21, 23, 24, 31 | MZ kNm | 10 | 8.1 | 17.9 / -14.48 |
| P21_S_int_N.png | 60, 61 | N kN | 50 | 50 | 59.18 / -50.75 |
| P22_S_int_My.png | 60, 61 | MY kNm | 20 | 12 | 15.42 / -26.23 |
| P23_S_int_Vz.png | 60, 61 | VZ kN | 20 | 16 | 36.04 / -28.88 |
| P24_S_ext_N.png | 62 | N kN | 50 | 46 | 48.5 / -54.34 |
| P25_S_ext_My.png | 62 | MY kNm | 5 | 4 | 8.93 / -7.58 |
| P26_S_ext_Vz.png | 62 | VZ kN | 10 | 6.8 | 12.54 / -15.12 |

## Group extremes v20 -> v21 (My and N, kNm / kN)

| group | My max | My min | N max | N min |
|---|---|---|---|---|
| 11 | 4.15 -> 4.84 | -5.79 -> -6.04 | 18.46 -> 18.18 | -290.58 -> -290.66 |
| 12 | 1.8 -> 1.8 | -0.0 -> -0.0 | 37.71 -> 37.4 | -76.52 -> -75.55 |
| 13 | 4.62 -> 4.62 | -4.63 -> -4.63 | 10.62 -> 10.66 | -264.77 -> -263.71 |
| 14 | 0.73 -> 0.74 | -1.05 -> -1.11 | -20.72 -> -21.25 | -398.77 -> -403.71 |
| 15 | 45.19 -> 48.6 | -85.67 -> -89.11 | 109.19 -> 108.83 | -57.9 -> -57.77 |
| 21 | 20.94 -> 20.53 | -22.34 -> -22.7 | 29.6 -> 29.45 | -229.63 -> -228.44 |
| 23 | 2.21 -> 2.2 | -1.66 -> -1.64 | -6.26 -> -6.53 | -146.11 -> -145.03 |
| 24 | 3.9 -> 3.92 | -4.07 -> -4.05 | -5.26 -> -5.79 | -263.75 -> -268.76 |
| 25 | 233.65 -> 237.68 | -363.8 -> -374.44 | 62.45 -> 62.7 | -33.18 -> -33.33 |
| 31 | 21.15 -> 21.0 | -23.68 -> -23.75 | 45.29 -> 45.7 | -59.9 -> -60.05 |
| 35 | 44.67 -> 44.67 | -41.12 -> -41.13 | 54.53 -> 55.58 | -53.4 -> -54.11 |
| 60 | 16.8 -> 15.42 | -22.38 -> -26.23 | 67.49 -> 59.18 | -24.07 -> -24.46 |
| 61 | 0.0 -> 0.0 | -0.0 -> -0.0 | 0.34 -> 0.73 | -50.94 -> -50.75 |
| 62 | 9.55 -> 8.93 | -10.41 -> -7.58 | 49.23 -> 48.5 | -54.52 -> -54.34 |

Kingpost: shell elements, no beam diagram. Table with Vy, Vz, Mt, Mz and governing beam / x / LC: env_table_ULS.csv / .json (SLS: env_table_SLS.*).

Inputs: `26016_env_wing.dat` (WinGRAF + PLBCONVERTER, from scripts/make_wing.py), scripts/harvest_env.py, storey_ext.py, finalize.py, make_md.py; envelope LCs from the model run (maxima_comb3_excerpt.dat in the v20 envelopes, unchanged).
