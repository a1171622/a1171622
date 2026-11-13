# 26016 v19 – Part A follow-up numbers (read-only, 12 Nov 2026)
Source: 26016_check_v19.cdb / .erg. No calculation started. Picture: A_followup_reading.png. Units kN, kNm, mm, m.

## A1 BDK max per group (util = max(nm-y, nm-z)) — util | SLN | LC
11 0.388 | 36 | 121
21 0.396 | 17 | 145
31 0.239 | 380 | 147
12 0.099 | 448 | 121
13 0.269 | 41 | 121
23 0.142 | 96 | 119
14 0.360 | 399 | 145
24 0.294 | 417 | 122
15 0.645 | 263 | 153
25 1.064 | 56 | 120 NOT PASSED  (UB 254 ring, SNO 2: 1.064 SLN 56 LC 120; UB 457 radials, SNO 4: 0.725 SLN 73 LC 148)
35 0.617 | 318 | 107
60 0.307 | 490 | 122
61 0.112 | 602 | 120
62 1.013 | 722 | 122 NOT PASSED (leg, Lcr = 2L)

## A2 AQB max per section — util | beam | group | SLN | LC
1 RHS 150x150x10: 0.384 Tot-int | 110113 | 21 | 9 | 120
2 UB 254x146x43: 1.075 Tot-int | 140020 | 25 | 56 | 120
4 UB 457x191x89: 0.657 Tot-int | 140389 | 25 | 1662 (SOFiMSHC split of a radial) | 145
5 RHS 200x100x6: 0.672 Tot-int | 190016 | 62 | 711 | 122
6 RHS 50x50x5: 0.207 Tot-int | 170128 | 60 | 466 | 120
7 5 mm plate (elastic): sigma-v 0.699 | 190055 | 62 | 727 | no LC (stress envelope)
8 SHS 100x100x5: 0.101 | 180006 | 61 | 602 | 120
9 SHS 80x80x6.3: 0.242 Tot-int | 190453 | 62 | 1648 (= leg 755) | 121

## A3 Buckling
PLC 102: mode 1 6.947, mode 20 9.583. PLC 119: mode 1 7.357, mode 20 10.148.
Mode 1 PLC 102 (LC 9201): group 11 raking column ground-L1, mid-height node 2369 (r 11.82, 171.4 deg, z 1.74), bows outward/sideways (ux -35.1, uz +8.1 of max 36.0). Other groups <= 23 % of the max (21: 0.23, 15: 0.17, rest < 0.04). Local member mode, not global sway.
Mode 1 PLC 119 (LC 9221): same type, group 11 column at node 2358 (r 11.82, 148.6 deg, z 1.74).

## A4 SLS deflections ('rel' = relative to the straight line between the span ends, 'abs' = global uz; down negative)
(a) L1 outer ring r 12 between raking-column nodes 40 deg apart (chord 8.2 m, polyline 8.33 m):
  G+Q+0.5W: worst LC 221 (G+Q+psiW +Y down), span 0-40 deg, node 1558 at 20 deg: 11.5 rel / 12.7 abs (L/725). LC 201: 11.2 rel / 12.5 abs, same span. This span carries the external-stair brackets.
  LC 11 only: span 320-0 deg, node 1559 at 340 deg: 8.1 rel / 8.4 abs (L/1030).
(b) L2 radial, kingpost hub r 0.66 to ring r 12 (L 11.34 m), radials with no inner column:
  LC 201: radial 220 deg, node 5532 (r 7.3): 17.9 rel / 20.0 abs (L/635).
  LC 11+12+13: same node: 13.5 rel / 15.0 abs (L/840). (LC 13 alone 13.7 rel.)
  Note: largest absolute is radial 240 deg (ring end at 240 is between columns 220/260 and drops 30.9): 201 33.1 abs (11.3 rel), Q 24.9 abs (8.6 rel), node 5568 r 9.7.
(c) Roof radial r 0.66 to 12 (11.34 m):
  LC 201 down: max rel 12.4 at 340 deg (15.6 abs); max abs 15.9 at 180 deg node 3890 (11.7 rel).
  LC 12 only: 8.1 rel / 8.4 abs (80 deg); max abs 9.5 at 220 deg (8.0 rel).
  Upward G+W: LC 206 (G+W +X uplift), radial 180 deg node 3891 r 7.3: +31.7 abs / +27.2 rel (L/415). With psiQ (LC 202): +31.1 abs / +27.4 rel.
(d) Max horizontal (SLS 201-221, framing nodes of each level): L2 1.7 mm node 2632 (r 11.83, 68 deg) LC 204 (G+W -Y+psiQ uplift), h 8.05 -> h/4700. Roof 1.8 mm node 3651 (r 11.83, 88 deg) LC 204, h 12.06 -> h/6700. (L1 1.5 mm LC 216. External stair landing nodes excluded: up to 20.7 mm, see the stair note.)
(e) L1 radials under the internal stair landing posts, span r 8.5 to 12.0 (3.50 m), posts at r 9.67 and 11.77:
  SLN 222 at 280 deg (posts 601/602): LC 201 1.8 rel / 2.9 abs (L/1900).
  Radial 40 deg, SLN 263 (posts 603/604): LC 201 1.8 rel / 2.8 abs (L/1940).
