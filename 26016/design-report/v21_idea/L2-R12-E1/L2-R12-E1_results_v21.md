# 26016 L2-R12-E1 (Level 2 ring to radial joint at r 12), rebuilt to drawing 970027-S01-ST-1103 rev 04, v21 forces

Joint: node 1485 (r 12.0, 0 deg, z 8.055), radial SLN 73 (UB 457x191x98) ends on the continuous L2 outer ring SLN 55 / 56 (UB 254x146x43).
Forces: 26016_check_v21.cdb (run 13 Nov 2026), 43 ULS STR combinations (101-130, 135, 141-148, 151-154), one IDEA load effect each.
IDEA StatiCa Connection 26.0, CBFEM, EN 1993-1-8. Report: `L2-R12-E1_000.pdf` (author CaSE, 13.11.2026). Model picture: `L2-R12-E1_as_built_v21.png`.

## Result: FAIL (Wing to decide)

| check | max | load effect | where |
|---|---|---|---|
| Analysis | 100 % | all | load reached in all 43 |
| Plates (plastic strain, limit 5 %) | **6.6 %** | LC 153 | existing ring UB 254 bottom flange next to the joint |
| | 4.9 % | LC 119 | ring top flange |
| | 2.8 % / 2.7 % | LC 121 / 122 | ring web / 20 ring stiffener at 315 (SLN 55 side); new plates <= 1.3 % |
| Bolts (6 x M24 10.9) | 60.7 % | LC 122 | |
| Welds | **109.1 %** | LC 121 | 20 ring stiffener at 315 to the ring flange (a 7.0) |
| | 107.6 / 106.1 / 104.5 / 103.5 % | LC 122 / 121 | 395x145x20 fin lower pieces to the ring web (a 4.2, 6 mm leg) |
| | 107.4 % | LC 122 | 20 inclined stiffener to the ring top flange (a 7.0) |
| | 98-100 % | LC 153 / 135 / 122 | bracket web / inclined stiffeners / top plates (SLN 56 side) |

Forces at the joint (IDEA axes, kN / kNm), LC 121: radial N -8.5, Vz -89.8, My -47.2; ring each side N +24.8, My +135.9, Vz +36.9 / -52.9.
The ring moment 135.9 kNm is close to the elastic moment of UB 254x146x43 (W_el 504 cm3 x 275 = 138.6 kNm; M_pl 155.7 kNm). In the member
check the same ring line is already above 1.0 (SOFiSTiK BDK SLN 56 1.063, AQB 1.066, LC 120). So the strain and the weld overloads at the joint come mainly
from the existing ring at its limit, not from the new plates or the bolts.

## How the model was built (assumptions to check)

- Reading of D1 / E as in `L2-R12-E1_reading_v21.png`, option (a): radial web passes the ring web through a slot. In IDEA the ring web stays whole and overlaps the radial web (slightly stiff). Radial bottom flange cut back over the ring (to 105 mm inside the ring centre line, covering the 10 deg ring chord).
- 395x145x20 plates each side of the radial web, centred on the ring web, from 33 to 428 mm above the bottom of steel; split around the ring top flange and web (upper piece + 2 lower halves each side), every piece welded to the ring.
- Bolts M24 10.9, holes 26, bearing, through plate + radial web + plate: rows 105 / 230 / 330 mm below the plate top (98 mm above the bottom of steel), columns +-39 mm from the ring web (35 mm edges).
- Bracket in the ring web plane each side: 10 mm web plate, 20 mm top plate 145 wide under the radial top flange out to 155 mm, 20 mm inclined stiffener from 155 mm at the top to 315 mm on the ring top flange.
- 20 mm ring stiffener at 315 mm each side, modelled full width and welded to both ring flanges (a half-plate on one side never connected in IDEA 26.0 and made the model a mechanism).
- Welds: throat a = 7.0 mm (10 mm leg) to flanges, a = 4.2 mm (6 mm leg) to webs (drawing note), double fillets. Plates S275 (as the other 26016 joints).
- Left out: the two 20 x 295 plates above the ring bottom flange (with them IDEA reported a mechanism; they stiffen the ring bottom flange, so leaving them out is on the safe side for the ring), the 205x70x20 stiffener and the 185x70x20 plate of section E.
- No contact between the radial top flange and the bracket top plate (IDEA has no weld or contact there) - the bracket stiffens the ring but does not carry the radial flange directly.
- Joint at 0 deg built (the v14 location): radial end Vz 89.8 / My 47.2 kNm. Other r 12 radial ends: 120 deg 92.3 / 43.1, 160 deg 92.6 / 44.0, 240 deg 91.1 / 47.9, 80 / 200 / 320 deg about 75 / 40. Ring end moments at the other r 12 nodes were not compared; a joint at 160 or 240 deg could govern by a few percent.

