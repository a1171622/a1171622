"""26016 v19m export: JSON extracts from 26016_check_v19.cdb (read only) and the .erg tables (parsed by erg.py).
Run:  py -3 extract_v19.py <out_folder>
Reads the .cdb through the SOFiSTiK MCP server's own read-only reader (sofistik_mcp.results / cdbio)."""
import sys, os, re, json, math, bisect, datetime
import numpy as np
from cdbx import open_cdb, R, CDB

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
DAT = r"C:\Sofistik workflow\26016-member-check\v19m\26016_check_v19m.dat"
ERG = json.load(open(os.path.join(HERE, "erg_parsed.json")))
BDK = {int(k): v for k, v in ERG["bdk"].items()}
AQB = {int(k): v for k, v in ERG["aqb"].items()}

SRC = {"model": "26016 member check v19m (v19 + MZ released at 18 L1 r 8.5 ring ends, run 13 Nov 2026, NguyenPC, exit 0, 0 errors, 284 warnings)",
       "cdb": CDB, "erg": CDB.replace(".cdb", ".erg"),
       "extracted": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
       "reader": "SOFiSTiK MCP server read-only CDB reader (sof_cdb_w DLL), .erg tables parsed by erg.py",
       "units": "forces kN, moments kNm, displacements mm, coordinates m"}
SIGN_SUP = ("Support forces as stored by SOFiSTiK = force of the support on the structure in global axes: "
            "pz > 0 = support pushes the structure up (bearing / compression on the foundation), pz < 0 = uplift (tension in the anchors).")

def dump(name, obj):
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, indent=1)
    print("wrote", name)

cdb, d = open_cdb()
LCS = {l["lc"]: l for l in R.load_cases(cdb, d)}
def have(lc): return lc in LCS and "nodes" in (LCS[lc].get("has_results") or [])
ULS = [lc for lc in range(101, 155) if have(lc)]
STR = [lc for lc in ULS if lc not in (131, 132, 133, 134)]
SLS = [lc for lc in range(201, 222) if have(lc)]
EQU = [131, 132, 133, 134]
BASIC = [1, 2, 3, 4, 11, 12, 13, 14, 71, 72, 73, 74]
title = lambda lc: LCS[lc]["title"]

# ---------------- model: nodes, beams, groups, SLN parents ----------------
xyz = {k: v for k, v in R._node_coords(cdb, d).items()}
beams = R._beam_index(cdb, d)
G = sorted({(g["min_element"], g["group"]) for g in R.groups(cdb, d) if g["min_element"] > 0})
starts = [s for s, _ in G]
def egroup(nr): return G[bisect.bisect_right(starts, nr) - 1][1]

lines = open(DAT, encoding="latin-1").read().splitlines()
sln_def = {}; cur = None
for l in lines:
    m = re.match(r"SLN\s+(\d+)\s", l)
    if m:
        cur = int(m[1]); g = re.search(r"GRP\s+(\d+)", l); s = re.search(r"SNO\s+(\d+)", l); t = re.search(r'TITL\s+"([^"]*)"', l)
        sln_def[cur] = dict(grp=int(g[1]) if g else None, sno=int(s[1]) if s else None, title=t[1] if t else "", segs=[]); continue
    if l.startswith("SLNB") and cur is not None:
        m = re.search(r"X1\s+(\S+)\s+(\S+)\s+(\S+)\s+X2\s+(\S+)\s+(\S+)\s+(\S+)", l)
        if m:
            a = list(map(float, m.groups())); sln_def[cur]["segs"].append((np.array(a[:3]), np.array(a[3:])))
    elif l.startswith(("SPT", "SAR", "END", "GRP", "$")) and not l.startswith("SLNB"):
        cur = None if not l.startswith("$") else cur

def on_seg(p, a, b, tol=0.01):
    ab = b - a; t = np.dot(p - a, ab) / np.dot(ab, ab)
    return -1e-3 <= t <= 1 + 1e-3 and np.linalg.norm(a + t * ab - p) < tol

def parent_sln(bnr):
    """Wing's SLN of a beam: its own m_nref when that SLN is in the input, else the input SLN whose line holds both end nodes."""
    b = beams[bnr]; s = b["sln"]
    if s in sln_def and sln_def[s]["segs"]: return s
    p1, p2 = np.array(xyz[b["nodes"][0]]), np.array(xyz[b["nodes"][1]])
    g = egroup(bnr)
    for k, v in sln_def.items():
        if v["grp"] != g: continue
        for a, c in v["segs"]:
            if on_seg(p1, a, c) and on_seg(p2, a, c): return k
    return s

