#!/usr/bin/env python3
"""Write expected.json (applied load totals per load case) for project 26016, from the load generator.

usage: python3 -I make_expected_26016.py <26016 .dat that contains the unified loads> <out expected.json>
           [--generator /mnt/project-files/26016/audit/generator] [--params default|legacy] [--workdir W]

Route (03 M2, "two routes to the same number before SOFiSTiK sees it"): the generator's own record table
(gen_unified.py lc_records, the same source write_dat.py turned into the .dat) is summed record by record
with its geometry (geo.py / decomp.py: load-area polygons, structural-line lengths; arcs as chords) exactly as
generator/totals.py does, for EVERY load case of the generator, not only the 25 printed by totals.py.
Before writing, every STO# parameter of the .dat is compared with the generator's parameter set; any
difference -> CANNOT_RUN (the expected values would belong to another parameter set).

Output (the shape equilibrium_check.py reads):
  {"project": "26016", "source": ..., "dat_sha256": ..., "params": "default",
   "sign": "applied load, global axes, Z up; expected stored reaction = -F",
   "load_cases": {"2": {"F_kN": [fx, fy, fz], "gross_kN": g, "gross_kN_xyz": [gx, gy, gz], "title": "...",
                        "kind": "applied"}, ...},
   "not_expected": {"1": "reason", ...},
   "combinations": [101, 102, ...],
   "selfweight_lcs": [1]}
gross_kN_xyz[j] = sum over loaded objects of |F_j| (the per-component reference of equilibrium_check, A-06).
Moments of LINE MXX/MYY records and temperature records (DT/DTXY) add no force; they are counted in
'zero_force_records' so a load case that is only temperature shows gross 0 (equilibrium_check then asks for
the member-force proof E3 instead of passing a vacuous net sum).
"""
from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cadinp as C  # noqa: E402
from _common import CannotRun, Parser, Report, input_record, run_main, sha256_file  # noqa: E402

TOOL = "make_expected_26016"
GEN = "/mnt/project-files/26016/audit/generator"


def load_generator(gen_dir):
    g = {"__name__": "gen26016"}
    cwd = os.getcwd()
    try:
        os.chdir(gen_dir)
        with open(os.path.join(gen_dir, "gen_unified.py"), encoding="utf-8") as f:
            code = f.read()
        exec(compile(code, os.path.join(gen_dir, "gen_unified.py"), "exec"), g)
    finally:
        os.chdir(cwd)
    return g


def record_force(g, kind, n, typ, v):
    """global force (Fx, Fy, Fz) of one generator record, Z up; None if the type is not understood."""
    lar, sln, NEWLAR, quad_area = g["lar"], g["sln"], g["NEWLAR"], g["quad_area"]
    comp = {"PXX": 0, "PYY": 1, "PZZ": 2}
    if kind == "AREA":
        A = lar[n]["area"] if n in lar else quad_area(NEWLAR[n])
        if typ == "PG":
            return (0.0, 0.0, -v * A)
        if typ in comp:
            f = [0.0, 0.0, 0.0]
            f[comp[typ]] = v * A
            return tuple(f)
        return None
    if kind == "LINE":
        L = sln[n]["len"]
        if typ == "PG":
            return (0.0, 0.0, -v * L)
        if typ in comp:
            f = [0.0, 0.0, 0.0]
            f[comp[typ]] = v * L
            return tuple(f)
        if typ in ("PXP", "PYP", "PZP"):
            j = "PXP PYP PZP".split().index(typ)
            o = [k for k in range(3) if k != j]
            proj = sum(math.hypot(b[o[0]] - a[o[0]], b[o[1]] - a[o[1]]) for a, b in sln[n]["segs"])
            f = [0.0, 0.0, 0.0]
            f[j] = v * proj
            return tuple(f)
        if typ in ("MXX", "MYY", "MZZ"):
            return (0.0, 0.0, 0.0)
        return None
    if kind in ("BEAMGRP", "QUADGRP") and typ in ("DT", "DTXY"):
        return (0.0, 0.0, 0.0)
    return None


