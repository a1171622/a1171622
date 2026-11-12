import re, json, sys
E = r"C:\Sofistik workflow\26016-member-check\v19\26016_check_v19.erg"
L = open(E, encoding="latin-1").read().splitlines()
# BDK summaries
bdk = {}; state = None; nblk = 0
for i, l in enumerate(L):
    if "Summary of the Results" in l: state = "sum"; nblk += 1; continue
    if state == "sum":
        m = re.match(r"\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\S.*)$", l)
        if m:
            g = m.groups(); u = max(float(g[7]), float(g[8]))
            rec = dict(id=int(g[0]), lc=int(g[1]), n_y=float(g[3]), n_z=float(g[4]), m_y=float(g[5]), m_z=float(g[6]), nm_y=float(g[7]), nm_z=float(g[8]), util=u, check=g[9].strip(), bdk_block=nblk, erg_line=i+1)
            if rec["id"] in bdk: print("dup", rec["id"], bdk[rec["id"]]["util"], u, file=sys.stderr)
            if rec["id"] not in bdk or u > bdk[rec["id"]]["util"]: bdk[rec["id"]] = rec
        elif re.search(r"PROG|END|Program|Statistic", l) and "BDK" not in l and "Tors" not in l: pass
# AQB station table (only inside the "Utilisation Level" tables)
aqb = {}; inT = False; beam = None; x = sno = None
rA = re.compile(r"^\s+(\d{4,7})\s+(\d+\.\d+)\s+(\d+)\s+(max|\d+)\s+(.*)$")
rB = re.compile(r"^\s{8,22}(\d+\.\d+)\s+(\d+)\s+(max|\d+)\s+(.*)$")
rC = re.compile(r"^\s{24,}(max|\d{3})\s+(-?\d.*)$")
def num(t):
    try: return float(t)
    except ValueError: return None
for i, l in enumerate(L):
    s_ = l.strip()
    if s_.startswith("Maximum Utilisation Level"): break
    if s_.startswith("Utilisation Level"): inT = True; continue
    if s_.startswith("Plate Slenderness"): inT = False; continue
    if not inT: continue
    tok = None
    m = rA.match(l)
    if m: beam, x, sno, tok, rest = int(m[1]), float(m[2]), int(m[3]), m[4], m[5]
    else:
        m = rB.match(l)
        if m: x, sno, tok, rest = float(m[1]), int(m[2]), m[3], m[4]
        else:
            m = rC.match(l)
            if m: tok, rest = m[1], m[2]
    if tok != "max" or beam is None: continue
    l1 = rest.split(); l2 = L[i+1].split() if i+1 < len(L) else []; l3 = L[i+2].split() if i+2 < len(L) else []
    l3raw = L[i+2] if i+2 < len(L) else ""
    three = len(l3) >= 10 and num(l3[0]) is not None and l3raw.startswith(" "*20) and not (rA.match(l3raw) or rB.match(l3raw) or rC.match(l3raw))
    sv = num(l1[-1]); tl = num(l2[-1]) if l2 else None
    ti = num(l3[-1]) if three else None
    lc = int(l3[1]) if three and l3[1].isdigit() else None
    if ti is not None and (ti > 0 or (tl or 0) > 0): u = ti
    else: u = sv
    aqb.setdefault(beam, []).append(dict(util=u, x=x, sno=sno, sig_v=sv, tot_lin=tl, tot_int=ti, lc=lc, line=i+1))
json.dump({"bdk": bdk, "aqb": aqb}, open("erg_parsed.json", "w"))
print(len(bdk), "bdk ids;", len(aqb), "aqb beams; blocks", nblk)
print(bdk.get(722), bdk.get(56))
print(aqb.get(60001)[:2])
