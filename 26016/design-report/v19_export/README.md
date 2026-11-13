# 26016 v19 export for the design report (external stairs)

Source: `C:\Sofistik workflow\26016-member-check\v19\` (run 12 Nov 2026 on NguyenPC, exit 0, 0 errors, 278 warnings).
Read only. No SOFiSTiK calculation was started on the v19 database. The WinGRAF pictures were made from a copy
(`26016-member-check\v19_wing\26016_v19_copy.cdb`).

Note: the v15 extract scripts and the v15 `out` folder were not on this PC, and they are not in the GitHub repo.
So the JSON layouts below are new. Each file has the same name as the v15 file, and its `what`, `notes` and `sign` fields describe its content.

## Files
| File | Content |
|---|---|
| v19_text.zip | 26016_check_v19.erg, .lst, .prt and RESULTS_v19.md (the originals stay in the v19 folder) |
| reactions_basic_sums.json | sum Fx, Fy, Fz of all 69 supports for LC 1-4, 11-14, 71-74, with the sum SOFiSTiK stored (they match) |
| reactions_EQU.json | px, py, pz at every support node (column bases 2-34, SPT 1001/1002, stair bases 901-916, kingpost base line 5807-5824) for EQU 131-134, with sums and uplift nodes |
| env_support_ULS.json | min / max px, py, pz (and moments where they are not zero) with the governing LC per support node, ULS 101-154 (EQU 131-134 included, as BDK/AQB; `str_only_load_cases` lists the cases without EQU) |
| env_support_SLS.json | the same for SLS 201-221 |
| env_node_SLS_L1/L2/RF.json | SLS 201-221 envelope of ux, uy, uz, horizontal resultant per node, for every node of the framing beams of group 15 (L1, z 4.05), 25 (L2, z 8.05) and 35 (roof, z 12.06), with a summary block |
| stair_ext.json | external stair, group 62: per SLN the section, BDK and AQB with the governing LC; N, My, Mz of the governing members; base reactions LC 102 / 201 / ULS envelope; ring brackets 724/725/769/770; flight and landing deflections; landing 1 and landing 2 horizontal movement |
| ring_L2.json | L2 outer ring r 12, SLN 55-72: BDK and AQB per SLN; for the three highest: N, Vz, My, Mz at the node, My at 300 mm and the other end |
| summary_v19.json | maximum BDK and AQB per group, every member above 0.90, lowest buckling factors |
| W1-W4, W8 *.png | WinGRAF pictures, same views and style as v15 W1-W4, plus W8 (close view of the external stair) |
| R1_external_stair_reading.png | plan of the stair drawn from the model geometry, showing how the results were read |
| wingraf_recipe_v19.dat | the WinGRAF + PLBCONVERTER batch used for the pictures |
| scripts/ | extract_v19.py (cdb reads), erg.py (BDK / AQB tables from the .erg), draw_reading.py, cdbx.py |

## Reading rules (check these)
- Support sign: SOFiSTiK support force on the structure. pz > 0 = bearing, pz < 0 = uplift.
- BDK utilisation = max(nm-y, nm-z) from the BDK "Summary of the Results" (2 BDK programs, the higher value is kept per member ID; ID = SLN).
- AQB utilisation = the "Tot-int" value of each station's max row, or the elastic von Mises ratio where no plastic line is printed (class 3 stations, 5 mm treads). The maxima reproduce the AQB "Maximum Utilisation Level" Total of every section (1.075, 0.699, 0.242, ...).
- Group 62 legs and stringers were split by SOFiMSHC (SLN 16xx/17xx). They are mapped back to the input SLN by geometry.
- The ring brackets pass N only. `force_on_ring_global` = N times the unit vector from the ring to the landing. `reaction_on_landing_global` is the opposite force.
- Ring L2: "node end" = the end with the larger |My| in the BDK governing LC. My at 300 mm uses a Hermite interpolation with dMy/dx = Vz (a linear value is also given).
