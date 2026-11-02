"""SOFiSTiK side of the workflow (code independent): read the model and the forces, nothing about any design code.

  read_dat(path)         sections (AQUA SECT/PROF), structural lines (SOFIMSHC SLN/SLNB) and the STO# values
  read_bdk_members(path) the member definitions of the BDK block (MEMB SLN + CONT, CVL restraint stations),
                         with the CADINP IF/ELSE/ENDIF switches evaluated from the STO# values
  read_forces(csv.gz)    beam forces per load case: rows lc, beam, sln, group, x, N, Vy, Vz, Mt, My, Mz
                         (made from the SOFiSTiK MCP server's cdb_beam_forces results by harvest_mcp.py, or by
                         export_cdb_forces.py on the PC)
  read_bdk_summary(erg)  BDK 'Summary of the Results' table (for comparison only)
  read_aqb_maxima(erg)   AQB 'Maximum Utilisation Level' per section (for comparison only)
"""
from __future__ import annotations

import csv
import gzip
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Sln:
    no: int
    grp: int
    sno: int
    pts: list                 # polyline points (x, y, z) in m
    fixa: str = ""
    fixe: str = ""
    title: str = ""

    @property
    def length(self) -> float:
        return sum(math.dist(self.pts[i], self.pts[i + 1]) for i in range(len(self.pts) - 1))


@dataclass
class BdkMember:
    id: int
    slns: list
    stations: list = field(default_factory=list)   # [(S from member start in m, 'CY' / 'CY+DX', comment)]
    comment: str = ""
    curve: str = ""                                 # CTRL CURV (LTB curve) in force
    lcs: str = ""                                   # LC list in force
    sway: bool = False


def _num(tok, sto):
    tok = tok.strip()
    if tok.startswith("#"):
        return float(sto.get(tok[1:].upper(), 0.0))
    return float(tok)


def read_dat(path: str):
    """sections {no: {'prof': 'RHS', 'name': 'RHS 200x100x6', 'title': ...}}, slns {no: Sln}, sto {name: value}."""
    sections, slns, sto = {}, {}, {}
    prog = ""
    cur_sect = None
    cur_sln = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\n")
            code = line.split("$")[0] if not line.lstrip().startswith("!") else ""
            m = re.match(r"\s*\+?PROG\s+(\w+)", code, re.I)
            if m:
                prog = m.group(1).upper()
                continue
            m = re.match(r"\s*STO#(\w+)\s+([-+]?\d[\d.]*(?:[Ee][-+]?\d+)?)\s*$", code)
            if m:
                sto[m.group(1).upper()] = float(m.group(2))
            if prog == "AQUA":
                m = re.match(r"SECT\s+(\d+)", code)
                if m:
                    cur_sect = int(m.group(1))
                    t = re.search(r'TITL\s+"([^"]*)"', line)
                    sections[cur_sect] = {"prof": None, "name": None, "title": t.group(1) if t else ""}
                m = re.match(r"PROF\s+TYPE\s+'(\w+)'\s+Z1\s+([\d.]+)(?:\s+Z2\s+([\d.]+))?(?:\s+Z3\s+([\d.]+))?", code)
                if m and cur_sect is not None:
                    typ = m.group(1).upper()
                    z = [g for g in m.group(2, 3, 4) if g]
                    zz = [str(int(float(v))) if float(v).is_integer() else v for v in z]
                    if typ == "CHS":
                        name = f"CHS {zz[0]}x{zz[-1]}"
                    elif typ == "RHS" and zz[0] == zz[1]:
                        name = f"SHS {'x'.join(zz)}"
                    else:
                        name = f"{typ} {'x'.join(zz)}"
                    sections[cur_sect].update(prof=typ, name=name)
            elif prog == "SOFIMSHC":
                m = re.match(r"SLN\s+(\d+)\s+(.*)", code)
                if m:
                    no = int(m.group(1))
                    rest = m.group(2)
                    g = re.search(r"GRP\s+(\d+)", rest)
                    s = re.search(r"SNO\s+(\d+)", rest)
                    fa = re.search(r"FIXA\s+'(\w*)'", rest)
                    fe = re.search(r"FIXE\s+'(\w*)'", rest)
                    t = re.search(r'TITL\s+"([^"]*)"', line)
                    cur_sln = Sln(no, int(g.group(1)) if g else 0, int(s.group(1)) if s else 0, [],
                                  fa.group(1) if fa else "", fe.group(1) if fe else "", t.group(1) if t else "")
                    slns[no] = cur_sln
                    continue
                m = re.match(r"SLNB\s+X1\s+(\S+)\s+(\S+)\s+(\S+)\s+X2\s+(\S+)\s+(\S+)\s+(\S+)", code)
                if m and cur_sln is not None:
                    p1 = tuple(float(v) for v in m.group(1, 2, 3))
                    p2 = tuple(float(v) for v in m.group(4, 5, 6))
                    if not cur_sln.pts:
                        cur_sln.pts = [p1, p2]
                    elif math.dist(cur_sln.pts[-1], p1) < 1e-4:
                        cur_sln.pts.append(p2)
                    else:
                        cur_sln.pts += [p1, p2]
                elif not code.startswith("SLN"):
                    cur_sln = None if re.match(r"(SAR|SPT|GRP|END)", code) else cur_sln
    return sections, slns, sto


