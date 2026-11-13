# 26016 v21 kingpost - von Mises check of the shell model

Model `26016_check_v21` (run 13 Nov 2026), read only from the copy `26016_env_v21.cdb`; nothing re-analysed. Reading picture: `kingpost_reading_v21.png`.

Kingpost shells, all t = 20 mm, S275 (fy = 275 MPa, t <= 40 mm, gamma_M0 = 1.0): tube wall groups 6 + 7 (r 0.305, z 0-12.2, about CHS 610 x 20, 12,117 elements); horizontal collar / cap plates group 1 (r <= 0.916; Level 2 z 7.81 and 8.30, roof z 11.91 and 12.20; 18,055 elements); vertical radial fins group 2 (r 0.304-0.506, 18 per level; 5,328 elements). Base: 20 support nodes on the tube end. Each Level 2 / roof radial beam end is tied by kinematic constraints to 4 plate nodes (288 tied nodes); no beam shares a node with the shells.

Method: ASE shell forces of the 43 ULS STR combinations (101-130, 135, 141-148, 151-154) and SLS 201 are in the cdb (key 210/LC). Per element: sigma = n/t +- 6 m/t^2 at top / bottom, mid = n/t; sigma_v = sqrt(sx^2 + sy^2 - sx sy + 3 txy^2). 'Element' = element-centre forces (averaged over the element); 'gauss' = largest Gauss point (raw). Scripts: `scripts/kp_vonmises.py`, `scripts/kp_peaks.py`.

## Results, ULS (element centre, MPa, utilisation on 275)

| zone | max sigma_v | util | element | z / r / angle | LC | surface |
|---|---|---|---|---|---|---|
| horizontal collar / cap plates, Level 2 | 609.3 | 2.216 | 23531 | 7.811 / 0.602 / 334.8 | 122 | bottom |
| horizontal collar / cap plates, roof | 156.6 | 0.57 | 17671 | 11.914 / 0.51 / 179.6 | 107 | top |
| tube wall, Level 2 connection zone (z 7.4-8.7) | 137.5 | 0.5 | 50812 | 7.615 / 0.305 / 239.1 | 122 | bottom |
| tube wall, base zone (z 0-0.5) | 34.3 | 0.125 | 41481 | 0.028 / 0.301 / 9.1 | 145 | top |
| tube wall, between levels | 45.9 | 0.167 | 42798 | 11.418 / 0.305 / 275.1 | 110 | bottom |
| tube wall, roof connection zone (z > 11.5) | 83.1 | 0.302 | 54454 | 11.708 / 0.305 / 259.4 | 110 | bottom |
| vertical radial fin plates, Level 2 | 298.8 | 1.087 | 34073 | 7.803 / 0.498 / 240.1 | 122 | top |
| vertical radial fin plates, roof | 111.6 | 0.406 | 31557 | 11.906 / 0.498 / 280.0 | 110 | top |

## Local peaks at the radial ties (ULS, element centre, excluding elements closer than the distance to a tied or support node)

| zone | 0 mm | 50 mm | 100 mm | 150 mm |
|---|---|---|---|---|
| collar / cap plates, Level 2 | 609.3 (2.216) | 360.2 (1.31) | 360.2 (1.31) | 160.1 (0.582) |
| collar / cap plates, roof | 156.6 (0.569) | 156.6 (0.569) | 156.6 (0.569) | 62.2 (0.226) |
| radial fin plates, Level 2 | 298.8 (1.087) | 298.8 (1.087) | 298.8 (1.087) | 135.1 (0.491) |
| radial fin plates, roof | 111.6 (0.406) | 111.6 (0.406) | 111.6 (0.406) | 62.4 (0.227) |
| tube wall, Level 2 zone | 137.5 (0.5) | 137.5 (0.5) | 137.5 (0.5) | 137.5 (0.5) |
| tube wall, base | 34.3 (0.125) | 34.3 (0.125) | 32.5 (0.118) | 31.2 (0.113) |
| tube wall, between levels | 45.9 (0.167) | 45.9 (0.167) | 45.9 (0.167) | 45.9 (0.167) |
| tube wall, roof zone | 83.1 (0.302) | 83.1 (0.302) | 83.1 (0.302) | 83.1 (0.302) |

