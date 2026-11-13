"""Post-process the WinGRAF PNGs (thicken 1 px lines, name them), write the standalone A4 PDF
(cover + summary tables + one picture per page with a caption line). Run after the WinGRAF run.
py -3.11 finalize.py"""
import json, os, glob, datetime
from PIL import Image, ImageFilter
from fpdf import FPDF

HERE = os.path.dirname(os.path.abspath(__file__)); E = os.path.dirname(HERE)
PICS = json.load(open(os.path.join(E, "pictures.json")))
TAB = json.load(open(os.path.join(E, "env_table_ULS.json")))
SAN = json.load(open(os.path.join(E, "sanity_check.json")))
OUTP = os.path.join(E, "png"); os.makedirs(OUTP, exist_ok=True)
U = {"N": "kN", "VY": "kN", "VZ": "kN", "MT": "kNm", "MY": "kNm", "MZ": "kNm"}
K = {"N": "N", "VY": "Vy", "VZ": "Vz", "MT": "Mt", "MY": "My", "MZ": "Mz"}

src = sorted(glob.glob(os.path.join(E, "wing_img", "img_*.png")), key=lambda f: int(f.rsplit("_", 1)[1].split(".")[0]))
assert len(src) == len(PICS) + 1, (len(src), len(PICS))
items = [dict(file="P00_key_beam_groups.png", caption="Key: beam groups of model v20 (group number on each member, colour legend at top). "
              "Groups 1, 2, 6, 7 are shell (QUAD) groups and are not shown.")]
for i, p in enumerate(PICS, 1):
    q = p["q"]; lmax, lmin = p["lcs"]
    items.append(dict(file=f"P{i:02d}_{p['name']}.png", p=p, caption=(
        f"{K[q]} [{U[q]}], ULS envelope: max LC {lmax} (red) and min LC {lmin} (blue) over the 43 ULS STR combinations "
        f"101-130, 135, 141-148, 151-154. {p['title']}. Diagram scale 1 cm = {p['unit']:g} {U[q]} (on the 25.5 cm sheet); "
        f"labels only where |value| > {p['thr']:g} {U[q]}. Envelope extremes: max {p['max']:g}, min {p['min']:g} {U[q]}.")))
for s, it in zip(src, items):
    im = Image.open(s).convert("RGB")
    im = im.filter(ImageFilter.MinFilter(3))          # dark/coloured lines 1 px -> 3 px (about 0.2 mm at 170 mm print width)
    im.save(os.path.join(OUTP, it["file"]), dpi=(300, 300), optimize=True)
    it["size"] = im.size
json.dump([{k: v for k, v in it.items() if k != "p"} | ({"picture": it["p"]} if "p" in it else {}) for it in items],
          open(os.path.join(E, "pictures_final.json"), "w"), indent=1)

# ------------------------------------------------------------------ PDF
class P(FPDF):
    def footer(self):
        self.set_y(-10); self.set_font("Helvetica", "", 7)
        self.cell(0, 5, f"26016 Concourse viewing platform - model v20 - ULS member force envelopes - page {self.page_no()}", align="C")

