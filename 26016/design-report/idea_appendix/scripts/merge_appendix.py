"""26016 IDEA StatiCa appendix: inventory.csv, index page and ONE merged PDF of the current-design joint reports.
Utilisations are read from each report's own Summary page and cross-checked with the run summary csv.
py -3.11 merge_appendix.py"""
import csv, os, re, glob, datetime, io
from pypdf import PdfReader, PdfWriter
from fpdf import FPDF

A = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I = r"C:\Sofistik workflow\idea-statica"
SETS = [  # order in the appendix
    ("L1-R8-A", I + r"\v19m\xml_A_noflange", "v19m (13 Nov 2026, Mz released at the r 8.5 ring ends)",
     "ring end plate onto radial web, no flange plates, 4 M20 8.8", r"C:\Sofistik workflow\26016-design-report\v19m_export\idea_L1_noflange\joint_check_summary_v19m.csv"),
    ("L1-R8-B", I + r"\v19m\xml_B_noflange", "v19m (13 Nov 2026, Mz released at the r 8.5 ring ends)",
     "as A + column above, no flange plates", r"C:\Sofistik workflow\26016-design-report\v19m_export\idea_L1_noflange\joint_check_summary_v19m.csv"),
    ("L1-R8-S", I + r"\v15\xml_strut_10deg_asis", "v15 (SAF 27 Oct 2026), as-is", "A-type strut joint, true 10 deg ring, double fin 2x12, 4 M20",
     I + r"\v15\xml_strut_10deg_asis\joint_check_summary.csv"),
    ("L1-R8-T", I + r"\v15\xml_strut_10deg_asis", "v15 (SAF 27 Oct 2026), as-is", "A-type strut joint, true 10 deg ring, double fin 2x12, 4 M20",
     I + r"\v15\xml_strut_10deg_asis\joint_check_summary.csv"),
    ("L2-R8-A", I + r"\v15\xml_L2haunch_flush_asis", "v15 (SAF 27 Oct 2026), as-is", "r12 haunch detail, ring bottom flush, M20",
     I + r"\v15\xml_L2haunch_flush_asis\part*\joint_check_summary.csv"),
    ("L2-R8-B", I + r"\v15\xml_L2haunch_flush_asis", "v15 (SAF 27 Oct 2026), as-is", "r12 haunch detail, ring bottom flush, M20",
     I + r"\v15\xml_L2haunch_flush_asis\part*\joint_check_summary.csv"),
]
LEVEL = {"L1": ("Level 1", 4.05), "L2": ("Level 2", 8.05)}


def csv_rows(pattern):
    out = {}
    for f in glob.glob(pattern):
        for r in csv.DictReader(open(f, encoding="utf-8-sig")):
            out[r["joint"].replace(".xml", "").replace("_joint", "")] = r
    return out


def summary(pdf):
    r = PdfReader(pdf); res = {"pages": len(r.pages)}
    for p in r.pages:
        t = p.extract_text() or ""
        if "Summary" in t and "Bolts" in t and "Welds" in t:
            for k in ("Analysis", "Plates", "Bolts", "Welds"):
                m = re.search(k + r"\s+([\d.]+)\s*(?:<\s*[\d.]+)?%?\s*(OK|Not OK)", t)
                if m: res[k] = float(m[1]); res[k + "_st"] = m[2]
            break
    return res


rows, docs = [], []
for prefix, folder, forces, detail, cpat in SETS:
    cs = csv_rows(cpat)
    for con in sorted(glob.glob(os.path.join(folder, "**", prefix + "_*.ideaCon"), recursive=True)):
        j = os.path.splitext(os.path.basename(con))[0]; ang = int(j[-3:])
        pdf = os.path.join(A, "reports", j + ".pdf")
        s = summary(pdf) if os.path.exists(pdf) else {}
        c = cs.get(j, {})
        gov = max(("Plates", "Bolts", "Welds"), key=lambda k: float(c.get(k + " max %") or 0) / (5.0 if k == "Plates" else 100.0)) if c else ""
        ok = s and all(s.get(k + "_st") == "OK" for k in ("Analysis", "Plates", "Bolts", "Welds")) and s.get("Analysis") == 100.0
        lev, z = LEVEL[j[:2]]
        rows.append(dict(
            joint=j, level=lev, location=f"{lev}, r 8.5 m, {ang} deg (z {z} m)", joint_type=prefix[-1], detail=detail,
            ideaCon=con, ideaCon_date=datetime.datetime.fromtimestamp(os.path.getmtime(con)).strftime("%Y-%m-%d %H:%M"),
            force_version=forces, report_pdf=("reports/" + j + ".pdf") if s else "MISSING",
            report_type="IDEA Connection detailed report (API report.generate_pdf, stored CBFEM results)" if s else "",
            report_pages=s.get("pages", ""), analysis_pct=s.get("Analysis", ""), plates_strain_pct=s.get("Plates", ""),
            bolts_pct=s.get("Bolts", ""), welds_pct=s.get("Welds", ""), status=("PASS" if ok else ("FAIL" if s else "MISSING")),
            governing_check_csv=gov, governing_case_csv=c.get(gov + " governing", ""),
            csv_check=("same" if c and all(abs(float(c.get(k + " max %") or 0) - float(s.get(k, -1))) < 0.06 for k in ("Plates", "Bolts", "Welds")) else ("no csv row" if not c else "DIFFERS")),
            above_90pct=("YES" if s and max(s.get("Bolts", 0), s.get("Welds", 0)) >= 90 else ""), included="yes" if s else "no"))
        if s: docs.append((j, pdf, s["pages"]))