def beams_of_group(g): return sorted(b for b in beams if egroup(b) == g)
B62 = beams_of_group(62); B25 = beams_of_group(25)
par = {b: parent_sln(b) for b in B62 + B25}
sln_beams = {}
for b in B62 + B25: sln_beams.setdefault(par[b], []).append(b)
unmapped = sorted({par[b] for b in B62 if par[b] not in sln_def})
print("group 62 SLN:", len([s for s in sln_beams if egroup(sln_beams[s][0]) == 62]), "unmapped", unmapped)

def chain(bl):
    """beams of one SLN in order from its start, with the cumulative distance of each beam start."""
    bl = list(bl); nodes = {}
    for b in bl:
        for n in beams[b]["nodes"]: nodes[n] = nodes.get(n, 0) + 1
    ends = [n for n, c in nodes.items() if c == 1]
    first = min(ends) if ends else beams[bl[0]]["nodes"][0]
    out = []; n = first; left = set(bl); s = 0.0
    while left:
        nxt = [b for b in left if n in beams[b]["nodes"]]
        if not nxt: break
        b = nxt[0]; left.discard(b)
        a, c = beams[b]["nodes"]; flip = (c == n)
        L = float(np.linalg.norm(np.array(xyz[c]) - np.array(xyz[a])))
        out.append(dict(beam=b, start=s, L=L, flip=flip, n0=n, n1=(a if flip else c)))
        s += L; n = a if flip else c
    return out

def aqb_of(bl):
    best = None
    for b in bl:
        for r in AQB.get(b, []):
            if r["util"] is not None and (best is None or r["util"] > best["util"]):
                best = dict(r, beam=b)
    return best

def bdk_of(s):
    r = BDK.get(s)
    return None if r is None else dict(util=r["util"], lc=r["lc"], check=r["check"], n_y=r["n_y"], n_z=r["n_z"], m_y=r["m_y"], m_z=r["m_z"], nm_y=r["nm_y"], nm_z=r["nm_z"])

SECT = {s["nr"]: s["title"] for s in R.sections(cdb, d)}

# ---------------- per LC reads ----------------
node_cache = {}
def nodes_lc(lc):
    if lc not in node_cache:
        node_cache[lc] = {r["node"]: r for r in R._node_rows(cdb, d, lc, None)}
    return node_cache[lc]
sup_cache = {}
def sup_lc(lc):
    if lc not in sup_cache:
        r = R.support_reactions(cdb, d, lc, max_rows=100000)
        sup_cache[lc] = r
    return sup_cache[lc]

# support nodes and labels
SUPN = [r["node"] for r in sup_lc(201)["rows"]]
def sup_label(n):
    if 901 <= n <= 916: return "external stair base (SPT %d)" % n
    if 5807 <= n <= 5824: return "kingpost base line"
    if n in (1001, 1002): return "SPT %d" % n
    if 2 <= n <= 34: return "column base (SPT %d)" % n
    return ""
# stair SPT labels from the input titles
spt_t = {}
for l in lines:
    m = re.match(r"SPT\s+(\d+)\s.*TITL\s+\"([^\"]*)\"", l)
    if m: spt_t[int(m[1])] = m[2]
def sup_info(n):
    x = xyz.get(n, (None,) * 3)
    lab = sup_label(n)
    if n in spt_t and spt_t[n] != "Point": lab = (lab + ": " if lab else "") + spt_t[n]
    return dict(node=n, x=x[0], y=x[1], z=x[2], location=lab)

COMP = ("px", "py", "pz", "mx", "my", "mz")
def sup_envelope(lcs):
    env = {}
    for lc in lcs:
        for r in sup_lc(lc)["rows"]:
            e = env.setdefault(r["node"], {})
            for c in COMP:
                v = r[c]
                if v is None: continue
                if c + "_max" not in e or v > e[c + "_max"]: e[c + "_max"] = v; e[c + "_max_lc"] = lc
                if c + "_min" not in e or v < e[c + "_min"]: e[c + "_min"] = v; e[c + "_min_lc"] = lc
    out = []
    for n in sorted(env):
        e = env[n]
        if all(abs(e.get(c + "_max", 0)) < 1e-9 and abs(e.get(c + "_min", 0)) < 1e-9 for c in ("mx", "my", "mz")):
            for c in ("mx", "my", "mz"):
                for k in ("_max", "_min", "_max_lc", "_min_lc"): e.pop(c + k, None)
        out.append(dict(sup_info(n), **e))
    return out

