---
name: idea-statica-joint-workflow
description: Use when checking steel connections in IDEA StatiCa 26.0 from a SOFiSTiK model for Wing: geometry-first drawings, SAF export, IOM XML build, critical load cases, batch runs and reading CBFEM results.
---

# IDEA StatiCa joint workflow (SOFiSTiK -> IDEA 26.0), learned on 26016, Oct to Nov 2026

Load with `sofistik-working-knowledge`. Every lesson here cost at least one rerun.

## 1. Order of work (Wing's rule: geometry first)

1. Inventory joint types from the model (classify nodes by level, ring, member set; fold nodes < 20 mm apart). Code them Level-Ring-Type-Angle, e.g. L1-R8-S-020 (type letters by frequency, angle anticlockwise from +X).
2. Draw every type (parallel helpers are fine): members, plates, bolts, welds, cuts, which member is continuous, and the assumptions, labelled. Get Wing's yes per type. Anything built before that is unconfirmed.
3. Check the model releases match the agreed detail at every joint (continuous member continuous in the model, ended member released in the model, web-only coped ends released for MY AND MZ). Fix the model, not the joint.
4. Export forces (SAF), build IOM XML per joint, import + run CBFEM, read results, show pictures.
5. Report with screenshots from the IDEA 3D scene (IDEA cannot export window screenshots; render from the scene in the file) and a combined table.

## 2. Forces

- SOFiSTiK `+PROG SAF_EXPORT`: `CTRL OPT LCS VAL1 'ZYX_IDEA'`, `EXPO TO "f.xlsx" RESU YES` (without RESU no forces), select only the ULS combinations wanted (26016: 101 to 130, 135, 141 to 148, 151 to 154; temperature dropped by Wing's decision).
- SAF result signs = IDEA's convention; vs vector convention N +, Vy -, Vz -, Mx -, My -, Mz +. Check every node balances (< 1 N).
- Combinations go in as an Exclusive Variable group + one CombiInputEC each.
- Send only the critical ULS cases per joint (all cases made runs too slow): per member the top 3 cases by N/Npl + Mx/Mt + My/Mpl,y + Mz/Mpl,z plus the largest shear ratio; per joint the top 3 by that sum. Cases Wing ruled out are dropped first. Ranking uses absolute values, so a sign-reversal case can drop out: any joint above ~90% gets a final all-cases run.
- Never zero a force on the IDEA side (leaves the joint unbalanced): take forces from a SOFiSTiK model with the matching release.

## 3. Building the IOM (the 26.0 API cannot add plates, bolts or welds)

Route: SAF xlsx -> joint JSON (members, roles, direction vectors) -> IomGen (C#, NuGet IdeaStatiCa.OpenModel 26.0.x, .NET 8, buildable in the cloud) -> IOM XML -> `run_import.bat` (pip `ideastatica-connection-api` 26.0.*, needs aiohttp installed by hand) imports, runs CBFEM, writes joint_check_summary.csv.

Geometry rules:
- Members at their TRUE plan angle from the model direction vectors, never squared up (26016 L1 ring chords are 10 deg off square to the radial).
- Eccentricities (e.g. ring bottom flush with a deeper radial) go on Member1D. IDEA ignores Element1D offsets: on 26016 every L2 ring sat 102 mm too high until this was found.
- The continuous member in IDEA must be the continuous member in the model, and vice versa.
- A plate that crosses a web (flange plates through a ring web) is modelled as two half plates, one each side.
- Welds: IDEA ignores WeldData Start/End and welds the whole touching edge; control length with a cope or cut. One DoubleFillet on the web centreline, not two fillets. On skewed members put weld points along the plate's own in-plane axis.
- Copes: negative PlateData (IsNegativeObject) + CutBeamByBeamData (CuttingObject = that plate, Method = Surface).
- Ended member on a continuous one: CutBeamByBeam against the continuous beam (Surface for a web end plate, BoundingBox for a column on a flange), Offset = plate thickness, and put the weld on the cut (IsWeld + WeldDefinition), never a second WeldData on the same edge.
- Bolt grids through several parts (two end plates + web) work.

## 4. Running

- At most 2 IDEA batches at once on the 16-core PC (3 was too many). ~1 to 2 min per joint; results are written only at the end.
- Do not touch .cdb files from the IDEA thread; check no SOFiSTiK run is live before a big batch.
- Keep each variant in its own folder (e.g. xml_<detail>_asis, xml_<detail>_mz0) and a summary CSV per batch; never overwrite a folder Wing has seen.

## 5. Reading results

- A joint that "finishes" in ~2 s was not calculated (weld clash / duplicated welds).
- Stopping short of 100% load = broken model or a real mechanism: find out which (stub members, missing weld, released member with nothing to bear on).
- "Plates" = plastic strain vs 5% limit, not a utilisation; hundreds of % = FE runaway. Welds at ~100% beside a yielding plate do not improve with bigger welds: fix the plate first (stiffeners, thicker plate).
- IDEA has no bolt slip: note snug-tight bolts or slotted holes on drawings where restraint forces (temperature) are ignored.
- Compare variants in one table (as-is vs alternative), state which governs and the governing case.

## 6. 26016 details that passed (reference, not rules)

- L1 r 8.5: radial continuous, ring end-plated onto the radial web, 12 mm flange half-plates, M20 8.8, 6 mm fillets; strut joints as A type + double fin 2x12 mm, 4 M20 in double shear (welds govern 98 to 99%).
- L2 r 8.5: haunch detail, end plates 170x390x20 both sides, 6 M30 8.8, 12 mm haunch web, ring bottom flush (max 86%).
- Files: builder in /mnt/project-files/idea-statica/v15/builder/ (build_joints.py, critical_cases.py, joint_geometry.py, Program.cs), lessons /mnt/project-files/idea-statica/joint-builder/LESSONS_LEARNED.md.