(f) Internal stair stringers (group 60, RHS 200x100x6), L1 to mid landing (z 4.05 -> 6.04, slope 30 deg, 3.98 m along / 3.45 m plan):
  LC 201: 4.0 mm vertical relative to the stringer ends (3.5 mm normal to the stringer), L/1000. SLS envelope worst 4.4 (LC 221). Upper flights (6.29 -> 8.05, 2.94 m) 0.7 mm.

## A5 Support reactions (force of the support on the structure, pz + = compression)
node | r (m) angle (deg) | 102 px | py | pz | 201 pz | EQU min pz (LC)
2 | 12.00 180.0 | 94.0 | 7.8 | 424.9 | 292.2 | -116.7 (131)
3 | 12.00 140.0 | 65.0 | -64.7 | 418.9 | 288.1 | -83.7 (131)
4 | 12.00 220.0 | 39.0 | 82.4 | 385.5 | 265.4 | -83.6 (131)
5 |  8.50 220.0 | -0.2 | -0.2 | 124.4 | 85.0 | -19.7 (132)
6 |  8.50 200.0 | 0.4 | 0.1 | 134.0 | 91.5 | 0.9 (131)
7 |  8.50 180.0 | -0.4 | 0.0 | 118.2 | 80.8 | -25.5 (132)
8 |  8.50 160.0 | 0.8 | -0.3 | 143.9 | 98.2 | 1.7 (131)
9 |  8.50 140.0 | -0.6 | 0.5 | 113.0 | 77.2 | -19.9 (132)
10 |  8.50 120.0 | 0.4 | -0.8 | 143.8 | 98.2 | 1.8 (133)
11 |  8.50 100.0 | -0.1 | 0.3 | 126.8 | 86.6 | -26.9 (134)
12 | 12.00 100.0 | -21.6 | -84.1 | 373.2 | 257.0 | -120.6 (133)
13 |  8.50  80.0 | -0.1 | -0.4 | 135.4 | 92.4 | 0.9 (133)
14 | 12.00  60.0 | -53.7 | -87.6 | 403.5 | 277.7 | -95.8 (133)
15 |  8.50  60.0 | 0.2 | 0.2 | 256.0 | 175.3 | -10.1 (134)
16 |  8.50  40.0 | -0.0 | -0.1 | 239.5 | 163.7 | 4.9 (131)
17 |  8.50  20.0 | 1.4 | 0.2 | 147.5 | 100.9 | -26.5 (131)
18 |  8.50   0.0 | -0.8 | -0.0 | 144.2 | 98.4 | 1.8 (132)
19 | 12.00  20.0 | -58.0 | -44.3 | 356.4 | 245.4 | -104.5 (132)
20 |  8.50 340.0 | 0.2 | -0.1 | 135.3 | 92.4 | -25.9 (131)
21 |  3.00  20.0 | 0.3 | -0.0 | 301.3 | 206.8 | 11.9 (131)
22 |  3.00  80.0 | 0.1 | 0.5 | 366.9 | 251.4 | 12.2 (134)
23 |  3.00 140.0 | -0.3 | 0.2 | 376.9 | 258.3 | 15.2 (132)
24 |  3.00 200.0 | -0.6 | -0.2 | 398.5 | 273.1 | 14.0 (132)
25 |  3.00 260.0 | -0.2 | -0.7 | 234.4 | 160.9 | 4.9 (133)
26 |  8.50 240.0 | 0.4 | 0.6 | 144.7 | 98.7 | 2.0 (134)
27 | 12.00 260.0 | 17.0 | 103.6 | 415.4 | 285.8 | -111.8 (134)
28 |  8.50 260.0 | -0.1 | -0.8 | 234.9 | 160.8 | -12.1 (133)
29 |  8.50 280.0 | -0.1 | -0.0 | 241.6 | 165.2 | 4.2 (131)
30 |  3.00 320.1 | 0.5 | -0.4 | 373.2 | 255.8 | 15.3 (133)
31 |  8.50 300.0 | 0.7 | -0.8 | 151.2 | 103.4 | -21.8 (133)
32 | 12.00 300.0 | -17.8 | 75.0 | 368.2 | 253.6 | -94.1 (134)
33 |  8.50 320.0 | -0.3 | 0.2 | 134.6 | 91.9 | 1.3 (134)
34 | 12.00 340.0 | -59.7 | 22.0 | 321.3 | 221.7 | -105.4 (132)
901 | x 11.68 y  -2.48 | -17.5 | -29.6 | -12.5 | -8.1 | -21.1 (131)
902 | x 13.73 y  -2.84 | 9.2 | 17.2 | 23.1 | 15.6 | -20.3 (132)
903 | x 12.09 y  -0.06 | -0.3 | 0.3 | 15.4 | 10.4 | -8.8 (132)
904 | x 14.14 y  -0.39 | -0.1 | 0.1 | 15.9 | 10.9 | -4.8 (133)
905 | x 14.04 y   1.02 | -0.3 | -0.1 | 20.3 | 13.8 | -4.3 (132)
906 | x 11.99 y   0.66 | -0.4 | -0.1 | 41.3 | 28.4 | -2.8 (131)
907 | x 13.59 y   3.53 | -0.3 | -0.0 | 31.4 | 21.5 | -2.7 (133)
908 | x 13.25 y   5.42 | -0.7 | -0.1 | 17.5 | 12.0 | 1.4 (134)
909 | x 10.55 y  -5.61 | 7.1 | 32.9 | -12.3 | -8.0 | -16.6 (133)
910 | x 12.36 y  -6.65 | -5.4 | -18.0 | 23.0 | 15.5 | -18.6 (132)
911 | x  9.32 y  -7.74 | -0.5 | -0.1 | 12.5 | 8.4 | -11.4 (134)
912 | x 11.11 y  -8.78 | -0.1 | -0.0 | 15.5 | 10.7 | -7.3 (131)
913 | x 10.14 y  -9.82 | -0.1 | 0.2 | 20.3 | 13.7 | -3.4 (132)
914 | x  8.79 y  -8.23 | -0.3 | 0.4 | 45.3 | 31.2 | -2.4 (131)
915 | x  8.19 y -11.46 | -0.2 | 0.2 | 31.4 | 21.5 | -2.8 (131)
916 | x  6.74 y -12.73 | -0.5 | 0.5 | 17.5 | 11.9 | 1.4 (132)
(stair 901-916 rows give x, y instead of r, angle)
Kingpost base, 18 nodes 5807-5824 (r 0.30): 102 sum px -10.1, py -5.7, pz 817.2; 201 sum pz 567.3; EQU min of the sum pz -30.2 (LC 134).
Also SPT 1001 / 1002 (r 0.30, 270 / 90 deg): 102 pz 29.4 / 41.7; 201 pz 20.4 / 28.9; EQU min -12.1 (134) / -12.1 (133). They are in the totals.
Grand total 102: px -15.8, py 5.7, pz 9581.6 (= SOFiSTiK stored; = 1.35 x 1920.1 G + 1.5 x 4659.6 Q). Grand total 201: pz 6579.7 (= G 1920.1 + Q 4659.6).
Column bases 2-34: base angles 20, 60, ... 340 at r 12 (raking, tops at 0, 40, ... 320), r 8.5 every 20 deg, r 3.0 at 20, 80, 140, 200, 260, 320.

