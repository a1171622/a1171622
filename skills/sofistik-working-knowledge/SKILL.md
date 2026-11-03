---
name: sofistik-working-knowledge
description: Use on any SOFiSTiK 2027 / CADINP / steel design job for Wing: how Wing wants work presented, PC and IT limits, MCP-server run rules, verified CADINP, ASE, BDK, AQB gotchas, model checks and the Python member-check route.
---

# SOFiSTiK working knowledge (distilled from the "Sofistik Automation" project, Oct to Nov 2026)

Load this at the start of any SOFiSTiK, CADINP or steel design task. It is what a previous project learned the hard way.
Job-specific state is NOT here; ask for the job's own notes or handoff.
Related skills: `idea-statica-joint-workflow` (connections), `structural-design-report` (reports), and the step-by-step
Haiku skills `sofistik-cadinp-author`, `sofistik-run-and-fix`, `sofistik-results-proof`.

## 1. Working with Wing

- Wing is a structural engineer, not a coder (Eurocode + UK NA, AS/NZS, SOFiSTiK 2027, IDEA StatiCa v26.0). Explain in engineering terms; guide step by step on anything Wing must click.
- Wing is the judge. Present your reading and a recommendation; let Wing decide. Questions = one-word answers, options on short lines, recommendation marked.
- Every findings report carries a picture from the model: zoomed, members/nodes/joints labelled, AND showing your reading (assumptions, boundaries, which member is continuous, where a void edge was taken) so Wing can correct it.
- Engineering work gets an independent, adversarial reviewer separate from the builder. "Make no mistake" = one reviewer + evidence. Big builds = lead + builders + reviewers; report what reviewers found and what was fixed.
- Lean by default; scale agents up only when Wing asks. Use a named model only when Wing names it. When usage is tight: small models for drawing/building helpers, a mid model for checkers.
- Scripts do arithmetic; every number has a receipt someone can re-check.
- Wing is often on the phone: do PC steps remotely where a tool allows, keep messages short.
- When Wing decides something that changes a release, a section or a load, tell every thread that owns a model run, a joint model or the report at once.

## 2. PCs and IT

- IT approval is slow and Wing will not write to IT. Do NOT add new MCP servers: new tools go inside the already-approved SOFiSTiK MCP server. Otherwise build on approved software (Python 3.12, SOFiSTiK Python, Rhino 8, IDEA + API, Excel), plain Python and skills. Never help bypass IT or ask Wing to loosen PC safety settings.
- Python on the PCs is `py`. The Windows Store "python.exe" alias breaks `python`; .bat files should try `py -3`, then `python`, then the install folders.
- Big runs go on the PC with the most RAM (a 311-member BDK peaked at 25 GB). Check which PC a tool lands on before assuming files are there; PCs may have no copy route between them (zip, Wing carries it, a session on the other PC unzips and checks the file count).
- A PC with strict safety settings may block Python scripts Claude wrote while data files get through: send data plus a small patch to an existing approved script.
- IDEA licence activations are limited; moving IDEA between PCs needs a free seat.
- No SOFILOAD-W wind licence: wind comes from own tools (CADINP loop or Python writing LINE SLN loads).
- If no PC is online, Wing runs the .dat in Teddy, inside the model's own project (a .dat run alone writes to a new, empty database).

## 3. Running SOFiSTiK through the MCP server

The local stdio server (`C:\Sofistik workflow\sofistik-mcp`, tools appear in cloud threads as `mcp__remote-devices__sofistik__*`) writes .dat files, runs sps.exe -B0, parses errors, reads the .cdb and searches the manuals.

Hard rules:
1. Never stop a running program. A stop leaves a lock flag INSIDE the .cdb ("CDBASE: WAIT FOR LOCK ABORTED BY USER"); copies are locked too. Clear only with Clean Locks (`dbinfo.exe <cdb> z` / `clear_cdb_lock`) and only when no live process uses the file.
2. One run per .cdb. Use `clone_cdb` for parallel work.
3. A Claude app restart KILLS running calculations. A run is done only when sps.exe has exited (`get_job_result`); a growing .lst is not proof. A dropped connection does not stop a run: check sps.exe before any rerun or lock clearing.
4. Estimate time and RAM first; set `timeout_minutes` well above the estimate (or server limit 0). Reference: 311 members x 47 combos, full chain 22 to 45 min on 62 GB (BDK ~25 min, .cdb ~4.4 GB, peak 25 GB), 2 h+ on 32 GB.
5. Put every program in one .dat (one database), run once. Track progress by .cdb mtime and `[ID n, LC m]` lines in the .lst, not by touching the run.
6. Do not copy multi-GB .cdb files through the device shell (~10 MB/s); rebuild instead. Zip .dat/.erg/.prt/.lst + summaries for Wing; leave .cdb/.plb in place.
7. Check PC runs every 30 to 60 min, not in a loop. Keep a RUN_LOG of incidents and lost time.
8. Check no IDEA batch or other run is using the PC before starting a big run.

Conventions confirmed: units m / kN / kNm; support reaction = force of the support on the structure (+Z load gives pz -1); right-hand rotations.
Tool limits: `cdb_node_results` caps at 5000 rows; CBEAM 100/0 has ~3 records per beam; BDK key 127/9100 has no decoder, read BDK tables from the .erg (end of BDK); AQB governing value = the "Total" line of Maximum Utilisation. Reactions per LC can be parsed from the .erg "Nodal Reactions" tables without the PC.

## 4. CADINP gotchas (checked in the 2027 manuals)