Raw Gauss-point peak (Level 2 bottom collar, LC 122): see kingpost_von_mises_v21.json ('gauss' rows). SLS 201 for reference: Level 2 collar 415 MPa at the same tie, tube wall 94 MPa.

## Reading and recommendation (Wing to decide)

- All 87 elements above fy are on the Level 2 bottom collar plate (z 7.81), next to the 4-node ties of the radial ends (max 609 MPa, element 23531, LC 122, 12 mm from a tied node). There the plate moment (32 kNm/m) exceeds the plastic moment of a 20 mm plate (27.5 kNm/m) and the transverse shear is 1.8 MN/m: a point-load artefact of tying a 457 deep beam end to 4 nodes, not the real bolted / welded end connection.
- 50-100 mm from the ties the peak is 360 MPa at the fin tip at 240 deg (re-entrant corner of fin and collar, a shell-model singularity); 150 mm or more away the Level 2 collar is 160 MPa (0.58) and the fins 135 MPa (0.49).
- Tube wall: 138 MPa (0.50) at Level 2, 83 (0.30) at the roof, 46 between levels, 34 at the base. Roof plates 157 (0.57), roof fins 112 (0.41).
- Recommended for the report: tube wall max 0.50 and plates 0.58 (at >= 150 mm from the ties), with a note that the beam-to-kingpost load introduction is not represented by the 4-node ties and is checked separately (connection design / IDEA). Alternative if Wing wants it conservative: refine the tie (couple the full beam end depth to the fins) and rerun.

## Pictures (WinGRAF, MPa, see pictures.json)

WinGRAF cannot envelope SV over load cases, so each picture shows the governing combination of its zone: LC 122 (G+Q+psiW +Y down) for Level 2 and the whole kingpost, LC 110 for the roof, LC 145 for the base. The plots average SV to the nodes (legend max 383 MPa at Level 2 for LC 122, against 609 MPa at the element centre in the table).

- `K1_kingpost_vonMises_LC122_iso.png`: Kingpost, von Mises SV, whole height, isometric (LC 122, legend max 382.6 MPa) - whole kingpost; peak on the Level 2 bottom collar plate at the radial ties
- `K2_kingpost_vonMises_LC122_opposite.png`: Kingpost, von Mises SV, opposite side (LC 122, legend max 382.6 MPa) - same as K1 from the opposite side
- `K3_L2_zone_vonMises_LC122.png`: Level 2 connection zone (z 7.5-8.6), von Mises (LC 122, legend max 382.6 MPa) - collar plates z 7.81 / 8.30, fins, tube; hot spots at the 4-node radial ties on the bottom collar
- `K3b_L2_bottom_collar_from_below_LC122.png`: Level 2 bottom collar plate (z 7.81) seen from below (LC 122, legend max 382.6 MPa) - ring of hot spots at r 0.6-0.7 = the tied nodes of the 18 radial ends; highest near 240 / 340 deg
- `K4_roof_zone_vonMises_LC110.png`: Roof connection zone (z > 11.5), von Mises (LC 110, legend max 120.9 MPa) - roof plates and fins, max well below fy
- `K5_base_zone_vonMises_LC145.png`: Base zone (z < 1.0), von Mises (LC 145, legend max 34.3 MPa) - tube wall at the 20 support nodes, low stress
- `K6_L2_zone_deformed_vonMises_LC122.png`: Level 2 zone, deformed shape x50 with von Mises (LC 122, legend max 382.6 MPa) - governing LC 122, local plate bending of the bottom collar under the radial ties

Recipe: `26016_kp_wing.dat` (WinGRAF on the copy cdb, PLBCONVERTER to PNG).