def sums(lc):
    r = sup_lc(lc)
    return dict(lc=lc, title=title(lc), sum_Fx=round(r["sum_kN"]["px"], 3), sum_Fy=round(r["sum_kN"]["py"], 3), sum_Fz=round(r["sum_kN"]["pz"], 3),
                sofistik_stored_sum_kN=[round(v, 3) for v in LCS[lc]["sum_reactions_kN"]], supports=r["supports_with_reaction"])

# ---------------- 1. support envelopes, EQU, basic sums ----------------
dump("env_support_SLS.json", dict(source=SRC, sign=SIGN_SUP, what="Envelope (min / max with governing combination) of the support forces at every support node over the SLS combinations",
                                  load_cases=SLS, load_case_titles={lc: title(lc) for lc in SLS}, supports=sup_envelope(SLS)))
dump("env_support_ULS.json", dict(source=SRC, sign=SIGN_SUP, what="Envelope (min / max with governing combination) of the support forces at every support node over all ULS combinations 101 to 154 (STR and EQU 131 to 134, as BDK / AQB)",
                                  load_cases=ULS, str_only_load_cases=STR, load_case_titles={lc: title(lc) for lc in ULS}, supports=sup_envelope(ULS)))
eq = []
for lc in EQU:
    rows = [dict(sup_info(r["node"]), px=r["px"], py=r["py"], pz=r["pz"]) for r in sup_lc(lc)["rows"]]
    upl = sorted([r for r in rows if r["pz"] < 0], key=lambda r: r["pz"])
    eq.append(dict(sums(lc), max_uplift=dict(node=upl[0]["node"], pz=upl[0]["pz"]) if upl else None, uplift_nodes=[r["node"] for r in upl], reactions=rows))
dump("reactions_EQU.json", dict(source=SRC, sign=SIGN_SUP, what="Support forces at every support node (columns, kingpost base line 5807 to 5824, external stair bases 901 to 916) for EQU 0.9G + 1.5W, combinations 131 to 134",
                                combinations=eq))
bs = [sums(lc) for lc in BASIC]
dump("reactions_basic_sums.json", dict(source=SRC, sign=SIGN_SUP, what="Sum of the support forces of all supports for the basic load cases (unfactored). Check: equals the sum stored by SOFiSTiK and the applied load.",
                                       load_cases=bs))

# ---------------- 2. node envelopes SLS per level ----------------
LEVELS = {"L1": (15, "Level 1 framing (group 15, z 4.05)"), "L2": (25, "Level 2 framing (group 25, z 8.05)"), "RF": (35, "Roof framing (group 35, z 12.06)")}
for key, (g, txt) in LEVELS.items():
    ns = sorted({n for b in beams_of_group(g) for n in beams[b]["nodes"]})
    env = {n: {} for n in ns}
    for lc in SLS:
        rows = nodes_lc(lc)
        for n in ns:
            r = rows.get(n); e = env[n]
            if r is None: continue
            uh = math.hypot(r["ux"], r["uy"])
            for c, v in (("ux", r["ux"]), ("uy", r["uy"]), ("uz", r["uz"]), ("uxy", uh)):
                if c + "_max" not in e or v > e[c + "_max"]: e[c + "_max"] = v; e[c + "_max_lc"] = lc
                if c != "uxy" and (c + "_min" not in e or v < e[c + "_min"]): e[c + "_min"] = v; e[c + "_min_lc"] = lc
    nodes_out = [dict(node=n, x=xyz[n][0], y=xyz[n][1], z=xyz[n][2], **env[n]) for n in ns]
    lo = min(nodes_out, key=lambda r: r["uz_min"]); hi = max(nodes_out, key=lambda r: r["uz_max"]); hz = max(nodes_out, key=lambda r: r["uxy_max"])
    in201 = nodes_lc(201); lo201 = min(ns, key=lambda n: in201[n]["uz"])
    dump("env_node_SLS_%s.json" % key, dict(source=SRC, what="SLS envelope of node displacements of the %s nodes (all nodes of the beams of that group), absolute (not relative to the supports)" % txt,
        sign="global axes, uz < 0 = downward", load_cases=SLS,
        summary=dict(uz_min=dict(value=lo["uz_min"], node=lo["node"], lc=lo["uz_min_lc"], xyz=[lo["x"], lo["y"], lo["z"]]),
                     uz_max=dict(value=hi["uz_max"], node=hi["node"], lc=hi["uz_max_lc"], xyz=[hi["x"], hi["y"], hi["z"]]),
                     uxy_max=dict(value=round(hz["uxy_max"], 4), node=hz["node"], lc=hz["uxy_max_lc"], xyz=[hz["x"], hz["y"], hz["z"]]),
                     uz_min_lc201=dict(value=in201[lo201]["uz"], node=lo201, xyz=list(xyz[lo201]))),
        nodes=nodes_out))

