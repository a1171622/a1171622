# Tools contract (fixed by the lead; tools engineer implements, skill designers write against it)
Folder: /mnt/project-files/skills/tools/   Run: python3 -I <script> ...   Python 3 stdlib (+numpy allowed).
Every script: prints ONE JSON object to stdout {"tool":..., "verdict":"PASS"|"FAIL"|"ESCALATE"|"CANNOT_RUN", "checks":[...], "notes":[...]}
and appends the same object as one line to <workdir>/proofs.jsonl when --workdir is given. Exit code 0 PASS, 1 FAIL, 2 ESCALATE, 3 CANNOT_RUN.
Never widen a tolerance from the command line.

1. dat_lint.py <file.dat> [--workdir W]                       G1 static lint (S1-S13 + load-atom duplicate check in combos)
2. canary_check.py <selftest_results.json> [--workdir W]      G0: compare saved cdb_* JSON of the self-test cantilever with hand values
3. equilibrium_check.py <load_cases.json> <expected.json> [--workdir W]
                                                              G4: stored reaction sums (from cdb_load_cases JSON) vs expected applied totals per LC
                                                              (expected.json written by the author stage or by a generator; missing LC -> ESCALATE)
4. combo_check.py <file.dat> <load_cases.json> [--workdir W]  G5: forward superposition: parse the combo table (COPY NO n FACT f, incl. STO#/LET# values)
                                                              from the .dat, predict each combo's reaction sums, compare (0.1 %). TH2 combos -> skipped with a note.
5. coverage_census.py <file.dat> <checked_members.json> [--workdir W]
                                                              every beam/SLN in the model is BDK-checked, AQB-only, excluded-with-reason, or UNACCOUNTED (-> FAIL)
6. receipts.py add|audit ...                                  number receipts: add {value, tool, args, cdb, cdb_mtime}; audit picks N at random for the lead to re-call
7. scorecard.py <workdir>                                     reads proofs.jsonl -> GREEN / AMBER / RED with the reasons
8. mutation_drill.py <file.dat> [--workdir W]                 injects known faults into COPIES and proves dat_lint/combo_check catch each one
README.md in the folder: one paragraph per script, its inputs (exact JSON shapes it expects from the MCP cdb_* tools), outputs, tolerances, evidence.
