# 26016 v19m export (L1 r 8.5 ring ends pinned about both axes at the A/B joints)

Source: `C:\Sofistik workflow\26016-member-check\v19m\26016_check_v19m.dat` = v19 + MZ release (FIXA/FIXE 'MY' -> 'MYMZ')
at the 18 Level 1 ring ends (group 15, r 8.5 m) that frame into the radial web at the 9 A/B joints (0, 40, ... 320 deg).
Wing, 13 Nov 2026: the added top and bottom flange plates are removed, so the web-only ring end plate (4 M20) is pinned about the weak axis.
Run 13 Nov 2026 on NguyenPC: exit 0, 0 errors, 284 warnings (v19: 278; the 6 extra are BDK no. 205 "member in tension" on ID 445, LC 125).
The v19 folder and the v19 export were not changed. All reads were read-only; the WinGRAF pictures come from a copy
(`26016-member-check\v19m_wing\26016_v19m_copy.cdb`).

Same layout and the same scripts as `v19_export` (paths moved to v19m), so the cloud scripts read both the same way.
Files that carry the model name have `v19m` in place of `v19` (`summary_v19m.json`, `v19m_text.zip`, `PART_A_v19m.md`, `wingraf_recipe_v19m.dat`).

## Files

| File | Content |
|---|---|
| RESULTS_v19m.md | v19 vs v19m: run checks, alpha_cr, reactions, max BDK / AQB per group, L1 r 8.5 rings and L1 radials in detail (My, Mz, BDK, AQB, SLS), ring-end Mz per joint, L2 ring SLN 56/57/62, flags |
| compare_v19_v19m.csv | every BDK id and every AQB beam, v19 and v19m utilisation, change, governing LC |
| flags_v19m.json | entries worse / better by more than 0.02 (none) |
| l1_detail_v19m.json, compare_v19/l1_detail_v19.json | group 15 per input SLN: BDK, AQB, max My / Mz / N with LC, SLS relative deflection; Mz at each ring end at r 8.5 |
| v19m_released_ends_plan.png | Level 1 plan from the model geometry, the 18 released ring ends marked with SLN and end |
| 26016_check_v19m.dat | the model run (only the 18 FIXA/FIXE literals and 2 header comment lines differ from v19) |
| summary_v19m.json, ring_L2.json, stair_ext.json, reactions_*.json, env_*.json | same content and layout as in v19_export |
| A_followup/partA1-3.json, PART_A_v19m.md, A_followup_reading.png | Part A follow-up numbers, v19 value beside each v19m value |
| W1-W4, W8 *.png | WinGRAF pictures, same views as v19 |
| W5_buckling_PLC119_mode1_L1.png | new: lowest PLC 119 mode in v19m (L1 inner radials, see RESULTS) |
| R1_external_stair_reading.png | external stair plan, as in v19 |
| v19m_text.zip | 26016_check_v19m.erg, .lst, .prt and RESULTS_v19m.md |
| idea_L1_noflange/ | IDEA CBFEM of the 9 L1-R8 A/B joints without flange plates, v19m forces: summary csv, results md, screenshots |
| scripts/ | extract_v19m.py, erg.py, l1_detail.py, make_results.py, run_export_v19m.sh, ... |

## Reading rules
As in v19_export (support sign, BDK = max(nm-y, nm-z), AQB = Tot-int or elastic von Mises, group 62 split SLNs mapped back by geometry).
Ring-end Mz is in the ring's local axes (weak axis of the UB, about the vertical).
