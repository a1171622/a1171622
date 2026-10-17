"""Read model data and results from an open .cdb (pure Python on top of cdbio.Cdb or a test double).

Keys and record classes (SOFiSTiK 2027 sofistik_daten.py):
  10/00 CSYST system          1/NR CMAT material          9/NR CSECT (id 0), CSECT_TXT (id 19)
  11/00 CGRP groups           12/LC CLC_CTRL / CLC_SUPE / CLC_EIGE load case (first record)
  14/ID CLC_ACT action        20/00 CNODE nodes           24/LC CN_DISP node results (m_nr > 0)
  100/00 CBEAM beams (m_nr > 0; id-0 records are CBEAM_SCT)   102/LC CBEAM_FOR beam forces (m_nr > 0)
  150/00 CTRUS, 152/LC CTRUS_RES    160/00 CCABL, 162/LC CCABL_RES    170/00 CSPRI   200/00 CQUAD

Units.  The CDB stores SI base units: lengths and displacements m, rotations rad, forces kN,
moments kNm, areas m2, second moments m4.  This module converts for output:
  displacements mm, rotations mrad, forces kN, moments kNm, A cm2, I cm4.
selftest.py checks these conversions against a hand calculation on a real SOFiSTiK run.
Values SOFiSTiK marks as undefined (|v| >= 1e30) are returned as None.
"""
from __future__ import annotations

import ctypes
import math
import re
import struct

UNDEF = 1.0e30
MAX_LC = 99999
MAX_NR = 99999

LC_KIND_NAMES = {2: "superposition / envelope (MAXIMA)", 4: "eigenmode"}
UNITS = {"displacement": "mm", "rotation": "mrad", "force": "kN", "moment": "kNm",
         "coordinate": "m", "x_along_beam": "m", "area": "cm2", "second_moment": "cm4",
         "frequency": "Hz"}


# ----------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------

def first_int(rec: bytes) -> int:
    return struct.unpack_from("<i", rec, 0)[0] if len(rec) >= 4 else 0


def as_rec(daten, clsname, rec: bytes):
    cls = getattr(daten, clsname)
    n = ctypes.sizeof(cls)
    return cls.from_buffer_copy(rec[:n].ljust(n, b"\0"))


