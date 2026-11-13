"""26016 v19m - overall sliding, FoS = mu x sum Fz / H (mu 0.40, unfactored DL + WL, as the original consultant),
with the wind drag refined. Numbers are support-reaction sums from 26016_check_v19m (read from the cdb overview of the
envelope copy) and component sums of the wind load lines in 26016_check_v19m.dat (wind_split.py).
py -3.11 sliding_wind_refine.py  -> sliding_refine.csv, printed table"""
import csv, json, math, re, os
import numpy as np

OUT = os.path.dirname(os.path.abspath(__file__))
MU = 0.40
DL = 872.276 + 842.933 + 28.878 + 176.013          # LC 1-4 sum Fz (kN)
LL = 2160.726 + 1915.327 + 324.273                 # LC 11, 13, 14 (L1, L2, stairs); roof Cat H (12) not with wind
# wind cases with uplift (complete): reaction sums [Fx, Fy, Fz] of LC 71-74, lateral block 81-84, stairs 25-28
W = {"+X": dict(lc=71, H=308.000, U=997.101, lat=249.584, st=(58.416, 0.206), stz=41.314),
     "-X": dict(lc=72, H=300.415, U=930.958, lat=249.584, st=(50.831, 1.457), stz=-24.830),
     "-Y": dict(lc=73, H=317.931, U=975.344, lat=260.106, st=(57.825, 2.847), stz=19.557),
     "+Y": dict(lc=74, H=314.964, U=953.562, lat=260.106, st=(54.858, 3.354), stz=-2.225)}
QP = 2 * 0.613 * 25 ** 2 / 1000                     # kPa, ce 2, vb 25 m/s (model values)
# cladding as modelled (qp x 3 m per windward column, cf 1, every windward column, any facet angle) - from wind_split.py
CLAD_MODEL = {"+X": 111.5, "-X": 111.5, "-Y": 120.8, "+Y": 120.8}
RAK_MODEL, RAK_XFLOW = 60.1, 39.7                    # rakers / struts, model and cross-flow (sin^2 theta on the normal)
ROOF_UPLIFT = QP * 1.0 * (66.226 / (0.2 * QP))       # roof area from LC 85 (cf 0.2 down): 432 m2; uplift at cf 1.0
D_G, H_G, D_C, H_C = 17.0, 4.05, 6.0, 4.0            # ground enclosure r 8.5 (incl. 0.0), core r 3 (L1-L2)


def clad(cf): return QP * cf * (D_G * H_G + D_C * H_C)


rows = []
for d, w in W.items():
    def fos(H, U, extra_n=0.0): return MU * (DL + extra_n - U) / H
    base = fos(w["H"], w["U"])
    dc10 = clad(1.0) - CLAD_MODEL[d]; dc08 = clad(0.8) - CLAD_MODEL[d]; dr = RAK_XFLOW - RAK_MODEL
    du_roof = -ROOF_UPLIFT * 0.5                     # roof uplift cf 1.0 -> 0.5 (EN Table 7.6, alpha 0, phi 0)
    r = dict(direction=d, lc=w["lc"], DL=round(DL, 1), uplift=round(w["U"], 1), H=round(w["H"], 1), FoS_model=round(base, 3),
             H_clad_cf10=round(w["H"] + dc10, 1), FoS_clad_cf10=round(fos(w["H"] + dc10, w["U"]), 3),
             H_rakers_xflow=round(w["H"] + dr, 1), FoS_rakers_xflow=round(fos(w["H"] + dr, w["U"]), 3),
             H_drag_both_cf10=round(w["H"] + dc10 + dr, 1), FoS_drag_both_cf10=round(fos(w["H"] + dc10 + dr, w["U"]), 3),
             H_drag_both_cf08=round(w["H"] + dc08 + dr, 1), FoS_drag_both_cf08=round(fos(w["H"] + dc08 + dr, w["U"]), 3),
             FoS_drag_cf10_roof05=round(fos(w["H"] + dc10 + dr, w["U"] + du_roof), 3),
             FoS_model_DL_07LL_05W=round(MU * (DL + 0.7 * LL - 0.5 * w["U"]) / (0.5 * w["H"]), 2))
    rows.append(r)
with open(os.path.join(OUT, "sliding_refine.csv"), "w", newline="") as f:
    wr = csv.DictWriter(f, fieldnames=list(rows[0])); wr.writeheader(); wr.writerows(rows)
print(f"qp {QP:.4f} kPa  DL {DL:.1f} kN  cladding new cf1.0 {clad(1.0):.1f} kN, cf0.8 {clad(0.8):.1f} kN  roof uplift cf1.0 {ROOF_UPLIFT:.1f} kN")
for r in rows: print(r)