# ---------------- 3. external stair ----------------
def forces(lc, bl):
    r = R.beam_forces(cdb, d, lc, beams=",".join(map(str, bl)), max_rows=100000)
    return r["rows"]

def member_kind(t):
    t = t.lower()
    for k, w in (("tread", "tread"), ("seat", "stringer seat"), ("stringer", "stringer"), ("legs beam", "transverse leg beam"), ("leg ", "leg"),
                 ("support on l1 ring", "ring bracket"), ("landing 1", "landing 1 beam"), ("landing 2", "landing 2 beam")):
        if w and k in t: return w
    return "other"

s62 = sorted(s for s in sln_beams if egroup(sln_beams[s][0]) == 62)
members = []
for s in s62:
    bl = sln_beams[s]; df = sln_def.get(s, {})
    a = aqb_of(bl); bk = bdk_of(s)
    members.append(dict(sln=s, title=df.get("title"), kind=member_kind(df.get("title", "")), section=SECT.get(df.get("sno")), sno=df.get("sno"),
                        beams=sorted(bl), length_m=round(sum(beams[b]["length_m"] for b in bl), 3),
                        bdk=bk, aqb=None if a is None else dict(util=a["util"], lc=a["lc"], beam=a["beam"], x=a["x"],
                                                                note=None if a["lc"] is not None else "AQB prints no governing LC for this station (stress envelope only)")))
# governing members: top 5 BDK, top 5 AQB, plus every member >= 0.5
govset = set()
for key in ("bdk", "aqb"):
    srt = sorted([m for m in members if m[key]], key=lambda m: -m[key]["util"])
    govset |= {m["sln"] for m in srt[:5]} | {m["sln"] for m in srt if m[key]["util"] >= 0.5}
for m in members:
    if m["sln"] not in govset: continue
    m["governing_forces"] = {}
    for key in ("bdk", "aqb"):
        if not m[key] or not m[key].get("lc"): continue
        lc = m[key]["lc"]; rows = forces(lc, m["beams"])
        def ext(c, f): r = f(rows, key=lambda r: r[c]); return dict(value=r[c], beam=r["beam"], x=r["x"])
        m["governing_forces"][key + "_lc_%d" % lc] = {c: dict(max=ext(c, max), min=ext(c, min)) for c in ("N", "My", "Mz")}
        if key == "aqb":
            st = [r for r in rows if r["beam"] == m["aqb"]["beam"] and abs(r["x"] - m["aqb"]["x"]) < 0.002]
            if st: m["governing_forces"]["at_aqb_station"] = {c: st[0][c] for c in ("N", "Vy", "Vz", "Mt", "My", "Mz")}

# supports of the stair and brackets
stair_spt = list(range(901, 917))
def sup_rows(lc, ns):
    rr = {r["node"]: r for r in sup_lc(lc)["rows"]}
    return [dict(sup_info(n), px=rr[n]["px"], py=rr[n]["py"], pz=rr[n]["pz"]) if n in rr else dict(sup_info(n), note="no reaction") for n in ns]
envU = {r["node"]: r for r in sup_envelope(ULS)}

