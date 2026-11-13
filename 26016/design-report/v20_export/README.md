# 26016 v20 export (qp 0.5 kPa, external stair stringer ends pinned for My)

Source: `C:\Sofistik workflow\26016-member-check\v20\26016_check_v20.dat` = v19m + (1) qp = 0.500 kPa for every wind load (STO#Q; v19m 0.766 kPa),
(2) external stair (group 62): My released at 12 stringer ends (both ends of flight 2: SLN 713, 714, 758, 759; landing end of flight 1: SLN 701, 702, 746, 747).
The flight-1 feet stay on their pinned supports SPT 901/902/909/910 without an extra hinge (with 16 hinges, run 1 stopped in the PLC 102 eigen ASE: free node rotation at the feet).
Wing, 13 Nov 2026. Run 2 on 13 Nov 2026, NguyenPC: exit 0, 0 errors, 212 warnings (no new warning type vs v19m), 34 min.
The v19m folder and the v19m export were not changed. WinGRAF pictures from a copy (`26016-member-check\v20_wing\26016_v20_copy.cdb`).

Same layout and the same scripts as `v19m_export` (paths moved to v20; `v19m` in place of `v19` as the comparison), so the report script reads it the same way.
Files that carry the model name have `v20` in place of `v19m` (`summary_v20.json`, `v20_text.zip`, `PART_A_v20.md`, `wingraf_recipe_v20.dat`, `compare_v19m_v20.csv`).

Extra in v20: `sliding_overturning_v20.json` (sliding and overturning from the real v20 reactions, also in RESULTS_v20.md),
`v20_stair_release_reading.png` (the released stringer ends), `scripts/results_extra_v20.py`, `scripts/run_checks.json`.

Reading rules as in v19m_export.