pdf = P("P", "mm", "A4"); pdf.set_auto_page_break(True, 14); pdf.set_margins(15, 12, 15)
pdf.add_page(); pdf.set_font("Helvetica", "B", 14)
pdf.multi_cell(0, 7, "26016 Concourse viewing platform\nModel v20 - ULS member force envelopes (SOFiSTiK WinGRAF)")
pdf.ln(2); pdf.set_font("Helvetica", "", 9)
txt = [
    f"Prepared {datetime.date.today():%d %b %Y} from 26016_check_v20 (v19m + qp 0.5 kPa for all wind + My hinges at 12 external stair stringer ends), read from a copy of the database.",
    "Envelope: the model's own MAXIMA superposition COMB 3 (EXTR NONL, TYPE DESI, BASE 4300): each of the 43 ULS STR combinations "
    "101-130, 135, 141-148, 151-154 enters as an exclusive alternative (TYPE AG1, factor 1.00), so every envelope value is the value of "
    "one complete combination. EQU combinations 131-134 are not included. The combinations are linear (ASE SYST PROB LINE) COPY combinations.",
    "Beam envelope load cases: N 4321/4322, Vy 4323/4324, Vz 4325/4326, Mt 4327/4328, My 4329/4330, Mz 4331/4332 (max/min). "
    "SLS characteristic 201-221: 4421-4432 (same order).",
    "Check: at every result station of every beam the MAXIMA value equals the largest / smallest value read from the 43 combinations "
    f"(largest difference over all stations: N {SAN['ULS_worst_station_diff']['N']:.1e}, My {SAN['ULS_worst_station_diff']['My']:.1e} kNm).",
    "Sign convention: SOFiSTiK local beam axes, N > 0 tension, My about the local y (strong) axis, Mz about the local z (weak) axis. "
    "Red = max load case, blue = min load case. Units kN, kNm.",
    "Floor framing is drawn in a steep isometric view because My, Vz act in the vertical plane and cannot be read in a true top view "
    "(tested: diagrams rotated into the plan flip side with the member direction). Mz of Level 1 is drawn in a true plan view (X right, Y up).",
    "Kingpost / central mast: modelled with shell elements (QUAD), no beam group, so no beam N / My diagram is given here."]
for t in txt:
    pdf.multi_cell(0, 4.6, t); pdf.ln(1.2)

def table(title, comps):
    pdf.add_page("L"); pdf.set_font("Helvetica", "B", 11); pdf.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 7)
    pdf.multi_cell(0, 3.6, "Each cell: envelope value, governing combination (LC), beam element and x [m from beam start]. "
                   "Full data incl. SLN: env_table_ULS.csv / .json.")
    w = [12, 62] + [33.5] * (2 * len(comps))
    pdf.set_font("Helvetica", "B", 7)
    hdr = ["Group", "Description / section"] + [f"{K[c]} {m} [{U[c]}]" for c in comps for m in ("max", "min")]
    for h, x in zip(hdr, w): pdf.cell(x, 5, h, border=1, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", "", 6.5)
    for g in TAB["groups"]:
        import re as _re; sec = _re.sub(r"\s*\((EN|BS)[^)]*\)", "", g["sections"]).replace(" x ", "x").replace("SHS 100x100x5 stair landing posts", "SHS 100x100x5"); cells = [str(g["group"]), g["description"][:44]]
        sub = ["", sec[:52]]
        for c in comps:
            k = K[c]
            for m in ("max", "min"):
                cells.append(f"{g[f'{k}_{m}']:.1f}  (LC {g[f'{k}_{m}_lc']})")
                sub.append(f"b {g[f'{k}_{m}_beam']} x {g[f'{k}_{m}_x']:.2f}")
        for t, x in zip(cells, w): pdf.cell(x, 4, t, border="LTR")
        pdf.ln()
        for t, x in zip(sub, w): pdf.cell(x, 3.6, t, border="LBR")
        pdf.ln()

table("ULS envelope per member group - forces N, Vy, Vz", ("N", "VY", "VZ"))
table("ULS envelope per member group - moments Mt, My, Mz", ("MT", "MY", "MZ"))

for it in items:
    pdf.add_page("P")
    w, h = it["size"]; wmm = 170; hmm = wmm * h / w
    if hmm > 240: hmm = 240; wmm = hmm * w / h
    pdf.image(os.path.join(OUTP, it["file"]), x=(210 - wmm) / 2, y=14, w=wmm, h=hmm)
    pdf.set_y(14 + hmm + 3); pdf.set_font("Helvetica", "B", 8); pdf.cell(0, 4, it["file"][:-4], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8); pdf.multi_cell(0, 4, it["caption"])
out = os.path.join(E, "26016_v20_ULS_envelopes.pdf"); pdf.output(out)
print("pdf", out, os.path.getsize(out) // 1024, "kB", pdf.page_no(), "pages")

