"""26016 IDEA appendix, all 36 r 8.5 joints on the v19m forces: index page (consultancy wording), merged PDF with
bookmarks, inventory.csv (updated) and a text scan of every report for 'Claude' / 'AI' / 'Wing'.
py -3.11 merge_appendix2.py"""
import csv, os, re, glob, io
from pypdf import PdfReader, PdfWriter
from fpdf import FPDF

A = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I = r"C:\Sofistik workflow\idea-statica"
PDFS = os.path.join(A, "reports_v19m"); PROJ = os.path.join(A, "projects_v19m")
SRC = {  # group prefix -> (source folder of the calculated v19m .ideaCon, detail)
    "L1-R8-A": (I + r"\v19m\xml_A_noflange", "ring end plate onto radial web, no flange plates, 4 M20 8.8"),
    "L1-R8-B": (I + r"\v19m\xml_B_noflange", "as A + column above, no flange plates"),
    "L1-R8-S": (I + r"\v19m\xml_strut_10deg", "A-type strut joint, true 10 deg ring, double fin 2x12, 4 M20"),
    "L1-R8-T": (I + r"\v19m\xml_strut_10deg", "A-type strut joint, true 10 deg ring, double fin 2x12, 4 M20"),
    "L2-R8-A": (I + r"\v19m\xml_L2haunch_flush_M20", "r12 haunch detail, ring bottom flush, M20"),
    "L2-R8-B": (I + r"\v19m\xml_L2haunch_flush_M20", "r12 haunch detail, ring bottom flush, M20")}
GRP = {"L1-R8-A": "Level 1 - ring to radial joints, type A", "L1-R8-B": "Level 1 - ring to radial joints, type B",
       "L1-R8-S": "Level 1 - strut joints, type S", "L1-R8-T": "Level 1 - strut joints, type T",
       "L2-R8-A": "Level 2 - haunch joints, type A", "L2-R8-B": "Level 2 - haunch joints, type B"}
BAD = re.compile(r"Claude|Anthropic|\bAI\b|for Wing|\bWing\b", re.I)


def summary(pdf):
    r = PdfReader(pdf); res = {"pages": len(r.pages), "hits": []}
    for i, p in enumerate(r.pages):
        t = p.extract_text() or ""
        for m in BAD.finditer(t):
            res["hits"].append(f"p{i + 1}: ...{t[max(0, m.start() - 40):m.end() + 40]}...".replace("\n", " "))
        if "Summary" in t and "Bolts" in t and "Welds" in t and "Plates" not in res:
            for k in ("Analysis", "Plates", "Bolts", "Welds"):
                m = re.search(k + r"\s+([\d.]+)\s*(?:<\s*[\d.]+)?%?\s*(OK|Not OK)", t)
                if m: res[k] = float(m[1]); res[k + "_st"] = m[2]
        mm = re.search(r"Author\s+(.*)", t)
        if mm and "author" not in res: res["author"] = mm[1].strip()
    return res


order = lambda j: (list(GRP).index(j[:7]), int(j[-3:]))
joints = sorted({os.path.splitext(os.path.basename(f))[0] for p, (d, _) in SRC.items() for f in glob.glob(os.path.join(d, p + "_*.ideaCon"))}, key=order)
rows, docs = [], []
for j in joints:
    d, det = SRC[j[:7]]; pdf = os.path.join(PDFS, j + ".pdf")
    s = summary(pdf) if os.path.exists(pdf) else {}
    ok = bool(s) and all(s.get(k + "_st") == "OK" for k in ("Analysis", "Plates", "Bolts", "Welds")) and s.get("Analysis") == 100.0
    lev = "Level 1" if j.startswith("L1") else "Level 2"
    rows.append(dict(joint=j, location=f"{lev}, radius 8.5 m, {int(j[-3:])}\u00b0", detail=det,
                     calculated_ideaCon=os.path.join(d, j + ".ideaCon"), stamped_copy=os.path.join(PROJ, j + ".ideaCon"),
                     forces="v19m (26016_check_v19m, 13.11.2026), 43 ULS STR combinations", report_pdf=f"reports_v19m/{j}.pdf" if s else "MISSING",
                     report_author=s.get("author", ""), report_pages=s.get("pages", ""), plates_strain_pct=s.get("Plates", ""),
                     bolts_pct=s.get("Bolts", ""), welds_pct=s.get("Welds", ""), status="PASS" if ok else ("FAIL" if s else "MISSING"),
                     above_90pct="YES" if s and max(s.get("Bolts", 0), s.get("Welds", 0)) >= 90 else "",
                     text_hits="; ".join(s.get("hits", [])[:3]), included="yes" if s else "no"))
    if s: docs.append((j, pdf, s["pages"]))