def build(dat_path, gen_dir, which):
    g = load_generator(gen_dir)
    P = g["pset"](which)
    # parameters of the .dat must equal the generator's set
    dat = C.Dat.from_file(dat_path)
    diffs = []
    for p in g["PARS"]:
        if p[0] == "$":
            continue
        name = p[0]
        if name not in dat.store:
            diffs.append(f"{name}: not stored (STO#) in the .dat")
            continue
        dv = dat.store[name]
        if not isinstance(dv, float) or abs(dv - P[name]) > 1e-9 * max(1.0, abs(P[name])):
            diffs.append(f"{name}: .dat {dv} vs generator '{which}' {P[name]}")
    if diffs:
        raise CannotRun("the .dat parameters differ from the generator parameter set '" + which + "': "
                        + "; ".join(diffs[:12]))
    out, notexp, zero = {}, {}, {}
    for no, d in g["LCD"].items():
        if no == 1:
            notexp["1"] = ("self-weight (FACD only): no generator total; E2 needs cdb_overview A_cm2 x member "
                           "lengths x 78.5 plus the shell plates (03 E2, not automated)")
            continue
        recs = g["lc_records"](no, P)
        F = [0.0, 0.0, 0.0]
        gross = 0.0
        unknown = []
        nz = 0
        per_obj = {}
        for (kind, n, typ), v in recs.items():
            f = record_force(g, kind, n, typ, v)
            if f is None:
                unknown.append(f"{kind} {n} {typ}")
                continue
            if f == (0.0, 0.0, 0.0):
                nz += 1
            acc = per_obj.setdefault((kind, n), [0.0, 0.0, 0.0])
            for j in range(3):
                F[j] += f[j]
                acc[j] += f[j]
        # gross = sum over loaded objects (area / line) of the size of the force each carries
        gross = sum(math.sqrt(sum(x * x for x in acc)) for acc in per_obj.values())
        # per-component reference (review A-06): sum over loaded objects of |F_j|
        gxyz = [sum(abs(acc[j]) for acc in per_obj.values()) for j in range(3)]
        if unknown:
            notexp[str(no)] = "record types without a force rule: " + ", ".join(unknown[:5])
            continue
        out[str(no)] = {"F_kN": [round(x, 4) for x in F], "gross_kN": round(gross, 4),
                        "gross_kN_xyz": [round(x, 4) for x in gxyz], "title": d["title"],
                        "kind": "applied", "zero_force_records": nz}
    combos = sorted(c[0] for c in g["COMBOS"])
    # intended combination factors (review N-01): per combination the FACD and the factor of every copied LC,
    # evaluated from the generator's own combination table (gen_unified.py COMBOS + GROUPS + EHF rule of
    # combo_records) with the same parameter set; combo_check C4 compares the .dat with these exactly.
    cf = {}
    for c in g["COMBOS"]:
        no, typ, facd, title, parts, ehf, eg, eq = c
        cp = {}
        for grp, expr in parts:
            f = g["ev"](expr, P)
            for src in (g["GROUPS"][grp] if isinstance(grp, str) else [grp]):
                cp[str(src)] = round(cp.get(str(src), 0.0) + f, 6)
        if ehf is not None and P["EHF"] > 0:
            cp[str(501 + ehf)] = round(cp.get(str(501 + ehf), 0.0) + g["ev"](eg, P), 6)
            if eq:
                cp[str(505 + ehf)] = round(cp.get(str(505 + ehf), 0.0) + g["ev"](eq, P), 6)
        cf[str(no)] = {"facd": round(g["ev"](facd, P), 6), "copies": cp, "title": title, "type": typ,
                       "expr": {"facd": facd, "parts": [[str(a), str(b)] for a, b in parts]}}
    return {"project": "26016", "params": which,
            "source": f"{gen_dir}/gen_unified.py lc_records + geo.py geometry (make_expected_26016.py)",
            "dat": os.path.abspath(dat_path), "dat_sha256": sha256_file(dat_path),
            "sign": "applied load F in global axes, Z up; equilibrium needs stored reaction R = -F",
            "load_cases": out, "not_expected": notexp, "combinations": combos, "selfweight_lcs": [1],
            "combination_factors": cf}


def main():
    ap = Parser(TOOL, description="expected.json for 26016 from the generator",
                formatter_class=__import__("argparse").RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("dat")
    ap.add_argument("out")
    ap.add_argument("--generator", default=GEN)
    ap.add_argument("--params", default="default", choices=("default", "legacy"))
    ap.add_argument("--workdir")
    a = ap.parse_args()
    rep = Report(TOOL, a.workdir, {"dat": input_record(a.dat, "dat")})
    e = build(a.dat, a.generator, a.params)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(e, f, indent=1)
    rep.check("expected_written", "PASS", out=os.path.abspath(a.out), load_cases=len(e["load_cases"]),
              not_expected=sorted(e["not_expected"], key=int), combinations=len(e["combinations"]))
    for k in ("2", "11", "21", "81", "501"):
        if k in e["load_cases"]:
            rep.note(f"LC {k}: F = {e['load_cases'][k]['F_kN']} kN, gross {e['load_cases'][k]['gross_kN']} kN")
    rep.emit()


if __name__ == "__main__":
    run_main(TOOL, main)
