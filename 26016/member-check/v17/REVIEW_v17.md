# 26016 v17 independent review (6 Nov 2026)

Read only, SOFiSTiK not run. Line numbers refer to `26016_check_v17.dat` unless marked v16.

## Findings, most severe first

### 1. HIGH: the cut L2 radial at 40 deg has no column under its end
- **Where:** SLN 81, l.1767-1769; ring SLN 83/84, l.1773/1776; column SLN 121, l.1878; BDK block l.16071-16083.
- **What is wrong:** SLN 81 now ends at r 8.5 / 40 deg on the L2 r8.5 ring beams 83 and 84. Both ring beams have `FIXA 'MY' FIXE 'MY'`, so they give that node no vertical stiffness. The node also has no column above L1.
- **How it was before:** in v16 the cut radial (60 deg) ended on column SLN 121 (L1 to L2). Stair A follows the same pattern: its cut radial at 280 deg ends on column SLN 85, and its top radial at 260 deg has column SLN 96.
- **What v17 did:** it kept column 121 at 60 deg, where it now sits inside the span of SLN 87. It did not put a column at 40 deg. The r8.5 end of SLN 81 is therefore a cantilever tip about 5.5 m beyond the r3.0 ring. This changes the load paths for L2 sectors 20-60 and does not match the "same as stair A void" reading.
- **Where a column would go:** an L1 node already exists at r8.5 / 40 deg, at the top of ground column SLN 40 (l.1642-1644, (6.51012, 5.46350, 4.054)).
- **Fix:** ask Wing. The likely fix is a group 13 RHS 150x150x10 column from (6.51187, 5.46284, 8.055) to (6.51012, 5.46350, 4.054). Give it the same wind, EHF and temperature line loads as column 121, and add a BDK MEMB for it. Then change the SLN 81 BDK comment to "ends: column (new)". The fork at the r 8.5 end is only valid once that column exists.

### 2. MEDIUM: BDK on the L2 r12 ring assumes a fork at 40 deg that no longer exists
- **Where:** SLN 63 (l.16853-16864) and SLN 64 (l.16865-16876).
- **What is wrong:** each ring segment is checked as a 4.17 m member with fork ends. At 40 deg nothing frames into the ring any more, because radial 81 was cut there and no raking column reaches L2 at 40 deg. The fork at that node is unconservative.
- **Fix:** take Lcr and LTB length as the 8.34 m run from 20 to 60 deg. Use `SKY`/`SKZ` or a joined member, or hand-check it. #DECK = 0, so no deck restraint is assumed; that is correct, since this is the void.

### 3. MEDIUM: flight 2 stringers pass through the L1 r12 ring beam
This is a physical clash. It does not stop the run and does not create an unintended connection.

| Member | Clashes with | Centreline distance |
|---|---|---|
| SLN 713, right flight 2 inner stringer (l.4231-4232) | L1 ring SLN 161 | 22 mm |
| SLN 713 | raking column SLN 28 | 86 mm |
| SLN 758, left flight 2 inner stringer | L1 ring SLN 164 | 29 mm |
| SLN 758 | raking column SLN 25 | 111 mm |
| treads SLN 743/744 | L1 ring | 80-100 mm |
| treads SLN 788/789 | L1 ring | 80-100 mm |

- **Why it is still a problem:** all of these are above TOLG 5 mm, so SOFiMSHC will not merge the lines. But an RHS 200 and a UB254 cannot both exist at these distances.
- **Fix:** the DXF geometry needs a decision from Wing, either moving S_lo or adding a seat on the ring. Until then, the force path at S1 and S3 is not what will be built.

### 4. LOW: check alpha_cr and local modes after the run
The external stair adds flexible parts: 2.4-4.4 m SHS 100x5 legs with pinned bases, landing 1 frames that sway transversely, and 0.38 m brackets pinned at the ring. Its local modes could govern the ASE eigen runs (urs:9201/9202). Check that the lowest mode is not a local external-stair mode before using alpha_cr for the platform.

### 5. LOW: EHF self-weight for section 5 is overstated
- **Where:** l.10734 onward and the matching lines in LC 501-504. The error is inherited from v16.
- **What is wrong:** sections 5 in groups 60 and 62 use `#RHOS*0.0115`. The area of RHS 200x100x6 is about 0.00335 m2, so the EHF from these members is about 3.4 times too high. This is conservative.
- **Fix:** change 0.0115 to 0.00335 for SNO 5 lines. Sections 7 (0.002) and 8 (0.00187) are correct.

### 6. LOW: clearance at the stair B foot and S2
- Stair B outer stringer SLN 490 (l.2921-2924) passes about 0.28 m in plan from the S2 bracket and landing-2 corner (10.74, 5.03). At that point it is at about z 4.73; the landing beam is at 4.43.
- The stair B foot (r 11.75 / 20 deg) is about 0.27 m in plan from landing-2 node K.
- **Fix:** confirm the clearance and the walking route where the external stair arrives at L1 (15-25 deg).

## Checked and found correct
- **Syntax:**
  - No CADINP syntax problems found.
  - IF/ENDIF balances to 0 in every program block, including SOFiLOAD.
  - No line is longer than 255 characters.
  - SLN, SPT and LAR numbers 701-790, 901-916 and 605-610 do not collide with existing numbers. GRP 62 is declared (l.118).
  - The lowercase `e` exponents are already used in v16, which ran clean.
- **Stair B rotation:** all group 60/61 lines with y > 0 are rotated exactly -20 deg, including their DRX values.
  - The feet lie on SLN 184, the posts 603/604 on SLN 263, and the top on SLN 87, which now runs from r 12.
  - LAR 603/604 are rotated (l.4645-4646).
  - The barrier vectors in LC 15/16 are rotated, and MXX = -h·Fy, MYY = h·Fx, as in v16.
  - Wind LC 25-28 for stair A is identical to v16; only the stair B and new lines changed.
- **Void transformation:**
  - All 20 occurrences of LAR 32 and LAR 34 are transformed. Sector 32 is now handled exactly as v16 handled sectors 33/34; sector 34 is unconditional.
  - LC 454 is conditional and LC 456 unconditional in SOFiLOAD (l.6203-6230), in the ASE list (l.13452-13462), in both MAXIMA lists (l.13636-13646 and l.13823-13833), and in LET#P2O (l.12217).
- **External stair connectivity:**
  - Every member connects at shared or on-line points: the brackets lie exactly on rings SLN 161/170/164/165, and the treads are projected onto the stringers.
  - With pinned bases (SPTP PP), rigid frame joints and MYMZ releases at the ring end only (torsion kept), there is no mechanism.
- **Load signs:**
  - The barriers point outward in LC 15 and inward in LC 16 for every rail line checked.
  - EHF signs match LC 501-508 (+X, -X, -Y, +Y).
  - The projected-length factor in EHF matches v16's 0.8 convention.
  - Temperature for group 62 is added in both DT cases (l.8204, l.8226).
- **BDK:** the new SLN 87 block (r 12, column 121 station at S 3.5) is consistent. The group 62 MEMB records sit inside the `#STR` IF block of urs:9003 (l.19789-19987).
