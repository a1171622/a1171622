# 26016 L1 r 8.5 ring-to-radial joints without flange plates, v19m forces (13 Nov 2026)

IDEA StatiCa 26.0 CBFEM, one batch of the 9 joints, all 43 ULS cases (101-130, 135, 141-148, 151-154). Run folders on NguyenPC:
`C:\Sofistik workflow\idea-statica\v19m\xml_A_noflange\` and `...\xml_B_noflange\` (.xml + calculated .ideaCon). v15 folders not changed.

- Geometry = the v15 no-flange IOM files (`v15\xml_A_noflange_asis`, `v15\xml_B_noflange_asis`): radial continuous, ring coped, web end plate 125x150x12, 4 M20 8.8, no flange plates.
- Forces = member end forces at the joint node from `26016_check_v19m.cdb` (ring ends released MY + MZ), as the model gives them. Ring-end Mz = 0.000 kNm comes from the model; nothing was set to zero by hand.
- Force route: the IOM loads of the v15 templates were fitted per element against the v15 cdb (calib.py; round trip of the 9 v15 files within 0.12 kN / kNm), then filled from the v19m cdb (build_v19m_xml.py). Same SAF / IDEA sign convention.
- Topology since v17a: the L1-L2 column at r 8.5 is at 40 deg (SLN 121) and 60 deg (SLN 131). So **40 deg = B layout** (column above and below) and **80 deg = A layout**. B_040 = v15 B_080 geometry rotated -40 deg; A_080 = v15 A_120 geometry rotated -40 deg (chk_rot.py: all points unchanged relative to the joint, 0.0 mm). Every v19m beam at each node matched an IOM member (direction dot > 0.999) and no beam was left out.

| File | What |
|---|---|
| 26016_L1_noflange_v19m_sheet.png | views of B_040 and A_080 + results table + reading |
| L1-R8-B_040_top/under.png, L1-R8-A_080_top/under.png | IDEA model views, same renderer and camera as screens_R8_final_v2 |
| L1_noflange_v19m_results.csv, joint_table.md | per joint: result, plates / bolts / welds %, governing LC, max ring-end Mz in, v15 as-is and Mz = 0 beside |
| joint_check_summary_v19m.csv | raw IDEA batch summary |
| forces_v19m_idea_axes.json | the forces that went in (kN, kNm, IDEA member axes), per joint, member and LC |
| builder/ | scripts used |