BR = [724, 725, 769, 770]
def bracket(lc):
    out = []
    for s in BR:
        b = sln_beams[s][0]; n1, n2 = beams[b]["nodes"]
        p1, p2 = np.array(xyz[n1]), np.array(xyz[n2])
        ring = n1 if p1[2] < p2[2] else n2; land = n2 if ring == n1 else n1
        rows = forces(lc, [b]); r_ring = [r for r in rows if (abs(r["x"]) < 1e-6) == (ring == n1)][0]
        e = (np.array(xyz[land]) - np.array(xyz[ring])); e /= np.linalg.norm(e)    # unit vector ring -> landing
        # force of the bracket on the ring node = N along the bracket axis (N > 0 tension pulls the ring towards the landing, i.e. up)
        F = r_ring["N"] * e
        out.append(dict(sln=s, title=sln_def[s]["title"], beam=b, ring_node=ring, ring_xyz=list(xyz[ring]), landing_node=land,
                        N=r_ring["N"], Vy=r_ring["Vy"], Vz=r_ring["Vz"], My=r_ring["My"], Mz=r_ring["Mz"],
                        force_on_ring_global=dict(px=round(float(F[0]), 4), py=round(float(F[1]), 4), pz=round(float(F[2]), 4)),
                        reaction_on_landing_global=dict(px=round(float(-F[0]), 4), py=round(float(-F[1]), 4), pz=round(float(-F[2]), 4))))
    return out
br_env = {s: {} for s in BR}
for lc in ULS:
    for r in bracket(lc):
        e = br_env[r["sln"]]
        for c in ("N", "Vy", "Vz", "My", "Mz"):
            v = r[c]
            if c + "_max" not in e or v > e[c + "_max"]: e[c + "_max"] = v; e[c + "_max_lc"] = lc
            if c + "_min" not in e or v < e[c + "_min"]: e[c + "_min"] = v; e[c + "_min_lc"] = lc
        for c, v in r["reaction_on_landing_global"].items():
            if c + "_max" not in e or v > e[c + "_max"]: e[c + "_max"] = v; e[c + "_max_lc"] = lc
            if c + "_min" not in e or v < e[c + "_min"]: e[c + "_min"] = v; e[c + "_min_lc"] = lc

# deflections: flights and landings
def nodes_of(slns): return sorted({n for s in slns for b in sln_beams.get(s, []) for n in beams[b]["nodes"]})
PARTS = {}
for side, base in (("right", 0), ("left", 1)):
    T = lambda pat: [m["sln"] for m in members if m["title"].startswith(side) and pat in m["title"]]
    fl = lambda k: [s for s in T("flight " + k) if not sln_def[s]["title"].startswith(side + " landing") and "seat" not in sln_def[s]["title"]]
    PARTS[side + " flight 1"] = fl("1")
    PARTS[side + " flight 2"] = fl("2")
    PARTS[side + " landing 1"] = [s for s in T("landing 1") if "leg" not in sln_def[s]["title"]]
    PARTS[side + " landing 2"] = [s for s in T("landing 2") if "leg" not in sln_def[s]["title"] and "support" not in sln_def[s]["title"]]

def rel_defl(lc, slns):
    """deflection of each member relative to the straight line between its own end nodes (uz)."""
    rows = nodes_lc(lc); best = None
    for s in slns:
        ch = chain(sln_beams[s]);
        if not ch: continue
        n0, n1 = ch[0]["n0"], ch[-1]["n1"]; Ltot = ch[-1]["start"] + ch[-1]["L"]
        for c in ch:
            for n, dist in ((c["n0"], c["start"]), (c["n1"], c["start"] + c["L"])):
                base = rows[n0]["uz"] + (rows[n1]["uz"] - rows[n0]["uz"]) * dist / Ltot
                v = rows[n]["uz"] - base
                if best is None or v < best["value"]:
                    best = dict(value=round(v, 4), node=n, xyz=list(xyz[n]), sln=s, span_m=round(Ltot, 3), span_over=round(Ltot * 1000 / abs(v)) if abs(v) > 1e-6 else None)
    return best

def defl(lcs, ns, comp):
    best = None
    for lc in lcs:
        rows = nodes_lc(lc)
        for n in ns:
            r = rows[n]; v = r["uz"] if comp == "uz" else math.hypot(r["ux"], r["uy"])
            key = v if comp == "uz" else -v
            if best is None or key < best["_k"]:
                best = dict(_k=key, value=round(v, 4), lc=lc, node=n, xyz=list(xyz[n]), ux=r["ux"], uy=r["uy"], uz=r["uz"])
    best.pop("_k"); return best
WIND_SLS = [lc for lc in SLS if lc != 201]
defl_out = {}
for part, sl in PARTS.items():
    ns = nodes_of(sl)
    defl_out[part] = dict(slns=sl, nodes=len(ns), uz_min_lc201=defl([201], ns, "uz"), uz_min_SLS_envelope=defl(SLS, ns, "uz"),
                          relative_uz_lc201=rel_defl(201, sl))
