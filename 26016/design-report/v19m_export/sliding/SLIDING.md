# 26016 v19m - overall sliding with refined wind drag (13 Nov 2026)

Check (as the original consultant): FoS = 0.40 x (DL - wind uplift) / H, unfactored DL + WL. Model 26016_check_v19m, reaction sums of LC 1-4 (DL 1920.1 kN) and the complete wind cases with uplift 71-74 (blocks 81-84 lateral, 25-28 stairs, 21-24 lateral + roof/deck uplift).
Reproduced: min FoS 1.19 (wind -Y: H 317.9 kN, uplift 975.3 kN); +X 1.20.

Wind lateral, wind -Y: cladding 120.8 kN, rakers/struts 60.1 kN, deck edges + balustrade 79.2 kN, stairs 57.8 kN. Uplift: roof 331 kN (cf 1.0), L1 + L2 decks 625 kN (cf 1.0), stairs 20 kN.

Refinements (nothing changed in the model yet):
- A cladding: modelled as qp x 3 m on every windward column, cf 1.0, in the wind direction = 30 m + 9 m loaded width on a 17 m (ground, r 8.5) + 6 m (core, r 3) enclosure. Refined: closed cylinder, cf on the projected width (EN 1991-1-4 7.9, Re about 4e7, psi_lambda 1.0 kept): cf 1.0 (profiled cladding) 71.1 kN, cf 0.8 (smooth) 56.9 kN.
- B rakers / struts: cross-flow principle (normal wind component, q sin^2 theta), cf 1.45 kept: 60.1 -> 39.7 kN. Engineer's judgement, not explicit in EN 1991-1-4.
- C (not drag) roof uplift cf 1.0 -> 0.5, EN Table 7.6 alpha 0 phi 0.

| min FoS over 4 directions | value |
|---|---|
| model now | 1.19 |
| A (cf 1.0) | 1.38 |
| A + B | 1.49 |
| A (cf 0.8) + B | 1.58 |
| A + B + C | 1.76 |

Per direction: sliding_refine.csv. Picture: sliding_wind_refine.png. Scripts: wind_split.py (component sums from the .dat load lines and SLN lengths), sliding_wind_refine.py, draw_sliding.py.
If adopted, the same changes should go into the SOFiSTiK wind blocks (STO#BCL route -> cylinder load, raker cf per member angle) and the model rerun, so member design uses the same wind.
