---
name: structural-design-report
description: Use when writing, rebuilding or updating a structural design report (Word + PDF) for Wing in the CaSE house style from SOFiSTiK and IDEA results: structure, wording rules, figures and the scripted build.
---

# Structural design report in the CaSE house style (learned on 26016, Oct to Nov 2026)

Load with `sofistik-working-knowledge`. The report goes out under CaSE's name, so it must read like CaSE's own reports, not like an AI draft.

## 1. Structure (follow Wing's sample, e.g. 970021-RPT-01-B; ask for the sample on a new job)

Cover (job title, report number, revision, initials of author / checker / approver, cover picture Wing supplies), contents, then:
1 Introduction; 2 Reference (drawings, codes, previous reports); 3 Description (with a previous vs current table when it is a modification); 4 Design loads (dead, imposed, wind, sway / EHF, temperature, load cases, STR / EQU / SLS combinations with the factor table); 5 Methodology; 6 Analysis (model, supports, releases, pictures); 7 Structural design (7.1 SLS, 7.2 ULS members, special member checks, global stability, connections, 7.3 base stability and reactions); 8 Conclusion; Appendix A connections (joint table + IDEA reports); Appendix B drawings.
- All tables and charts go in the body; the appendices hold only drawings and software reports.
- Ask Wing which numbers, joint names and cover details to use; use Wing's own draft edits over anything generated.

## 2. Wording rules (Wing, 29 Oct 2026)

- Full consultancy sentences, mostly passive: "The verification ... was carried out ... and found to be satisfactory as tabulated below", "has been adopted based on the Client's input", "hence", "Where, G is the dead load".
- "Appendix", never "Annex" or "Annexure".
- No dashes of any kind in prose: no hyphenated words (first order, cross section, ground floor), ranges as "98 to 99%", "Level 1 to Level 2". Keep code and drawing numbers (EN 1993-1-1, 970027-S01-ST-1101) and joint codes (L1-R8-A) as they are.
- Dates as 28.10.2026. No [brackets] placeholders left in. No short fragments with colons.
- Short prose; the tables carry the content.

## 3. Engineering presentation choices Wing made

- No moment redistribution: check members directly to EN 1993-1-1 (6.2, 6.3.3 eq 6.61 / 6.62) and show the calculation (Wing's Excel calculator / Python engine as the receipt). Utilisation limit stated (KK asked for 90%).
- Where a connection is strengthened, the member moment may be taken at the face of the strengthening if Wing says so; state the distance and both values.
- Base stability as the original consultant did it: overall sliding FoS = mu x sum Fz / H (mu 0.40) for unfactored DL+WL, DL+0.7LL+0.5WL, DL+LL+0.5WL, plus overturning, plus the EQU per-support uplift table for anchors.
- Connections: a joint table (code, detail, plates, bolts, welds, governing utilisation and case) plus IDEA screenshots; IDEA PDFs in Appendix A.
- Every number in the report comes from a results file (results.json etc.), never typed by hand.

## 4. Build pipeline (scripted, rebuilt every round)

- `build.py` (python-docx) writes the .docx from results JSON files + figures; `omml.py` converts a LaTeX subset to Word equations (OMML); `combos.py` writes the combination factor tables.
- Render with LibreOffice headless twice: the first render finds the page of every heading (pdftotext), writes pagemap.json, and the second builds the static contents page from it. Equations need libreoffice-math installed.
- Figures: matplotlib from model geometry (labelled members, nodes, supports) and WinGRAF batch pictures (`+PROG WING` ... then `+PROG PLBCONVERTER` to PNG; thicken thin lines with a PIL MinFilter(3)).
- Before sending: page through the PDF picture by picture, check figure numbers, table numbers, cross references and the contents page.
- Keep the previous issue in archive/ with its date; deliver docx + pdf to the job's design-report folder and the PC copy.
- 26016 example: /mnt/project-files/26016/design-report/ (scripts/case_version/build.py, README.md).

## 5. Open items to ask for early

Platform or site photos for the introduction figure, IDEA PDFs (often only on the PC), the required stability factor of safety, and the reviewer's (KK) comments list.
