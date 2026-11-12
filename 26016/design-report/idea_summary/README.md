# 26016 IDEA StatiCa results and model screenshots (collected 2026-11-12 on NguyenPC)

Read-only copy from `C:\Sofistik workflow\idea-statica\` on NguyenPC. No IDEA or SOFiSTiK run was
started and no source file was changed. Only csv / md / png were copied (no .ideaCon, .xml, .svg, .pdf).
Dates are file modified times on NguyenPC (local time). All forces are SOFiSTiK **v15** (SAF export
27 Oct 2026) unless noted; "as-is" = member-end Mz as the model gives it.

## Current design set (what `R8_current_design_asis.csv` reports, 36 joints at r 8.5 m)

| Joints | Detail | IDEA run folder (on PC) |
|---|---|---|
| L1-R8-A (7) | end-plate flanges 12 mm | `v15\xml_A_flanges_asis\` |
| L1-R8-B (2) | end-plate flanges, column welds a 5.6 | `v15\xml_B_flanges_asis\` |
| L1-R8-S (7) + T (2) | A-type strut, true 10° ring, double fin 2x12, 4 M20 | `v15\xml_strut_10deg_asis\` |
| L2-R8-A (14) + B (4) | r12 haunch, ring bottom flush (M20) | `v15\xml_L2haunch_flush_asis\` |

A later variant of the L2 set with M24 bolts (`v15\xml_L2haunch_flush_M24_asis\`, 4 Nov) also exists;
`R8_current_design_asis.csv` (3 Nov) still shows the M20 run.

## Files

| File in this folder | Source path (under `C:\Sofistik workflow\idea-statica\`) | Modified | Joint set / force version |
|---|---|---|---|
| `results/R8_current_design_asis.csv` | `v15/R8_current_design_asis.csv` | 2026-11-03 10:54 | CURRENT design table, 36 R8 joints, v15 as-is |
| `results/L1_R8_strut_10deg_summary.csv` | `v15/xml_strut_10deg_asis/joint_check_summary.csv` | 2026-11-03 10:53 | L1-R8-S/T strut set (9), true 10° ring, v15 as-is; current |
| `results/L2_R8_haunch_flush_M20_summary.csv` | `v15/xml_L2haunch_flush_asis/joint_check_summary.csv` | 2026-11-03 10:28 | L2-R8-A/B haunch flush (18), M20, v15 as-is; current |
| `results/L2_R8_haunch_flush_M24_summary.csv` | `v15/xml_L2haunch_flush_M24_asis/joint_check_summary.csv` | 2026-11-04 12:50 | L2-R8-A/B haunch flush (18), M24 variant, v15 as-is; newest L2 run |
| `results/L2_R8_haunch_flush_M24_bolt_tension.csv` | `v15/xml_L2haunch_flush_M24_asis/bolt_tension_M24.csv` | 2026-11-04 13:14 | L2 M24 variant: max bolt tension per joint (hand extract) |
| `results/L2_R8_haunch_not_flush_summary_superseded.csv` | `v15/xml_L2haunch_asis/joint_check_summary.csv` | 2026-11-03 10:08 | L2 haunch, not flush (18); superseded by flush |
| `results/R8_final_summary_2026-10-28_superseded.csv` | `v15/R8_final_summary.csv` | 2026-10-28 13:59 | previous 36-joint table (as-is + Mz0), old strut / old L2 flush; superseded |
| `results/RESULTS_v15_2026-10-30.md` | `26016_all/v15/RESULTS_v15.md` | 2026-10-30 11:57 | first v15 write-up (27 Oct runs); superseded, history only |
| `results/L2_R12_E1_v14_summary.csv` | `v14/xml_E1/joint_check_summary.csv` | 2026-10-20 15:34 | L2-R12-E1_000 only, **v14 forces** (20 Oct), FAIL welds 100.6 %; not rerun on v15 |
| `screens_R8_final_v2/<joint>_top.png`, `_under.png` (72) | `v15/figures/idea_screens/final_v2/` | 2026-11-03 10:44 | IDEA model views (from above / below), all 36 current R8 joints |
| `screens_L2haunch_R12/*.png` (18) | `v15/figures/idea_screens/L2haunch/` | 2026-11-03 10:00 to 2026-11-04 12:52 | L2-R12-E1_000 source connection (haunch donor), L2-R8 A_040/B_060/B_260 haunch vs haunch_flush, B_080 haunch_flush_M24 |

## Screenshot folders found on the PC

| Folder | Date | Files | Content |
|---|---|---|---|
| `v15\figures\idea_screens\final_v2\` | 2026-11-03 10:44 | 144 (72 png + 72 svg) | complete: 36 joints x top/under. Newest complete set |
| `v15\figures\idea_screens\L2haunch\` | 2026-11-03 / 11-04 | 36 (18 png + 18 svg) | partial: comparison views for 5 joints + R12 source |
| `v15\figures\S_300_img\` | 2026-10-27 | 26 png | IDEA report images of L1-R8-S_300 with the OLD strut detail; not copied |

## Not found / not copied

- No IDEA results on v15 forces for the r 12 m joints (L2-R12-E1): only the v14 run of E1_000 (FAIL),
  v14 models for E1_040...E1_320 exist without a result row. `v15\xml_L2haunch_asis\r12_source_connection_data.json`
  holds the R12 connection data used as the haunch donor (json, not copied).
- No IDEA models or results for stairs or a kingpost anywhere under `C:\Sofistik workflow\`.
- `v15\xml_L2flush_fixed_asis\` has only partA results (incomplete run); not copied.

## Overview sheets

`26016_IDEA_L1_overview.png` and `26016_IDEA_L2_overview.png`: every current joint (top view) with plate strain / bolts / welds % and PASS/FAIL from `R8_current_design_asis.csv`; the L2 sheet adds L2-R12-E1_000 (v14, FAIL). Made 2026-11-13 from the files in this folder.