# horizontal movement of landing 1 and landing 2 (each arm), SLS 201 and the worst SLS wind combination
sway = {}
for part in [p for p in PARTS if "landing" in p]:
    ns = nodes_of(PARTS[part])
    worst = defl(WIND_SLS, ns, "uxy")
    sway[part] = dict(lc201=defl([201], ns, "uxy"), worst_wind_SLS=worst, worst_wind_lc_title=title(worst["lc"]),
                      height_m=round(float(np.mean([xyz[n][2] for n in ns])), 3))

stair = dict(source=SRC, what="External stair ground to L1 (group 62): members, supports, ring brackets, SLS deflections",
             notes=["BDK = EN 1993-1-1 6.3 member check (BDK summary table, util = max(nm-y, nm-z)); legs with Lcr = 2 L (SKY = SKZ = 2.0) as run in v19.",
                    "AQB = cross-section check EN 1993-1-1 6.2 (util = 'Tot-int' plastic interaction where printed, else the elastic von Mises ratio, as the AQB 'Total' line).",
                    "Treads (5 mm plate, section 7) are AQB only; AQB prints a stress envelope for them without a governing LC.",
                    "Beam forces in local beam axes, SOFiSTiK sign convention (N > 0 tension).",
                    "Split structural lines (SOFiMSHC 16xx / 17xx) are mapped back to the input SLN by geometry.",
                    "Ring brackets: released VY VZ MT MY MZ at the ring, so they pass only N. force_on_ring_global = N times the unit vector ring -> landing; reaction_on_landing_global is the opposite (the support force of the ring on the stair, same sign rule as the supports).",
                    "Deflections absolute in global axes (uz < 0 down); relative_uz = deflection relative to the line between the member's own end nodes, worst member of that part.",
                    SIGN_SUP],
             load_case_titles={lc: title(lc) for lc in [102, 201] + WIND_SLS},
             members=members,
             supports=dict(lc102=sup_rows(102, stair_spt), lc201=sup_rows(201, stair_spt),
                           ULS_envelope={n: {k: v for k, v in envU[n].items() if k[:2] in ("px", "py", "pz")} for n in stair_spt if n in envU},
                           ULS_load_cases=ULS),
             ring_brackets=dict(lc102=bracket(102), lc201=bracket(201), ULS_envelope=br_env),
             deflection=defl_out, landing_horizontal_movement=sway)
dump("stair_ext.json", stair)

# ---------------- 4. L2 outer ring r 12 ----------------
ring = []
for s in range(55, 73):
    bk = bdk_of(s); a = aqb_of(sln_beams[s])
    ring.append(dict(sln=s, title=sln_def[s]["title"], bdk=bk, aqb=None if a is None else dict(util=a["util"], lc=a["lc"], beam=a["beam"], x=a["x"])))
top = sorted([r for r in ring if r["bdk"]], key=lambda r: -r["bdk"]["util"])[:3]

def hermite(x0, x1, y0, y1, m0, m1, x):
    h = x1 - x0; t = (x - x0) / h
    return ((2*t**3 - 3*t**2 + 1) * y0 + (t**3 - 2*t**2 + t) * h * m0 + (-2*t**3 + 3*t**2) * y1 + (t**3 - t**2) * h * m1)