# not included (listed for completeness)
NOT = [("L2-R12-E1_000", I + r"\v14\xml_E1\L2-R12-E1_000.ideaCon", "v14 (20 Oct 2026)",
        "r 12 haunch source joint (donor of the L2 haunch detail); only a v14 run exists, welds 100.6 % FAIL; not rerun on v15/v19m: NOT included, needs a decision"),
       ("L2-R8 haunch flush M24 variant (18)", I + r"\v15\xml_L2haunch_flush_M24_asis", "v15", "later M24 bolt variant (4 Nov); current table uses the M20 run: NOT included"),
       ("L1-R8-A/B flange plate versions", I + r"\v15\xml_A_flanges_asis, xml_B_flanges_asis, v15\xml_A/B_noflange_asis", "v15",
        "superseded by the v19m no-flange runs: NOT included")]
for j, p, f, why in NOT:
    rows.append(dict(joint=j, level="", location="", joint_type="", detail=why, ideaCon=p, ideaCon_date="", force_version=f,
                     report_pdf="", report_type="", report_pages="", analysis_pct="", plates_strain_pct="", bolts_pct="", welds_pct="",
                     status="not included", governing_check_csv="", governing_case_csv="", csv_check="", above_90pct="", included="no"))
with open(os.path.join(A, "inventory.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

# ---------------- index pages
inc = [r for r in rows if r["included"] == "yes"]
def build_index(NIDX):
    start = {}; pg = NIDX + 1
    for j, _, n in docs: start[j] = pg; pg += n
    pdf = FPDF("P", "mm", "A4"); pdf.set_margins(12, 12, 12); pdf.set_auto_page_break(True, 12)
    pdf.add_page(); pdf.set_font("Helvetica", "B", 13)
    pdf.multi_cell(0, 6.5, "26016 Concourse viewing platform\nAppendix - IDEA StatiCa Connection reports, all r 8.5 m joints (current design)")
    pdf.ln(1); pdf.set_font("Helvetica", "", 8)
    pdf.multi_cell(0, 4, f"Compiled {datetime.date.today():%d %b %Y}. One IDEA StatiCa 26.0 detailed report per joint, generated with the IDEA Connection API "
                   "from the calculated .ideaCon projects (stored CBFEM results, no re-analysis). Plates = plastic strain against the 5 % limit; bolts and "
                   "welds = utilisation. Status from each report's own Summary page. ULS combinations 101-130, 135, 141-148, 151-154 (critical cases per joint). "
                   "Level 1 A and B joints are on the v19m forces (no flange plates, ring-end Mz released); strut joints and all Level 2 joints are still on the "
                   "v15 forces. Not included: L2-R12-E1_000 (v14 only), superseded variants (see inventory.csv).")
    pdf.ln(2)
    W = [26, 44, 50, 16, 14, 14, 16, 10]
    pdf.set_font("Helvetica", "B", 7.5)
    for h, x in zip(["Joint", "Location", "Model / force version", "Plates %", "Bolts %", "Welds %", "Status", "Page"], W): pdf.cell(x, 5, h, border=1, align="C")
    pdf.ln(); pdf.set_font("Helvetica", "", 7.5)
    for r in inc:
        fv = "v19m, no flange plates" if r["force_version"].startswith("v19m") else ("v15 as-is, strut 10 deg ring" if r["joint"][:7] in ("L1-R8-S", "L1-R8-T") else "v15 as-is, haunch flush M20")
        vals = [r["joint"], r["location"].replace(" (z 4.05 m)", "").replace(" (z 8.05 m)", ""), fv, f"{r['plates_strain_pct']:.1f}",
                f"{r['bolts_pct']:.1f}", f"{r['welds_pct']:.1f}", r["status"], str(start[r["joint"]])]
        for v, x in zip(vals, W): pdf.cell(x, 4.4, v, border=1, align="L" if x > 20 else "C")
        pdf.ln()
    return PdfReader(io.BytesIO(bytes(pdf.output()))), start


ip, start = build_index(1)
if len(ip.pages) != 1: ip, start = build_index(len(ip.pages))
wr = PdfWriter()
for p in ip.pages: wr.add_page(p)
wr.add_outline_item("Index", 0)
parents = {}
for j, path, n in docs:
    first = len(wr.pages)
    for p in PdfReader(path).pages: wr.add_page(p)
    grp = {"L1-R8-A": "Level 1 A joints", "L1-R8-B": "Level 1 B joints", "L1-R8-S": "Level 1 strut joints S",
           "L1-R8-T": "Level 1 strut joints T", "L2-R8-A": "Level 2 A joints (haunch)", "L2-R8-B": "Level 2 B joints (haunch)"}[j[:7]]
    if grp not in parents: parents[grp] = wr.add_outline_item(grp, first)
    wr.add_outline_item(j, first, parent=parents[grp])
    assert first + 1 == start[j]
if hasattr(wr, "compress_identical_objects"): wr.compress_identical_objects()
out = os.path.join(A, "26016_IDEA_StatiCa_all_joints.pdf")
with open(out, "wb") as f: wr.write(f)
print(out, len(wr.pages), "pages", round(os.path.getsize(out) / 1e6, 1), "MB")
print("included", len(inc), "missing", [r["joint"] for r in rows if r["status"] == "MISSING"],
      "fail", [r["joint"] for r in inc if r["status"] != "PASS"], ">=90%", [r["joint"] for r in inc if r["above_90pct"]],
      "csv differs", [r["joint"] for r in inc if r["csv_check"] != "same"])