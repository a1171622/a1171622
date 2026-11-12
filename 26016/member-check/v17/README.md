# 26016 v17 member check input

v17 = v16 + stair B moved one bay (-20 deg, opening 20-60 deg at L2, column SLN 121 under the cut radial end moved 60 -> 40 deg)
+ the external stair from ground to L1 (group 62) from the fabrication DXF ALS-FAB-0140-REV00 (edited), confirmed 6 Nov 2026.

- `26016_check_v17.dat`: full chain (AQUA, SOFIMSHC, SOFILOAD, ASE, MAXIMA, BDK, buckling ASE, AQB). Run as one job.
- `builder/make_v17.py v16.dat v17.dat` rebuilds it from v16; `ext_geom.py` holds the external stair geometry
  (DXF rotated +20 deg about (93341, 0), z + 4.004 m); `validate.py` shows the stair wind generator reproduces v16 exactly.
- `REVIEW_v17.md`: independent review of the input. Finding 1 (no column under the cut L2 radial at 40 deg) is fixed by moving column 121.
