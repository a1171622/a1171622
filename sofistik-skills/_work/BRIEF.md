# Brief for the skill-design team (written by the lead, 2026-10-18)

## Goal (Wing's words)
"exploring writing very detailed sets of skills to instruct a haiku model to complete the workflow
autonomously successfully ... agents under your management will have discussion, brainstorming and
ideas, you will be the judge ... Everything is to have very robust proof checking, maximise novelty ideas"

Wing = structural engineer, not a coder. SOFiSTiK 2027, Eurocode (+UK NA) and AS/NZS.

## Scope = "the workflow"
The SOFiSTiK automation chain this project built:
1. write unified, parametric CADINP (.dat) (variables, not hard-coded values; no load counted twice in a combo)
2. run it through the SOFiSTiK MCP server on PC NguyenPC3 (tools named mcp__...sofistik__run_calculation etc.)
3. parse errors/warnings, fix, re-run
4. read .cdb results (cdb_* tools)
5. member checks: BDK buckling (EN 1993-1-1 6.3), ASE alpha_cr buckling eigenvalue, AQB cross-section
6. reports (Python report tool + SOFiSTiK-native hybrid)
(Wind loads tool and IDEA StatiCa joints are optional add-ons; include only if judged ready.)

## The executor
A Claude HAIKU model will follow the skills and do the work autonomously. Skills are SKILL.md files
(frontmatter name + description, then Markdown body). Only up to 3 skills can be delivered in one go,
each self-contained (Haiku may not see /mnt/project-files when it runs on the PC). The lead (a
stronger model) stays the "brain" that dispatches Haiku and judges its output.

## Where the evidence is (READ these, cite them)
- Project memory (hard-won lessons): /tmp/claude/memory/team/silo/*.md  (MEMORY.md is the index;
  sofistik-long-runs.md, sofistik-bdk-cadinp-facts.md, project-sofistik-mcp.md,
  project-sofistik-benchmarks.md, project-26016-load-audit.md, project-26016-ltb-check.md,
  wind-beam-loads-tool.md, idea-iom-import-lessons.md, sofistik-report-generator.md)
- MCP server source + docs: /mnt/project-files/sofistik-mcp/ (README.md, CHANGELOG.md, sofistik_mcp/server.py = tool list)
- Run incident log: /mnt/project-files/26016/member-check/RUN_LOG.md
- Benchmarks with known answers: /mnt/project-files/sofistik-benchmarks/ (BENCHMARK_RESULTS.md + .dat inputs)
- Real inputs: /mnt/project-files/26016/audit/26016_loads_unified.dat, /mnt/project-files/26016/ltb/*.dat,
  /mnt/project-files/26016/member-check/run/
- Combination template: /mnt/project-files/sofistik-templates/EN1990_combinations_buildings.dat
- Report tool: /mnt/project-files/reports/sofistik_report/ (README.md, CONTRACT.md)
- Manuals (PDF, large): /mnt/project-files/Sofistik workflow/*_1.pdf (English). Only open if needed; use pdftotext on a page range.

## Hard rules for everything you propose
- NEVER start SOFiSTiK runs now: a 26016 run is live on NguyenPC3 with ~4 GB RAM free. Offline work only.
- Never stop a running program; never touch a .cdb another run is using (one run per .cdb).
- Claims must carry evidence (file:line, memory file, manual page). Mark anything inferred as inferred.
- Do NOT call any mcp__hearthbot__ tools. Do not write outside /mnt/project-files/skills/_work/ .
- The shared folder is a network mount: don't grep -r the whole of /mnt/project-files (PDFs); search specific folders/text files.