for r in top:
    s = r["sln"]; lc = r["bdk"]["lc"]; ch = chain(sln_beams[s]); Ltot = ch[-1]["start"] + ch[-1]["L"]
    rows = forces(lc, sln_beams[s]); byb = {}
    for q in rows: byb.setdefault(q["beam"], []).append(q)
    # stations along the SLN from its first node: (s, forces); a flipped beam keeps local values (local axis reversed: dMy/ds = -Vz)
    st = []
    for c in ch:
        for q in sorted(byb[c["beam"]], key=lambda q: q["x"]):
            sdist = c["start"] + (c["L"] - q["x"] if c["flip"] else q["x"])
            st.append(dict(q, s=sdist, sgn=-1 if c["flip"] else 1))
    st.sort(key=lambda q: q["s"])
    e0, e1 = st[0], st[-1]
    node_end, far = (e0, e1) if abs(e0["My"]) >= abs(e1["My"]) else (e1, e0)
    target = 0.3 if node_end is e0 else Ltot - 0.3
    seg = [q for q in st if (q["s"] <= target if node_end is e0 else q["s"] >= target)]
    lo = max([q for q in st if q["s"] <= target], key=lambda q: q["s"]); hi = min([q for q in st if q["s"] >= target], key=lambda q: q["s"])
    # dMy/dx = Vz in the beam's own axis; along s the slope is sgn * Vz
    my300 = hermite(lo["s"], hi["s"], lo["My"], hi["My"], lo["sgn"] * lo["Vz"], hi["sgn"] * hi["Vz"], target) if hi["s"] > lo["s"] else lo["My"]
    nn = ch[0]["n0"] if node_end is e0 else ch[-1]["n1"]; fn = ch[-1]["n1"] if node_end is e0 else ch[0]["n0"]
    r["governing_lc"] = lc; r["governing_lc_title"] = title(lc); r["length_m"] = round(Ltot, 3)
    r["node_end"] = dict(node=nn, xyz=list(xyz[nn]), N=node_end["N"], Vz=node_end["Vz"], My=node_end["My"], Mz=node_end["Mz"], Vy=node_end["Vy"], Mt=node_end["Mt"])
    r["My_at_300mm_from_node"] = dict(value=round(my300, 3), interpolation="cubic Hermite between the stations %.3f and %.3f m (slopes from Vz)" % (lo["s"], hi["s"]),
                                      linear_check=round(lo["My"] + (hi["My"] - lo["My"]) * (target - lo["s"]) / (hi["s"] - lo["s"]), 3) if hi["s"] > lo["s"] else lo["My"])
    r["other_end"] = dict(node=fn, xyz=list(xyz[fn]), N=far["N"], Vz=far["Vz"], My=far["My"], Mz=far["Mz"])
dump("ring_L2.json", dict(source=SRC, what="Level 2 outer ring r 12 (group 25, SLN 55 to 72): BDK / AQB per SLN; for the three highest BDK members the forces at the node end for the governing LC",
                          notes=["Node end = the end with the larger |My| in the governing LC. Local beam axes, SOFiSTiK signs (N > 0 tension; My as stored, the same sign the BDK / AQB checks use).",
                                 "My at 300 mm from the node: face of the strengthening as Wing decided for 26016."],
                          members=ring, top3=[r["sln"] for r in top]))

# ---------------- 5. summary for the report back ----------------
grp_sum = {}
for s, r in BDK.items():
    g = sln_def.get(s, {}).get("grp")
    if g is None:
        bl = [b for b in beams if beams[b]["sln"] == s]; g = egroup(bl[0]) if bl else None
    e = grp_sum.setdefault(g, dict(bdk_max=0));
    if r["util"] > e["bdk_max"]: e.update(bdk_max=r["util"], bdk_sln=s, bdk_lc=r["lc"])
for b, rs in AQB.items():
    g = egroup(b); e = grp_sum.setdefault(g, dict(bdk_max=0))
    for q in rs:
        if q["util"] is not None and q["util"] > e.get("aqb_max", 0):
            e.update(aqb_max=q["util"], aqb_beam=b, aqb_lc=q["lc"], aqb_sln=beams[b]["sln"])
over = []
for s, r in BDK.items():
    if r["util"] > 0.9: over.append(dict(check="BDK", sln=s, group=sln_def.get(s, {}).get("grp"), util=r["util"], lc=r["lc"], title=sln_def.get(s, {}).get("title")))
aqb_sln = {}
for b, rs in AQB.items():
    for q in rs:
        if q["util"] is not None and q["util"] > 0.9:
            s = parent_sln(b) if egroup(b) in (62, 25) else beams[b]["sln"]
            k = aqb_sln.get(s)
            if k is None or q["util"] > k["util"]: aqb_sln[s] = dict(check="AQB", sln=s, group=egroup(b), util=q["util"], lc=q["lc"], beam=b, x=q["x"], title=sln_def.get(s, {}).get("title"))
over += list(aqb_sln.values())
buck = {102: [l for l in LCS.values() if 9201 <= l["lc"] <= 9220], 119: [l for l in LCS.values() if 9221 <= l["lc"] <= 9240]}
summ = dict(source=SRC, buckling={k: dict(lowest_lc=v[0]["lc"], title=v[0]["title"]) for k, v in buck.items()},
            groups={str(k): v for k, v in sorted(grp_sum.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))},
            above_0_90=sorted(over, key=lambda r: -r["util"]))
dump("summary_v19m.json", summ)
cdb.close()