## Recommendation (for Wing)

1. The ring UB 254x146x43 at r 12 is at its limit near the radial joints in both the member check (BDK 1.06) and IDEA (6.6 % strain). A local reinforcement of the ring (for example the drawn 20 mm plates above the bottom flange made to work, or a heavier ring section) is needed before the welds can be sized; increasing only the weld sizes does not fix the flange strain.
2. If the ring is reinforced, rerun this joint; the bolts (61 %) and the new plates (<= 1.3 % strain) have reserve.
3. Please confirm the reading of the radial web at the ring (slot vs cope) and the role of the 20 x 295 plates.

## Where it fails (added 13 Nov 2026, see the lower half of `L2-R12-E1_as_built_v21.png`)

- 6.57 % plastic strain (LC 153) sits in the EXISTING ring bottom flange directly below the radial web / lower fin plates
  (the 20 x 295 plates that the drawing shows above the ring bottom flange are not in the model there).
- Welds above 100 %: ring stiffener at 315 (SLN 55 side) to ring top flange 109.1 % (a 7.0, LC 121) and to bottom flange 103.8 %;
  fin lower plates to ring web 107.6 / 106.1 % (SLN 55 side) and 104.5 / 103.5 % (SLN 56 side) (a 4.2, LC 122 / 121);
  inclined stiffener b (SLN 55 side) to ring top flange 107.4 % (a 7.0, LC 122); bracket web (SLN 56 side) 100.2 % (a 4.2, LC 153).

## Governing forces at the joint (IDEA axes, kN / kNm)

| LC | radial SLN 73 N / Vz / My | ring SLN 55 N / Vz / My | ring SLN 56 N / Vz / My |
|---|---|---|---|
| 121 | -8.5 / -89.8 / -47.2 | +24.9 / +36.9 / +135.9 | +24.8 / -52.9 / +136.0 |
| 122 | -7.6 / -89.8 / -47.2 | +22.2 / +36.9 / +135.9 | +22.2 / -52.9 / +135.9 |
| 153 | -9.2 / -89.4 / -47.2 | +27.0 / +36.6 / +135.9 | +27.0 / -52.8 / +135.9 |

## Sensitivity to the web weld size (6 mm leg read from the drawing note)

Rerun with 10 mm leg (a 7.0) to the webs: ring-web welds 107.6 -> 99.2 %, but the maximum weld stays 108.3 % (flange welds to the ring),
plate-to-plate welds 108.7 -> 107.9 %, plastic strain 6.6 % unchanged, bolts 60.3 %. The result is not governed by reading the web welds as 6 mm.

## Variants with the drawing's extra bottom plates (13 Nov 2026, picture `L2-R12-E1_variants_v21.png`)

| variant | what is added | connects | max plate strain (where, LC) | max weld (which, LC) | bolts |
|---|---|---|---|---|---|
| 0 | none (current model) | yes | 6.6 % ring bottom flange below the radial web / lower fins (LC 153) | 109.1 % 315 stiffener to ring top flange, a 7.0 (LC 121) | 60.7 % |
| 1 | 20 x 295 plates on the ring bottom flange, 140 wide (2 x 70 + web), from the radial web face to the 315 stiffener; long edges welded to the flange face (a 7.0), end to the stiffener, lower fins welded onto them | yes | 7.1 % ring bottom flange at the end of the new plate (LC 120) | 102.8 % 295 plate to ring bottom flange, SLN 55 side (LC 119) | 59.1 % |
| 2 | section E 185x70x20 plates under the fins (2 x 70 + web, 185 along the ring), edges welded to the flange face; radial web cut to sit on it | yes | 8.0 % ring bottom flange at the plate ends (LC 119) | 105.3 % ring top flange welds; 185 plate to flange 104.9 % (LC 120) | 60.4 % |

The earlier mechanism with the 20 x 295 plates came from modelling them as two halves either side of the ring web; as one plate welded to the flange face along its long edges they connect.
Both variants move the peak to the end of the new plate / weld on the existing ring bottom flange and raise it; neither brings it under 5 %. The 205x70x20 stiffener (top of section E) is away from the peak and was not tried.
Two variants were enough to show the trend (not the 4 allowed). Reading: the ring flange is near yield over the joint, so the peak is a local concentration at every attachment end; the IDEA result does not support "add the drawn plates" as the fix on its own.