def val(v, scale=1.0, nd=6):
    """float or None (undefined / NaN), scaled and rounded to nd significant-ish decimals."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    if v != v or abs(v) >= UNDEF:
        return None
    v *= scale
    return round(v, nd) if abs(v) >= 1e-12 else 0.0


def parse_ids(spec) -> set | None:
    """None/'' -> None (all).  '1-10,15,20-30' or [1,2,3] or 7 -> set of ints."""
    if spec is None or spec == "" or spec == []:
        return None
    if isinstance(spec, int):
        return {spec}
    if isinstance(spec, (list, tuple, set)):
        out = set()
        for s in spec:
            out |= parse_ids(s) or set()
        return out
    out = set()
    text = re.sub(r"\s*(-|\bto\b|\.\.)\s*", r"\1", str(spec).strip(), flags=re.IGNORECASE)
    for part in re.split(r"[,\s;]+", text):
        if not part:
            continue
        m = re.fullmatch(r"(-?\d+)\s*(?:-|to|\.\.)\s*(-?\d+)", part, re.IGNORECASE)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > b:
                a, b = b, a
            if b - a > 1_000_000:
                raise ValueError(f"Range too large: {part}")
            out.update(range(a, b + 1))
        elif re.fullmatch(r"-?\d+", part):
            out.add(int(part))
        else:
            raise ValueError(f"Cannot read number list '{spec}'. Use e.g. 1-10,15,20-30.")
    return out


def scan_kwl(cdb, kwh, upto, only=None):
    if only is not None:
        return sorted(k for k in only if 0 < k <= upto and cdb.kexist(kwh, k) >= 1)
    return [k for k in range(1, upto + 1) if cdb.kexist(kwh, k) >= 1]


def _extremes(rows, comps, id_keys):
    """{comp: {max: {value, ids...}, min: {...}, abs_max: ...}} over rows (dicts)."""
    ext = {}
    for c in comps:
        best_max = best_min = None
        for r in rows:
            v = r.get(c)
            if v is None:
                continue
            if best_max is None or v > best_max[c]:
                best_max = r
            if best_min is None or v < best_min[c]:
                best_min = r
        if best_max is None:
            continue
        def pick(r, c=c):  # bind c now (B023); pick is only called in this iteration
            d = {"value": r[c]}
            for k in id_keys:
                if k in r:
                    d[k] = r[k]
            return d
        ext[c] = {"max": pick(best_max), "min": pick(best_min)}
    return ext


# ----------------------------------------------------------------------------------------------
# model data
# ----------------------------------------------------------------------------------------------

def system_info(cdb, daten) -> dict:
    recs = cdb.records(10, 0) if cdb.kexist(10, 0) >= 1 else []
    if not recs:
        return {}
    s = as_rec(daten, "CSYST", recs[0])
    box = [[val(s.m_box[i][j]) for j in range(3)] for i in range(2)]
    return {"project": cdb.text(s.m_txt), "group_divisor": int(s.m_igdiv), "nodes": int(s.m_nknot),
            "highest_node": int(s.m_mknot), "system_type": int(s.m_iprob),
            "gravity_code": int(s.m_iachs), "bounding_box_m": box}


def _count(cdb, kwh):
    if cdb.kexist(kwh, 0) < 1:
        return 0
    return sum(1 for r in cdb.records(kwh, 0) if first_int(r) > 0)


def materials(cdb, daten, upto=999):
    out = []
    for nr in scan_kwl(cdb, 1, upto):
        title = ""
        for rec in cdb.records(1, nr):
            if first_int(rec) == 0:
                title = cdb.text(as_rec(daten, "CMAT", rec).m_title)
                break
        out.append({"nr": nr, "title": title})
    return out


def sections(cdb, daten, upto=9999):
    out = []
    for nr in scan_kwl(cdb, 9, upto):
        d = {"nr": nr, "title": "", "A_cm2": None, "Iy_cm4": None, "Iz_cm4": None, "It_cm4": None,
             "material": None}
        for rec in cdb.records(9, nr):
            fi = first_int(rec)
            if fi == 0 and d["A_cm2"] is None:
                c = as_rec(daten, "CSECT", rec)
                d.update(A_cm2=val(c.m_a, 1e4, 3), Iy_cm4=val(c.m_iy, 1e8, 3), Iz_cm4=val(c.m_iz, 1e8, 3),
                         It_cm4=val(c.m_it, 1e8, 3), material=int(c.m_mno))
            elif fi == 19 and not d["title"]:
                d["title"] = cdb.text(as_rec(daten, "CSECT_TXT", rec).m_txt)
            elif fi == 12 and not d["title"] and hasattr(daten, "CSECT_PRO"):
                d["title"] = cdb.text(as_rec(daten, "CSECT_PRO", rec).m_bez)
        out.append(d)
    return out


def groups(cdb, daten):
    if cdb.kexist(11, 0) < 1:
        return []
    out = []
    for rec in cdb.records(11, 0):
        g = as_rec(daten, "CGRP", rec)
        out.append({"group": int(g.m_ng), "element_code": int(g.m_typ), "count": int(g.m_num),
                    "min_element": int(g.m_min), "max_element": int(g.m_max), "title": cdb.text(g.m_text)})
    return out


def _action_text(cdb, daten, ityp):
    ityp = int(ityp)
    if ityp == 0:
        return ""
    if cdb.kexist(14, ityp) >= 1 and hasattr(daten, "CLC_ACT"):
        for rec in cdb.records(14, ityp):
            if first_int(rec) == 1:
                t = cdb.text(as_rec(daten, "CLC_ACT", rec).m_txt)
                if t:
                    return t
    s = cdb.text([ityp])
    return s if s and all(ch.isalnum() or ch in "_-()" for ch in s) else ""


def load_cases(cdb, daten, only=None) -> list:
    out = []
    for lc in scan_kwl(cdb, 12, MAX_LC, only):
        recs = cdb.records(12, lc)
        if not recs:
            continue
        c = as_rec(daten, "CLC_CTRL", recs[0])
        kind = int(c.m_kind)
        d = {"lc": lc, "title": cdb.text(c.m_rtex), "kind": kind,
             "kind_name": LC_KIND_NAMES.get(kind, "load case"),
             "action": "" if kind == 4 else _action_text(cdb, daten, c.m_ityp)}
        if kind == 4 and hasattr(daten, "CLC_EIGE"):
            e = as_rec(daten, "CLC_EIGE", recs[0])
            om = val(e.m_omega)
            d.update(mode=int(e.m_nr_mode), frequency_Hz=round(om / (2 * math.pi), 5) if om else None,
                     period_s=round(2 * math.pi / om, 5) if om else None)
        elif kind != 2:
            d.update(factor=val(c.m_fact), dead_load_factors=[val(c.m_facx), val(c.m_facy), val(c.m_facz)],
                     sum_reactions_kN=[val(c.m_rx), val(c.m_ry), val(c.m_rz)])
        d["has_results"] = [name for kwh, name in ((24, "nodes"), (102, "beams"), (152, "trusses"),
                                                   (162, "cables"), (210, "quads"))
                            if cdb.kexist(kwh, lc) >= 1]
        out.append(d)
    return out


def overview(cdb, daten) -> dict:
    return {
        "system": system_info(cdb, daten),
        "element_counts": {"nodes": _count(cdb, 20), "beams": _count(cdb, 100), "trusses": _count(cdb, 150),
                           "cables": _count(cdb, 160), "springs": _count(cdb, 170), "quads": _count(cdb, 200)},
        "materials": materials(cdb, daten),
        "sections": sections(cdb, daten),
        "groups": groups(cdb, daten),
        "load_cases": load_cases(cdb, daten),
        "units": UNITS,
    }


def nodes(cdb, daten, ids=None, max_rows=500) -> dict:
    want = parse_ids(ids)
    rows: list = []
    total = 0
    if cdb.kexist(20, 0) >= 1:
        for rec in cdb.records(20, 0):
            n = as_rec(daten, "CNODE", rec)
            if n.m_nr <= 0 or (want is not None and n.m_nr not in want):
                continue
            total += 1
            if len(rows) < max_rows:
                rows.append({"node": int(n.m_nr), "x": val(n.m_xyz[0]), "y": val(n.m_xyz[1]),
                             "z": val(n.m_xyz[2]), "fixity_code": int(n.m_kfix)})
    return {"count": total, "rows": rows, "truncated": total > len(rows), "units": {"x,y,z": "m"}}


def _node_coords(cdb, daten):
    out = {}
    if cdb.kexist(20, 0) >= 1:
        for rec in cdb.records(20, 0):
            n = as_rec(daten, "CNODE", rec)
            if n.m_nr > 0:
                out[int(n.m_nr)] = (val(n.m_xyz[0]), val(n.m_xyz[1]), val(n.m_xyz[2]))
    return out


# ----------------------------------------------------------------------------------------------
# results
# ----------------------------------------------------------------------------------------------

NODE_COMPS = ("ux", "uy", "uz", "urx", "ury", "urz", "px", "py", "pz", "mx", "my", "mz")


def _node_rows(cdb, daten, lc, want):
    rows = []
    for rec in cdb.records(24, lc):
        if first_int(rec) <= 0:
            continue
        d = as_rec(daten, "CN_DISP", rec)
        nr = int(d.m_nr)
        if want is not None and nr not in want:
            continue
        rows.append({"node": nr,
                     "ux": val(d.m_ux, 1e3, 4), "uy": val(d.m_uy, 1e3, 4), "uz": val(d.m_uz, 1e3, 4),
                     "urx": val(d.m_urx, 1e3, 5), "ury": val(d.m_ury, 1e3, 5), "urz": val(d.m_urz, 1e3, 5),
                     "px": val(d.m_px, 1, 4), "py": val(d.m_py, 1, 4), "pz": val(d.m_pz, 1, 4),
                     "mx": val(d.m_mx, 1, 4), "my": val(d.m_my, 1, 4), "mz": val(d.m_mz, 1, 4)})
    return rows


def _missing(cdb, kwh, lc, what):
    if cdb.kexist(kwh, lc) < 1:
        return {"error": f"No {what} results for load case {lc} in this .cdb (key {kwh}/{lc} missing). "
                         "Check the load case number and that the analysis (e.g. ASE) ran for it."}
    return None


def node_results(cdb, daten, lc, ids=None, max_rows=200, include_coords=False) -> dict:
    lc = int(lc)
    miss = _missing(cdb, 24, lc, "node")
    if miss:
        return miss
    rows = _node_rows(cdb, daten, lc, parse_ids(ids))
    ext = _extremes(rows, NODE_COMPS[:6], ("node",))
    for r in rows:
        r["u_total"] = (round(math.sqrt(sum((r[k] or 0) ** 2 for k in ("ux", "uy", "uz"))), 4)
                        if any(r[k] is not None for k in ("ux", "uy", "uz")) else None)
    ext.update(_extremes(rows, ("u_total",), ("node",)))
    shown = rows[:max_rows]
    if include_coords:
        xyz = _node_coords(cdb, daten)
        for r in shown:
            r["x"], r["y"], r["z"] = xyz.get(r["node"], (None, None, None))
    return {"lc": lc, "count": len(rows), "extremes": ext, "rows": shown,
            "truncated": len(rows) > len(shown),
            "units": {"ux,uy,uz,u_total": "mm", "urx,ury,urz": "mrad", "px,py,pz": "kN", "mx,my,mz": "kNm"}}


def support_reactions(cdb, daten, lc, ids=None, max_rows=500) -> dict:
    lc = int(lc)
    miss = _missing(cdb, 24, lc, "node")
    if miss:
        return miss
    rows = [r for r in _node_rows(cdb, daten, lc, parse_ids(ids))
            if any(abs(r[k] or 0) > 1e-9 for k in ("px", "py", "pz", "mx", "my", "mz"))]
    for r in rows:
        for k in ("ux", "uy", "uz", "urx", "ury", "urz"):
            r.pop(k, None)
    sums = {k: round(sum(r[k] or 0 for r in rows), 4) for k in ("px", "py", "pz")}
    ctrl = load_cases(cdb, daten, only={lc})
    return {"lc": lc, "supports_with_reaction": len(rows), "sum_kN": sums,
            "sum_stored_by_sofistik_kN": (ctrl[0].get("sum_reactions_kN") if ctrl else None),
            "extremes": _extremes(rows, ("px", "py", "pz", "mx", "my", "mz"), ("node",)),
            "rows": rows[:max_rows], "truncated": len(rows) > max_rows,
            "units": {"px,py,pz": "kN", "mx,my,mz": "kNm"},
            "note": "Sign as stored by SOFiSTiK (nodal support force in global axes)."}


def _beam_index(cdb, daten):
    """element -> {sln, section, length_m}"""
    out: dict = {}
    if cdb.kexist(100, 0) < 1:
        return out
    for rec in cdb.records(100, 0):
        if first_int(rec) > 0:
            b = as_rec(daten, "CBEAM", rec)
            out[int(b.m_nr)] = {"sln": int(b.m_nref) or None, "section": int(b.m_np), "length_m": val(b.m_dl, 1, 4),
                         "nodes": [int(b.m_node[0]), int(b.m_node[1])]}
    return out


def _group_of(nr, grp_list, gdiv, code=None):
    hits = [g for g in grp_list if g["min_element"] <= nr <= g["max_element"]]
    if code is not None:
        coded = [g for g in hits if g["element_code"] == code]
        if coded:
            hits = coded
    gs = sorted({g["group"] for g in hits})
    if len(gs) == 1:
        return gs[0]
    if not gs and gdiv and gdiv > 0:
        return nr // gdiv
    return None if not gs else gs


def _beam_ctx(cdb, daten):
    return {"idx": _beam_index(cdb, daten), "groups": groups(cdb, daten),
            "gdiv": system_info(cdb, daten).get("group_divisor", 0)}


SLN_NOTE = ("Structural line numbers are taken from each beam's reference axis (CBEAM m_nref). The self-test "
            "checks this on a SOFiMSHC model; if its SLN check failed, do not rely on SLN filters.")


def beam_forces(cdb, daten, lc, beams=None, groups_=None, slns=None, max_rows=300, ends_only=False,
                ctx=None) -> dict:
    lc = int(lc)
    miss = _missing(cdb, 102, lc, "beam")
    if miss:
        return miss
    want_b, want_g, want_s = parse_ids(beams), parse_ids(groups_), parse_ids(slns)
    ctx = ctx or _beam_ctx(cdb, daten)
    idx, grp_list, gdiv = ctx["idx"], ctx["groups"], ctx["gdiv"]
    rows = []
    for rec in cdb.records(102, lc):
        if first_int(rec) <= 0:
            continue
        f = as_rec(daten, "CBEAM_FOR", rec)
        nr = int(f.m_nr)
        if want_b is not None and nr not in want_b:
            continue
        info = idx.get(nr, {})
        if want_s is not None and info.get("sln") not in want_s:
            continue
        g = _group_of(nr, grp_list, gdiv, code=100)
        if want_g is not None and not (g in want_g if isinstance(g, int) else bool(set(g or []) & want_g)):
            continue
        rows.append({"beam": nr, "sln": info.get("sln"), "group": g, "x": val(f.m_x, 1, 4),
                     "N": val(f.m_n, 1, 4), "Vy": val(f.m_vy, 1, 4), "Vz": val(f.m_vz, 1, 4),
                     "Mt": val(f.m_mt, 1, 4), "My": val(f.m_my, 1, 4), "Mz": val(f.m_mz, 1, 4)})
    if ends_only:
        keep: list = []
        by: dict = {}
        for r in rows:
            by.setdefault(r["beam"], []).append(r)
        for rs in by.values():
            rs.sort(key=lambda r: r["x"] or 0)
            keep.extend([rs[0]] + ([rs[-1]] if len(rs) > 1 else []))
        rows = keep
    ext = _extremes(rows, ("N", "Vy", "Vz", "Mt", "My", "Mz"), ("beam", "x", "sln", "group"))
    extra = {}
    if want_s is not None:
        extra["sln_note"] = SLN_NOTE
        if not rows:
            known = sorted({v["sln"] for v in idx.values() if v.get("sln")})
            extra["warning"] = ("No beam matched these structural lines. Lines known from the beams: "
                                + (", ".join(map(str, known[:60])) if known else "none (m_nref is 0 for all beams)"))
    return {**extra, "lc": lc, "stations": len(rows), "beams": len({r["beam"] for r in rows}), "extremes": ext,
            "rows": rows[:max_rows], "truncated": len(rows) > max_rows,
            "units": {"x": "m from beam start", "N,Vy,Vz": "kN", "Mt,My,Mz": "kNm"},
            "note": "Local beam axes, SOFiSTiK sign convention (N > 0 tension). 'group' is taken from the "
                    "group element ranges (11/00); a list means the range is ambiguous."}


def axial_forces(cdb, daten, lc, element_type="truss", ids=None, max_rows=300) -> dict:
    lc = int(lc)
    kwh, cls, what = {"truss": (152, "CTRUS_RES", "truss"), "cable": (162, "CCABL_RES", "cable")}[element_type]
    miss = _missing(cdb, kwh, lc, what)
    if miss:
        return miss
    want = parse_ids(ids)
    rows = []
    for rec in cdb.records(kwh, lc):
        if first_int(rec) <= 0:
            continue
        r = as_rec(daten, cls, rec)
        if want is not None and int(r.m_nr) not in want:
            continue
        rows.append({"element": int(r.m_nr), "N": val(r.m_n, 1, 4), "axial_disp": val(r.m_v, 1e3, 4)})
    return {"lc": lc, "type": element_type, "count": len(rows),
            "extremes": _extremes(rows, ("N",), ("element",)), "rows": rows[:max_rows],
            "truncated": len(rows) > max_rows, "units": {"N": "kN (tension +)", "axial_disp": "mm"}}


def envelope(cdb, daten, lcs, what="beam", ids=None, groups_=None, slns=None) -> dict:
    """Max / min of each component over several load cases, with the governing LC."""
    lcset = parse_ids(lcs)
    if not lcset:
        return {"error": "Give the load cases, e.g. 101-118."}
    kwh = {"beam": 102, "node": 24, "support": 24, "truss": 152, "cable": 162}[what]
    found = [lc for lc in sorted(lcset) if cdb.kexist(kwh, lc) >= 1]
    eigen = []
    for lc in found:                                # mode shapes are normalised, not real results
        recs = cdb.records(12, lc) if cdb.kexist(12, lc) >= 1 else []
        if recs and int(as_rec(daten, "CLC_CTRL", recs[0]).m_kind) == 4:
            eigen.append(lc)
    found = [lc for lc in found if lc not in eigen]
    warnings: list = []
    per_lc: dict = {}
    overall: dict = {}
    ctx = _beam_ctx(cdb, daten) if what == "beam" else None
    for lc in found:
        if what == "beam":
            r = beam_forces(cdb, daten, lc, beams=ids, groups_=groups_, slns=slns, max_rows=0, ctx=ctx)
        elif what == "node":
            r = node_results(cdb, daten, lc, ids=ids, max_rows=0)
        elif what == "support":
            r = support_reactions(cdb, daten, lc, ids=ids, max_rows=0)
        else:
            r = axial_forces(cdb, daten, lc, element_type=what, ids=ids, max_rows=0)
        if hasattr(cdb, "forget"):
            cdb.forget(kwh, lc)                     # keep memory flat over many load cases
        if r.get("warning") and r["warning"] not in warnings:
            warnings.append(r["warning"])
        per_lc[lc] = r.get("extremes", {})
        for comp, mm in per_lc[lc].items():
            o = overall.setdefault(comp, {"max": None, "min": None})
            if o["max"] is None or mm["max"]["value"] > o["max"]["value"]:
                o["max"] = dict(mm["max"], lc=lc)
            if o["min"] is None or mm["min"]["value"] < o["min"]["value"]:
                o["min"] = dict(mm["min"], lc=lc)
    out = {"what": what, "load_cases_found": found,
           "load_cases_missing": sorted(lcset - set(found) - set(eigen)), "overall": overall, "per_lc": per_lc,
           "units": UNITS}
    if eigen:
        out["eigen_load_cases_skipped"] = eigen
        warnings.append("Eigenmode load cases " + ", ".join(map(str, eigen)) + " were left out: mode shapes "
                        "are normalised and are not design results.")
    if warnings:
        out["warning"] = " ".join(warnings)
    return out


def read_key(cdb, daten, kwh, kwl, class_name=None, max_records=20, skip=0) -> dict:
    """Generic: decode records of any key with any sofistik_daten class (for things the other tools
    do not cover).  Without class_name: record sizes and the first integers / floats."""
    ex = cdb.kexist(int(kwh), int(kwl))
    out: dict = {"kwh": int(kwh), "kwl": int(kwl), "kexist": ex,
                 "kexist_meaning": {0: "key missing", 1: "key exists, no data", 2: "key with data"}.get(ex, "?")}
    if ex < 1:
        return out
    recs = cdb.records(int(kwh), int(kwl))
    out["record_count"] = len(recs)
    rows: list = []
    cls = getattr(daten, class_name, None) if class_name else None
    if class_name and cls is None:
        out["error"] = f"No class {class_name} in sofistik_daten.py."
        return out
    for rec in recs[skip:skip + max_records]:
        if cls is None:
            n = len(rec) // 4
            rows.append({"bytes": len(rec), "ints": list(struct.unpack_from(f"<{min(n, 12)}i", rec)),
                         "floats": [val(x) for x in struct.unpack_from(f"<{min(n, 12)}f", rec)]})
            continue
        obj = as_rec(daten, class_name, rec)
        d: dict = {"_bytes": len(rec)}
        for fname, _ in cls._fields_:
            v = getattr(obj, fname)
            if isinstance(v, ctypes.Array):
                flat = []
                for x in v:
                    flat.extend(list(x) if isinstance(x, ctypes.Array) else [x])
                if fname in ("m_text", "m_rtex", "m_txt", "m_title", "m_bez", "m_name"):
                    d[fname] = cdb.text(flat)
                else:
                    d[fname] = [val(x) if isinstance(x, float) else x for x in flat[:24]]
            else:
                d[fname] = val(v) if isinstance(v, float) else v
        rows.append(d)
    out["records"] = rows
    out["note"] = "Raw CDB values (SI base units: m, kN, kNm, rad), not converted."
    return out
