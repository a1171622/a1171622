# 26016 v16: new workflow vs SOFiSTiK BDK

Model: `26016_check_v16.dat` / `.cdb` (NguyenPC), 43 ULS combinations (101-130, 135, 141-148, 151-154), 407 members
(327 BDK members + the beam lines BDK does not list), S275, UK NA, Annex B.

## Result

- 3 members above 1.0, all L2 ring r 12 (UB 254x146x43): 68 = 1.05, 62 = 1.01, 69 = 1.01. Governing: 6.2.9
  bending + axial **at the node** (BDK 1.04 / 1.00 / 1.00). The design report takes this moment 300 mm from the node
  (stiffened connection, Wing 1 Nov), which this run does not do yet.
- Next: rings 57 0.98, 56 0.97 (eq. 6.62, same as BDK to 0.001).
- Columns max 0.41, stairs max 0.38, roof max 0.56.

## Agreement with BDK (eq. 6.61 / 6.62, 174 members with BDK > 0.2)

139 within 0.03, 154 within 0.05, mean difference -0.01. See `bdk_comparison.png`. The differences:

| members | this | BDK | why |
|---|---|---|---|
| L1 radials 169, 196, 211, 263 | 0.39-0.43 | 0.57-0.63 | BDK's number matches a buckling analysis of the whole 10.1 m member **with no intermediate restraint**. The BDK file gives the column at 3.5 m and the ring at 9.0 m (CVL REF STRT) on a joined member (MEMB + CONT); it looks as if BDK did not apply them. This workflow uses them. To confirm: one BDK run of member 263 with ECHO FULL. |
| L2 radials (UB 457, e.g. 92, 115, 122) | 0.06 lower | | Both use the ring restraints. The rest is not pinned down (BDK's own eigen model of the restraint at the centre line); this workflow is about 6 % less conservative here. |
| 223 (L1 radial piece, own member) | 0.70 | 0.58 | This workflow takes max My and max Mz over the length together (conservative); BDK combines section by section. |
| stair RHS 130, 133, 487 | +0.05 to +0.09 | | same reason (non-concurrent maxima), conservative. |