## A6 reactions_basic_sums (sum Fx, Fy, Fz)
LC 1 SW: 0.0, 0.0, 872.3
LC 2 SDL floors/roof: 0.0, 0.0, 842.9
LC 3 SDL stairs: 0.0, 0.0, 28.9
LC 4 DL 0.2 kPa: 0.0, 0.0, 176.0
LC 11 LL L1: 0.0, 0.0, 2160.7
LC 12 LL roof: 0.0, 0.0, 259.3
LC 13 LL L2: 0.0, 0.0, 1915.3
LC 14 LL stairs: 0.0, 0.0, 324.3
LC 71 WL+X uplift: -308.0, -0.2, -997.1
LC 72 WL-X uplift: 300.4, 1.5, -931.0
LC 73 WL-Y uplift: -2.8, 317.9, -975.3
LC 74 WL+Y uplift: -3.4, -315.0, -953.6

## A7 ULS reaction envelope, STR only (101-154 without 131-134)
max pz 430.2 node 2 LC 146; min pz -112.6 node 12 LC 109 (1.0G+W -Y uplift); max horizontal resultant 117.6 node 27 LC 105 (px 16.7, py 116.4, pz 417.3).

## A8 L2 outer ring SLN 56, LC 120
Segment 340 -> 0 deg between radial nodes 1460 (340, radial SLN 1521 + column) and 1485 (0, radial SLN 1449, no column): 4.168 m (10 elements x 0.417; arc 4.189).
Node 1460 (340): N +13.5, Vz -91.0, My -163.2, Mz 1.4 (confirmed). Node 1485 (0): N +14.2, Vz -52.9, My +136.7, Mz 1.1.
psi (hogging negative at 340): M(0 deg) / M(340 deg) = +136.7 / -163.2 = -0.84. My changes sign at about 349.6 deg (sagging at the 0-deg end, which has no column).
N is TENSION (+13.5 kN, SOFiSTiK N > 0 = tension).

## A9 External stair group 62 per member type — BDK (SLN, LC) | AQB (SLN, LC)
stringers (8): 0.210 (758, 135) | 0.400 (758, 135)
stringer seats (4): 0.662 (711, 122) | 0.672 (711, 122)
landing 1 beams (8): 0.306 (751, 121) | 0.454 (751, 121)
landing 2 beams (14): 0.223 (720, 135) | 0.261 (720, 152)
legs (12, Lcr = 2L): 1.013 (722, 122) NOT PASSED | 0.242 (755, 121)
transverse leg beams 791-798 (8): 0.009 (793, 123) | 0.036 (793, 119)
ring brackets 724/725/769/770 (4): 0.033 (725, 122) | 0.034 (770, 152)
treads (40): AQB only, sigma-v 0.699 (727, stress envelope, no LC)