- Comma lists hold only ~25 values: use `LC (101 130 1)` or a LOOP. Lines max 255 chars; `$$` continuation is not for lists.
- No variable names containing DIV, SIN, COS, SQR (operators). Avoid `;` inside a `$` comment.
- `COPY NO/FACT` take only a plain #name or number: precompute with STO#. STO# persists in the CDB; RCL# reads it in a later file.
- LOOP body max 255 lines unless `LET#LOOPSIZE n`; `LOOP#I ARR` iterates an array.
- `SVAL IY/IZ` default unit is m4: write `[cm4]`.
- A MAXIMA ACT record resets GAMU/PSI; LC FACT does not scale temperature; QUAD uniform temperature is DTXY (DT = gradient); LC TYPE 'IMP' not usable in linear ASE or MAXIMA.
- SOFiLOAD deletes an LC's old loading when new loads follow its LC record, so a unified load file can follow the model file.
- Loads: unified and parametric (STO# switches, a legacy value per fix), no load counted twice in a combination, area loads checked against voids (stair openings).
- `LINE SLN '1@Z-'` loads the upper edge; `BEAM ... EZA ±h/2[mm]` gives a load eccentricity.
- Regular shell mesh: 4-sided SARs, every SLN `SDIV -n` (equal on opposite edges, even n), `SAR ... MCTL REGM`, `CTRL EFAC 0`, `CTRL PSUP -1`. Gmsh only for free-form shells.
- Removing members cleanly (e.g. columns) touches: SOFIMSHC SLN blocks and GRP line, every LINE SLN load on them (wind, EHF), "BEAM FROM GRP" temperature loads, BDK MEMB blocks, and BDK CVL restraint stations that relied on them.

## 5. ASE, BDK, AQB

- alpha_cr: `SYST PLC n` + `EIGE n BUCK LC m LMIN AUTO`, one ASE per primary LC; non-sway if >= 10, else escalate to the engineer. Dynamics/eigen needs 8 to 10+ elements per member.
- ASE MASS LC converts only nodal loads (error 2430); a mass LC must not carry FACD/DLZ (error 436).
- BDK (EN 1993-1-1 6.3) cannot use MAXIMA superposition LCs: build real COPY combinations. Restraints apply only to the next MEMB. CTRL persists item-wise: restate the full CTRL and the LC list per group. No load-height item; `MEMB SKY/SKZ` change only Ncr.
- BDK on MEMB + CONT (joined) members appeared to ignore CVL stations (result matched an unrestrained eigen over the full length; unconfirmed, one ECHO FULL run would settle it). Cross-check joined members by hand or with the Python route below.
- UK NA hollow sections: `SCL AUTO CURV B BETA 0.75 LLT0 0.4`, LTB AUTO (`LTB NO` is undocumented). PROF 'RHS' = hot finished, 'RHSC' = cold formed. AQUA UK annex: `NORM 'BS' 'EN199X-200X'`.
- Do not use moment redistribution for steel checks unless the engineer asks; check members directly to EN 1993-1-1. Where the engineer has a strengthened connection, the moment may be taken at the face of the strengthening (26016: 300 mm from the node) by the engineer's decision.

## 6. Python member-check route (no BDK needed)

- MCP `cdb_beam_forces` per LC (two or three calls by group; big results auto-save) -> harvest script -> forces table -> EN 1993-1-1 engine (6.2, 6.3.1 to 6.3.3, Annex A/B) built to match eurocodeapplied.com and Wing's Excel calculator to machine precision -> utilisation per member and combination.
- Code plug-in interface so AS 4100 etc. can follow (AS 4100 was a stub). Mcr from an own eigen solver (ring beam: v = 0 at the shear centre, twist free; column ends as LTB length).
- SOFiMSHC split lines need beam positions rebuilt from CBEAM + nodes. Class 4 only flagged; no warping stresses.
- Repo `member-check/` (PR #5) and Excel engine `EC3_beam_column_ULS.xlsx`.

## 7. Releases and model checks

- Every released node needs a continuous member through it, or ASE error 197 (mechanism).
- A web-only coped end needs MY AND MZ released; otherwise the joint check sees weak-axis moments the detail cannot carry.
- Read joint moments from the .cdb and confirm with Wing which member is continuous before choosing releases; check modelled ends against Wing's details. Wing's own model exports can carry OLD releases (26016 v13+ had strut joints released the pre-agreed way): diff the releases against the agreed detail on every new export.
- A curved or kinked ring that is pinned at every node can become a mechanism or drop alpha_cr sharply; a ring kinking 20 deg per node puts ~0.35 M into the radial tip, so either both members get moment joints or the ring is continuous.
- Nodes a few mm apart may be merged by SOFiSTiK: check the analysed node before calling it a gap.
- Prove results before using them: reaction vs applied load per LC, combination factors, alpha_cr, every member accounted for, independent hand checks on the top members and anything 0.9 to 1.1. Check SLS deflection of members that carry new posts or stairs (a landing post on a cantilevering radial failed span/180 on 26016).

## 8. Global stability checks Wing uses

- Overall sliding as the original consultant: FoS = mu x sum Fz / H, mu 0.40, unfactored DL+WL, DL+0.7LL+0.5WL, DL+LL+0.5WL; overturning separately; EQU (0.9G + 1.5W) per-support uplift table kept for anchors. Target FoS to be confirmed by Wing per job (1.5 assumed).

## 9. Where the previous work lives

- Repo https://github.com/a1171622/a1171622 (MCP server, Haiku skills, member-check workflow, skills/).
- Handoff note (3 Nov 2026, Claude Doc): https://claude.ai/artifact/2aQ6SLDb5bzBVJkRZHge2S (supersedes 19 Oct https://claude.ai/code/artifact/9ce19d3e-fa00-4238-8fa3-73b3d1ec80b4).
- NotebookLM notebooks: "sofistik manual", "bridge designs", "design aids".