def read_bdk_members(path: str, sto: dict | None = None) -> list:
    """Members of every BDK program in the file, after the CADINP switches."""
    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    starts = [i for i, l in enumerate(lines) if re.match(r"\s*\+?PROG\s+BDK", l, re.I)]
    out = []
    for i0 in starts:
        out += _bdk_block(lines, i0, dict(sto or {}))
    return out


def _bdk_block(lines, i0, sto):
    stack = []                 # list of (active_before, cond_value, in_else)
    active = True
    pending = []
    members = []
    comment = ""
    curve, lcs, sway = "", "", False
    cur = None
    for raw in lines[i0 + 1:]:
        if re.match(r"\s*END\b", raw):
            break
        s = raw.strip()
        if s.startswith("$"):
            if active and re.match(r"\$\s+\S", s) and not s.startswith("$ -") and not s.startswith("$   spans"):
                comment = s.lstrip("$ ").strip()
            continue
        code = raw.split("$")[0].strip()
        if not code:
            continue
        m = re.match(r"IF\s+#(\w+)\s*([<>=]+)\s*([-\d.]+)", code, re.I)
        if m:
            val = float(sto.get(m.group(1).upper(), 0.0))
            op, ref = m.group(2), float(m.group(3))
            cond = {">": val > ref, "<": val < ref, ">=": val >= ref, "<=": val <= ref, "=": val == ref,
                    "==": val == ref}[op]
            stack.append((active, cond))
            active = active and cond
            continue
        if re.match(r"ELSE\b", code, re.I):
            before, cond = stack[-1]
            active = before and not cond
            continue
        if re.match(r"ENDIF\b", code, re.I):
            active = stack.pop()[0]
            continue
        if not active:
            continue
        m = re.match(r"STO#(\w+)\s+([-+]?\d[\d.]*(?:[Ee][-+]?\d+)?)\s*$", code)
        if m:
            sto[m.group(1).upper()] = float(m.group(2))
            continue
        if code.upper().startswith("CTRL"):
            c = re.search(r"CURV\s+(\w)", code)
            curve = c.group(1) if c else curve
            sway = bool(re.search(r"SWY\s+YES", code))
            continue
        if code.upper().startswith("LC"):
            lcs = code[2:].strip()
            continue
        m = re.match(r"CVL\s+REF\s+STRT\s+S\s+([\d.]+)(.*)", code)
        if m:
            kind = "CY+DX" if re.search(r"DX\s+FIX", m.group(2)) else "CY"
            note = raw.split("$", 1)[1].strip() if "$" in raw else ""
            pending.append((float(m.group(1)), kind, note))
            continue
        m = re.match(r"MEMB\s+SLN\s+(\d+).*?ID\s+(\d+)", code)
        if m:
            cur = BdkMember(int(m.group(2)), [int(m.group(1))], pending, comment, curve, lcs, sway)
            members.append(cur)
            pending = []
            continue
        m = re.match(r"CONT\s+(\d+)", code)
        if m and cur is not None:
            cur.slns.append(int(m.group(1)))
    return members


def read_forces(path: str, lcs=None) -> dict:
    """{lc: {sln: [(beam, x, N, Vy, Vz, Mt, My, Mz), ...] sorted by beam then x}}"""
    out: dict = defaultdict(lambda: defaultdict(list))
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt", newline="") as f:
        for r in csv.DictReader(f):
            lc = int(r["lc"])
            if lcs is not None and lc not in lcs:
                continue
            sln = int(r["sln"]) if r["sln"] not in ("", "None") else None
            out[lc][sln].append((int(r["beam"]), float(r["x"]), float(r["N"]), float(r["Vy"]), float(r["Vz"]),
                                 float(r["Mt"]), float(r["My"]), float(r["Mz"])))
    for lc in out:
        for sln in out[lc]:
            out[lc][sln].sort(key=lambda t: (t[0], t[1]))
    return out


