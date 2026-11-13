# 26016 v21 export (model updated to drawings 970027-S01-ST, issue 13.11.2026)

Source: `C:\Sofistik workflow\26016-member-check\v21\26016_check_v21.dat` = v20 + three section changes from the drawings (Wing, 13 Nov 2026):
(1) new SECT 10 RHS 160x80x5 for the external stair stringers, stringer seats and landing edge/middle beams (group 62, 34 SLN) and the internal stair sloped stringers (group 60, 8 SLN);
(2) SECT 4 L2 radials UB 457x191x89 -> UB 457x191x98; (3) external stair landing supports on the L1 ring (SLN 724, 725, 769, 770) SHS 100x100x5 -> SHS 80x80x6.3.
Everything else as v20. Picture: `v21_changed_members_reading.png`.
Run 13 Nov 2026, NguyenPC: 17:46-18:21, exit 0, 0 errors, 212 warnings (no new warning type vs v20), 35.7 min, peak RAM 10.1 GB.
The v20 folder and the v20 export were not changed. WinGRAF pictures from a copy (`26016-member-check\v21_wing\26016_v21_copy.cdb`).

Same layout and the same scripts as `v20_export` (paths moved to v21; `v20` in place of `v19m` as the comparison).
Files that carry the model name have `v21` in place of `v20` (`summary_v21.json`, `v21_text.zip`, `PART_A_v21.md`, `wingraf_recipe_v21.dat`, `compare_v20_v21.csv`, `sliding_overturning_v21.json`).

Extra in v21:
- `stair_ext.json`: `governing_forces` for every leg (12), not only the governing members.
- `buckling_group62_participation.json` (script `A_followup/scripts/buckling_g62.py`): group 62 (external stair) share in all 20 buckling modes of PLC 102 and PLC 119
  (max |u| in group 62 / max |u| overall, and the group 62 share of sum |u|^2). Largest: PLC 102 mode 20 (factor 9.50) 0.117 / 1.4 %; PLC 119 mode 19 (10.00) 0.099 / 1.0 %. The stair does not drive any of the 40 modes.
- `envelopes/`: ULS member force envelopes on v21 (same recipe as v20, read from a copy `v21\envelopes\26016_env_v21.cdb`).

Reading rules as in v19m_export.