NOT = [("L2-R12-E1_000", I + r"\v14\xml_E1\L2-R12-E1_000.ideaCon", "only a v14 run (20.10.2026), welds 100.6 % FAIL; r 12 haunch donor joint, not rerun: NOT included"),
       ("first appendix (v15 forces for struts and Level 2)", A + r"\26016_IDEA_StatiCa_all_joints.pdf", "kept, superseded by this file")]
for j, p, why in NOT:
    rows.append(dict(joint=j, calculated_ideaCon=p, detail=why, status="not included", included="no"))
cols = list(dict.fromkeys(k for r in rows for k in r))
with open(os.path.join(A, "inventory.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols, restval=""); w.writeheader(); w.writerows(rows)
inc = [r for r in rows if r.get("included") == "yes"]
allpass = all(r["status"] == "PASS" for r in inc) and len(inc) == 36


def build_index(n_idx):
    start, pg = {}, n_idx + 1
    for j, _, n in docs: start[j] = pg; pg += n
    pdf = FPDF("P", "mm", "A4"); pdf.set_margins(15, 15, 15); pdf.set_auto_page_break(True, 15)
    pdf.add_page(); pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, "IDEA StatiCa Connection Reports", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, "26016 Concourse Viewing Platform        Date: 13.11.2026", new_x="LMARGIN", new_y="NEXT"); pdf.ln(2)
    if allpass:
        pdf.multi_cell(0, 4.6, "The steel connections at radius 8.5 m were verified with IDEA StatiCa Connection 26.0 (CBFEM) for the "
                       "ULS combinations of this report and were found to be satisfactory.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    W = [30, 52, 30, 18, 18, 16, 16]
    pdf.set_font("Helvetica", "B", 8)
    for h, x in zip(["Joint", "Location", "Plates (strain %, limit 5)", "Bolts %", "Welds %", "Status", "Page"], W):
        pdf.cell(x, 6, h, border=1, align="C")
    pdf.ln(); pdf.set_font("Helvetica", "", 8)
    for r in inc:
        for v, x in zip([r["joint"], r["location"], f"{r['plates_strain_pct']:.1f}", f"{r['bolts_pct']:.1f}", f"{r['welds_pct']:.1f}",
                         "OK" if r["status"] == "PASS" else "NOT OK", str(start[r["joint"]])], W):
            pdf.cell(x, 4.8, v, border=1, align="L" if x in (30, 52) else "C")
        pdf.ln()
    return PdfReader(io.BytesIO(bytes(pdf.output()))), start


ip, start = build_index(1)
if len(ip.pages) != 1: ip, start = build_index(len(ip.pages))
wr = PdfWriter()
for p in ip.pages: wr.add_page(p)
wr.add_outline_item("Index", 0); parents = {}
for j, path, n in docs:
    first = len(wr.pages)
    for p in PdfReader(path).pages: wr.add_page(p)
    g = GRP[j[:7]]
    if g not in parents: parents[g] = wr.add_outline_item(g, first)
    wr.add_outline_item(j, first, parent=parents[g]); assert first + 1 == start[j]
wr.add_metadata({"/Title": "26016 Concourse Viewing Platform - IDEA StatiCa Connection Reports", "/Author": "CaSE"})
if hasattr(wr, "compress_identical_objects"): wr.compress_identical_objects()
out = os.path.join(A, "26016_IDEA_StatiCa_all_joints_v19m.pdf")
with open(out, "wb") as f: wr.write(f)
txt = " ".join((p.extract_text() or "") for p in PdfReader(out).pages[:1])
print(out, len(wr.pages), "pages", round(os.path.getsize(out) / 1e6, 1), "MB; index hits:", BAD.findall(txt))
print("included", len(inc), "missing", [r["joint"] for r in inc if r["status"] == "MISSING"], "fail", [r["joint"] for r in inc if r["status"] != "PASS"],
      ">=90", [(r["joint"], r["welds_pct"]) for r in inc if r["above_90pct"]], "authors", sorted({r["report_author"] for r in inc}))
for r in inc:
    if r["text_hits"]: print("TEXT", r["joint"], r["text_hits"])