def read_bdk_summary(erg_path: str) -> dict:
    """{member id: dict(lc, ny, nz, my, mz, nmy, nmz, check)} from every BDK 'Summary of the Results' table."""
    out = {}
    lines = open(erg_path, encoding="utf-8", errors="replace").read().split("\n")
    for i, l in enumerate(lines):
        if "Summary of the Results" not in l:
            continue
        for l2 in lines[i + 1:i + 2000]:
            m = re.match(r"\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\w[\w ]*)$",
                         l2)
            if m:
                k = int(m.group(1))
                rec = dict(lc=int(m.group(2)), ny=float(m.group(4)), nz=float(m.group(5)), my=float(m.group(6)),
                           mz=float(m.group(7)), nmy=float(m.group(8)), nmz=float(m.group(9)),
                           check=m.group(10).strip())
                if k not in out or max(rec["nmy"], rec["nmz"]) > max(out[k]["nmy"], out[k]["nmz"]):
                    out[k] = rec
            elif "Summary" in l2 or "Utilisation" in l2:
                break
    return out


def read_aqb_maxima(erg_path: str) -> dict:
    """{section no: total utilisation} from the last AQB 'Maximum Utilisation Level' table."""
    lines = open(erg_path, encoding="utf-8", errors="replace").read().split("\n")
    idx = [i for i, l in enumerate(lines) if "Maximum Utilisation Level" in l]
    out = {}
    if not idx:
        return out
    for l in lines[idx[-1]:idx[-1] + 60]:
        m = re.match(r"\s+Section\s+(\d+)\s+.*\s([\d.]+)\s*$", l)
        if m:
            out[int(m.group(1))] = float(m.group(2))
    return out


def project(pts, p):
    """(distance, position s) of point p onto the polyline pts."""
    best, acc = (1e9, 0.0), 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        ab = [b[k] - a[k] for k in range(3)]
        L2 = sum(c * c for c in ab)
        L = math.sqrt(L2)
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, sum((p[k] - a[k]) * ab[k] for k in range(3)) / L2))
        q = [a[k] + t * ab[k] for k in range(3)]
        d = math.dist(p, q)
        if d < best[0]:
            best = (d, acc + t * L)
        acc += L
    return best


def beam_positions(cbeam: dict, nodes: dict, slns: dict, beams=None, tol=0.01) -> dict:
    """{beam: (sln, s_start, s_end)}: which structural line of the .dat a beam lies on and where (m from the line
    start).  Needed where SOFiMSHC split a line into new numbered pieces (other lines meeting it mid-length);
    BDK still checks the original line.  cbeam = {beam: {'nodes': [n1, n2], 'sln': ...}}, nodes = {n: (x, y, z)}."""
    out = {}
    cands = list(slns.values())
    for b, info in cbeam.items():
        b = int(b)
        if beams is not None and b not in beams:
            continue
        n1, n2 = info["nodes"]
        if n1 not in nodes or n2 not in nodes:
            continue
        p1, p2 = nodes[n1], nodes[n2]
        hit = None
        for ln in cands:
            d1, s1 = project(ln.pts, p1)
            if d1 > tol:
                continue
            d2, s2 = project(ln.pts, p2)
            if d2 <= tol and abs(s2 - s1) > 1e-4:
                if hit is None or ln.no == info.get("sln"):
                    hit = (ln.no, s1, s2)
        if hit:
            out[b] = hit
    return out


def remap_forces(F: dict, beam_pos: dict, slns: dict) -> dict:
    """Put every beam on its .dat structural line with its position.  Rows become
    (beam, x, N, Vy, Vz, Mt, My, Mz, u) with u = position on the line (m from its start), or None when the beam's
    position is not known (then members.diagrams falls back to the beam-number order)."""
    out: dict = defaultdict(lambda: defaultdict(list))
    for lc, by in F.items():
        for sln, rows in by.items():
            for r in rows:
                b = r[0]
                bp = beam_pos.get(b) or beam_pos.get(str(b))
                if bp:
                    line, u1, u2 = bp
                    u = u1 + (r[1] if u2 >= u1 else -r[1])
                    out[lc][int(line)].append(tuple(r) + (u,))
                else:
                    out[lc][sln].append(tuple(r) + (None,))
    for lc in out:
        for sln in out[lc]:
            out[lc][sln].sort(key=lambda t: (t[8] if t[8] is not None else -1, t[0], t[1]))
    return out
