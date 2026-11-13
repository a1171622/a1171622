# 26016 L1 r 8.5 m: ring UB to radial UB, without the flange plates (2026-11-13)

Wing asked to see the L1 ring-to-radial joints (L1-R8-A, 7 joints; L1-R8-B, 2 joints) **without** the
top and bottom 12 mm flange half-plates 125x200 that were added in `v15\xml_A_flanges_asis` /
`v15\xml_B_flanges_asis`.

## Detail shown (no flange plates)

- Radial UB continuous. Ring UB stops at the radial web, with both flanges coped. The ring web is welded (6 mm fillet, a 4.2) to an
  end plate 125x150x12.
- 4 M20 8.8 go through both ring end plates and the radial web.
- Columns sit on 350x200x12 plates with 4 M20 into the radial flange. The column welds are a 4.2 on A and a 5.6 on B (current B model).

## How the models were made

There was already a no-flange set from 27 Oct (`v15\xml_asis`, `v15\xml_mz0`). I compared its IOM XML item by item
(points, members, sections, plates, bolt grids, welds, cuts, load cases, forces) with the current flange models:

- L1-R8-A (7): the only difference is the flange plates (8 half-plates and their 16 welds).
- L1-R8-B (2): there is one more difference. The column end-plate welds were a 4.2 then and are a 5.6 now.

So I made new no-flange models from the current flange models. I removed only the 8 flange half-plates and their
16 welds and changed nothing else. They are in `v15\xml_A_noflange_asis\` and `v15\xml_B_noflange_asis\`.
I checked all 9 joints in IDEA 26.0 in one batch with v15 as-is forces (2026-11-13). The A results came out
the same as the 27 Oct run, as expected.

## Files

| File | What |
|---|---|
| `26016_L1_noflange_sheet.png` | one sheet: views of A_040, A_000 and B_080 plus the results table |
| `<joint>_top.png`, `<joint>_under.png` | IDEA model views from above and from below (same renderer, camera and size as `screens_R8_final_v2`) |
| `L1_noflange_results.csv` | results for the 9 joints, as-is and Mz = 0 |

## Results

Plates = plastic strain as % of the 5 % limit. Bolts and welds = utilisation %.

| joint | as-is | plates | bolts | welds | case | Mz = 0 | plates | bolts | welds | case |
|---|---|---|---|---|---|---|---|---|---|---|
| L1-R8-A_000 | FAIL | 147.3 | 5.4 | 98.3 | LC_121 | PASS | 0.0 | 5.4 | 74.6 | LC_120 |
| L1-R8-A_040 | FAIL | 1119.1 | 76.2 | 255.4 | LC_135 | PASS | 0.0 | 8.3 | 69.7 | LC_121 |
| L1-R8-A_120 | FAIL | 194.0 | 5.7 | 98.4 | LC_120 | PASS | 0.0 | 5.6 | 74.1 | LC_121 |
| L1-R8-A_160 | FAIL | 209.4 | 6.1 | 98.5 | LC_145 | PASS | 0.0 | 5.6 | 76.4 | LC_119 |
| L1-R8-A_200 | FAIL | 199.0 | 6.2 | 98.8 | LC_148 | PASS | 0.0 | 5.1 | 64.0 | LC_119 |
| L1-R8-A_240 | FAIL | 183.0 | 5.7 | 98.6 | LC_119 | PASS | 0.0 | 5.6 | 71.7 | LC_122 |
| L1-R8-A_320 | FAIL | 487.6 | 9.9 | 151.0 | LC_135 | PASS | 0.0 | 5.2 | 63.9 | LC_120 |
| L1-R8-B_080 | FAIL | 220.1 | 10.2 | 98.9 | LC_120 | PASS* | 0.6 | 10.1 | 98.2 | LC_121 |
| L1-R8-B_280 | FAIL | 208.7 | 15.4 | 99.4 | LC_146 | PASS* | 0.1 | 15.0 | 97.8 | LC_122 |

- For a FAIL row, "case" is the governing case for plate strain. For a PASS row, it is the governing case for welds.
- As-is, A_040: the analysis stopped at 68 % of the load (FE runaway). Its percentages show that the plate cannot carry the load, not real utilisation values.
- Mz = 0 values come from the 27 Oct run (`v15\xml_mz0`). For A, that model is the same as the current one without flange plates.
  *For B, the 27 Oct model has column welds a 4.2 (now a 5.6), so B Mz = 0 is slightly conservative. B Mz = 0 was not rerun.

For comparison, with the flange plates (current design) all 9 joints PASS as-is: plates up to 0.6 %, welds up to 98.2 %.
Without them, every joint fails as-is on end-plate strain. That is the result that led to the flange plates.
