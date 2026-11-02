"""Run the member check:  SOFiSTiK model + forces  ->  chosen design code  ->  tables (+ comparison with BDK/AQB).

    python -m memcheck.run --dat model.dat --forces forces.csv.gz --out results/ [--erg model.erg]
                           [--code EN1993] [--grade S275] [--lcs 101-154] [--overrides members_input.csv]

overrides CSV (optional, one row per member id, blank = default): id, Ly_mode, k_y, k_z, k_LT, zg_mm, c1_method,
mcr_method,
torsion_restrained, lt_at_lateral.  This is where the engineer changes effective lengths and restraint assumptions.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time

from . import members as M
from . import sofistik as S
from .codes.base import get_code


def parse_lcs(spec):
    if not spec:
        return None
    out = set()
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        elif part.strip():
            out.add(int(part))
    return out


def load_overrides(path, members):
    if not path or not os.path.exists(path):
        return
    by = {m.id: m for m in members}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            m = by.get(int(r["id"]))
            if not m:
                continue
            d = m.design
            if r.get("lt_at_lateral", "").strip():
                d.lt_at_lateral = r["lt_at_lateral"].strip().lower() in ("1", "yes", "true", "y")
            for k, typ in (("Ly_mode", str), ("k_y", float), ("k_z", float), ("k_LT", float), ("zg_mm", float),
                           ("c1_method", str), ("mcr_method", str)):
                if r.get(k, "").strip():
                    setattr(d, k, typ(r[k]))
            if r.get("torsion_restrained", "").strip():
                d.torsion_restrained = r["torsion_restrained"].strip().lower() in ("1", "yes", "true", "y")


def run(dat, forces, out, code="EN1993", grade="S275", lcs=None, erg=None, overrides=None, settings=None,
        only=None, quiet=False, beam_pos=None):
    t0 = time.time()
    os.makedirs(out, exist_ok=True)
    sections, slns, sto = S.read_dat(dat)
    bdk = S.read_bdk_members(dat, sto)
    F = S.read_forces(forces, parse_lcs(lcs) if isinstance(lcs, str) else lcs)
    if beam_pos:
        bp = {int(k): v for k, v in json.load(open(beam_pos)).items()}
        F = S.remap_forces(F, bp, slns)
    lc_list = sorted(F)
    beam_slns = {s for lc in F for s in F[lc] if s is not None}
    mems = M.build_members(bdk, slns, sections, extra_slns=sorted(beam_slns))
    if only:
        mems = [m for m in mems if m.id in only]
    load_overrides(overrides, mems)
    dc = get_code(code)
    if settings is not None:
        dc.st = settings
    results = []
    for m in mems:
        sname = sections[m.section_no]["name"]
        sec = dc.section(sname)
        best = {}       # label -> (util, lc, s, clause, details)
        for lc in lc_list:
            rows = M.diagrams(m, F[lc])
            if not rows:
                continue
            for r in rows:
                for c in dc.station_checks(sec, grade, r[1], r[2], r[3], r[4], r[5], r[6]):
                    key = c.label.replace(" + torsion", "")
                    if key not in best or c.util > best[key][0]:
                        best[key] = (c.util, lc, r[0], c.clause, {})
            for seg in m.segments("LT"):
                a, b = seg
                sr = [r for r in rows if a - 1e-4 <= r[0] <= b + 1e-4]
                if len(sr) < 2:
                    continue
                for c in dc.segment_checks(sec, grade, m, seg, sr, rows):
                    if c.label not in best or c.util > best[c.label][0]:
                        best[c.label] = (c.util, lc, 0.5 * (a + b), c.clause, c.details)
        if not best:
            continue
        gov_label = max(best, key=lambda k: best[k][0])
        u, lc, s, cl, det = best[gov_label]
        results.append(dict(id=m.id, slns=m.slns, group=m.group, section=sname, length=round(m.length, 3),
                            n_segments=len(m.segments("LT")), restraints=[(round(a, 3), k) for a, k, _ in m.restraints],
                            comment=m.comment, governing=gov_label, util=u, lc=lc, s=round(s, 3), clause=cl,
                            checks={k: (round(v[0], 4), v[1], round(v[2], 3)) for k, v in best.items()},
                            details={k: (round(x, 4) if isinstance(x, float) else x) for k, x in
                                     best.get("Bending + compression, eq. 6.62", (0, 0, 0, 0, {}))[4].items()},
                            design=vars(m.design)))
    # comparison
    bdk_res = S.read_bdk_summary(erg) if erg else {}
    aqb = S.read_aqb_maxima(erg) if erg else {}
    for r in results:
        b = bdk_res.get(r["id"])
        if b:
            r["bdk"] = max(b["nmy"], b["nmz"])
            r["bdk_lc"] = b["lc"]
            mine = max(r["checks"].get("Bending + compression, eq. 6.61", (0,))[0],
                       r["checks"].get("Bending + compression, eq. 6.62", (0,))[0])
            r["mine_6361"] = mine
    _write(out, results, dc, lc_list, aqb, sections)
    if not quiet:
        print(f"{len(results)} members, {len(lc_list)} load cases, {time.time() - t0:.1f} s -> {out}")
    return results


def _write(out, results, dc, lc_list, aqb, sections):
    labels = []
    for r in results:
        for k in r["checks"]:
            if k not in labels:
                labels.append(k)
    with open(os.path.join(out, "members.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["member", "lines", "group", "section", "L (m)", "segments", "governing check", "clause",
                    "utilisation", "LC", "s (m)", "BDK 6.61/6.62", "BDK LC", "this 6.61/6.62", "comment"])
        for r in sorted(results, key=lambda r: -r["util"]):
            w.writerow([r["id"], "+".join(map(str, r["slns"])), r["group"], r["section"], r["length"], r["n_segments"],
                        r["governing"], r["clause"], round(r["util"], 3), r["lc"], r["s"], r.get("bdk", ""),
                        r.get("bdk_lc", ""), round(r.get("mine_6361", 0), 3) if "bdk" in r else "", r["comment"]])
    with open(os.path.join(out, "checks.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["member", "section"] + [x for k in labels for x in (k, "LC")])
        for r in sorted(results, key=lambda r: r["id"]):
            w.writerow([r["id"], r["section"]] + [x for k in labels for x in
                                                  ((r["checks"][k][0], r["checks"][k][1]) if k in r["checks"] else ("", ""))])
    meta = dict(code=dc.name, settings=vars(getattr(dc, "st", None)) if getattr(dc, "st", None) else {},
                load_cases=lc_list, aqb_section_maxima=aqb,
                sections={k: v["name"] for k, v in sections.items()})
    json.dump(dict(meta=meta, members=results), open(os.path.join(out, "results.json"), "w"), indent=1, default=str)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dat", required=True)
    ap.add_argument("--forces", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--erg")
    ap.add_argument("--code", default="EN1993")
    ap.add_argument("--grade", default="S275")
    ap.add_argument("--lcs")
    ap.add_argument("--overrides")
    ap.add_argument("--beam-pos", help="beam positions JSON (make_beam_pos.py), needed where SOFiMSHC split lines")
    a = ap.parse_args(argv)
    run(a.dat, a.forces, a.out, a.code, a.grade, a.lcs, a.erg, a.overrides, beam_pos=a.beam_pos)


if __name__ == "__main__":
    main()
