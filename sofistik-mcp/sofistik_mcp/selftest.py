"""Self-test on this PC: solve a cantilever with SOFiSTiK through the server's own code, read the .cdb
through the server's worker, and compare with a hand calculation.  Then start the MCP server the way
Claude does and check that it answers.

    python -m sofistik_mcp.selftest          (selftest.bat does this)

Writes selftest\\selftest_report.txt.  Every check prints PASS or FAIL with the numbers.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import time
import traceback
from typing import Any

from . import config, install, solver
from . import server as srv

ROOT = config.ROOT
RUN_DIR = os.path.join(ROOT, "selftest", "run")

P = 1.0          # kN tip load, LC 1 (LC 2: P2)
P2 = 2.0         # kN tip load, LC 2
L = 6.0          # m
N_BEAMS = 6      # beams 1..6, each L / 6 long, numbered from the support (node 1) to the tip (node 7)
TABLE = {"A_cm2": 53.8, "Iy_cm4": 3692.0}   # HEA 200, Euronorm 53-62 tables
E_EXPECT = 2.1e8                            # kN/m2 (210 000 N/mm2)
LC_TITLES = {1: "self-test tip load 1 kN", 2: "self-test tip load 2 kN"}   # as in selftest_cantilever.dat
SLN_MODEL = ((7, 3, 1.0), (8, 4, 2.0))      # selftest_sln.dat: (structural line, group, w [kN/m])

lines: list[str] = []
fails = 0


def out(msg=""):
    print(msg, flush=True)
    lines.append(msg)


def check(name, ok, detail):
    global fails
    if not ok:
        fails += 1
    out(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def info(name, detail):
    """A line printed for the record that is not a check (never counted as FAIL)."""
    out(f"  [INFO] {name}: {detail}")


def close(a, b, rel):
    return a is not None and b is not None and abs(abs(a) - abs(b)) <= rel * abs(b)


def absmax(ext, comp):
    """(|value|, extreme) of the larger of max / min of comp in an 'extremes' / 'overall' dict."""
    e = ext.get(comp) or {}
    cands = [x for x in (e.get("max"), e.get("min")) if x and x.get("value") is not None]
    if not cands:
        return 0.0, {}
    best = max(cands, key=lambda x: abs(x["value"]))
    return abs(best["value"]), best


def sign(v):
    return 0 if not v else (1 if v > 0 else -1)


def _caller(cdb):
    return lambda op, args: srv._cdb_call(op, cdb, args)


def run_checks():
    out("SOFiSTiK MCP self-test")
    out(f"  Python {sys.version.split()[0]}  ({sys.executable})")
    s = config.load_settings()
    out(f"  settings: {s.get('_path') or 'defaults'}")
    try:
        sofi = install.find(s)
    except install.SofistikNotFound as e:
        check("SOFiSTiK found", False, str(e))
        return
    check("SOFiSTiK found", bool(sofi["sps"]), f"sps.exe = {sofi['sps']}")
    check("CDB interface found", bool(sofi["dll"] and sofi["daten"]), f"{sofi['dll']} ; {sofi['daten']}")
    if not sofi["sps"] or not sofi["dll"]:
        return
    if not config.is_inside(RUN_DIR, s["work_folders"]):
        check("self-test folder is a work folder", False,
              f"{RUN_DIR} is not inside work_folders {s['work_folders']}; add it to settings.json")
        return

    out("\n1. Calculation with sps.exe (usually seconds; up to 10 minutes if the licence check is slow)")
    cdb = solve(sofi, "selftest_cantilever.dat")
    if not cdb:
        return
    props = cantilever_checks(_caller(cdb))
    if props:
        sln_checks(sofi, *props)


def cantilever_checks(call):
    """Sections 2 and 3 on the solved selftest_cantilever.dat.  call(op, args) reads the .cdb the way
    the server does.  Returns (E, G, Iy, Az) for the structural line model, or None."""
    out("\n2. Reading the .cdb (worker process)")
    t0 = time.monotonic()
    ov = call("overview", {})
    t_ov = time.monotonic() - t0
    if ov.get("error"):
        check("read overview", False, ov["error"] + ("\n" + ov.get("traceback", "")))
        return None
    t0 = time.monotonic()
    lc_list = call("load_cases", {})
    t_lc = time.monotonic() - t0
    lc_rows = lc_list if isinstance(lc_list, list) else lc_list.get("rows")  # server wraps lists in {"rows": ...}
    # both look for load case keys 12/1 ... 12/999999 (results.MAX_LC) through SOFiSTiK's DLL
    info("time to read", f"overview {t_ov:.1f} s, load_cases {t_lc:.1f} s "
         f"({len(lc_rows) if isinstance(lc_rows, list) else lc_list.get('error', '?')} load cases)")
    cnt = ov["element_counts"]
    check("element counts", cnt["nodes"] == 7 and cnt["beams"] == 6, f"{cnt['nodes']} nodes, {cnt['beams']} beams")
    sec = next((x for x in ov["sections"] if x["nr"] == 1), None)
    if not sec:
        check("section 1 present", False, str(ov["sections"])[:300])
        return None
    out(f"  section 1: '{sec['title']}' A {sec['A_cm2']} cm2, Iy {sec['Iy_cm4']} cm4, Iz {sec['Iz_cm4']} cm4")
    check("section area (units m2 -> cm2)", close(sec["A_cm2"], TABLE["A_cm2"], 0.03),
          f"{sec['A_cm2']} cm2 vs table {TABLE['A_cm2']}")
    check("section Iy (units m4 -> cm4)", close(sec["Iy_cm4"], TABLE["Iy_cm4"], 0.03),
          f"{sec['Iy_cm4']} cm4 vs table {TABLE['Iy_cm4']}")
    lcs = {x["lc"]: x for x in ov["load_cases"]}
    for lc in (1, 2):
        x: Any = lcs.get(lc)
        check(f"load case {lc} present with node and beam results",
              bool(x) and "nodes" in x["has_results"] and "beams" in x["has_results"], str(x))
        # ASE may replace SOFiLOAD's title (ase_1.pdf p. 3-86 is not clear), so this is for the record only
        title = (x or {}).get("title")
        info(f"load case {lc} title read back", f"'{title}' vs '{LC_TITLES[lc]}' written in SOFiLOAD"
             + (" (same)" if title == LC_TITLES[lc] else " (different: ASE may have replaced it)"))

    raw = call("read_key", {"kwh": 9, "kwl": 1, "class_name": "CSECT", "max_records": 50})
    cs: dict = next((x for x in raw.get("records", []) if x.get("m_id") == 0), {})
    mat = call("read_key", {"kwh": 1, "kwl": 1, "class_name": "CMAT_STEE", "max_records": 50})
    ms: dict = next((x for x in mat.get("records", []) if x.get("m_id") == 1), {})
    E = ms.get("m_emod") or cs.get("m_em")
    G = ms.get("m_gmod") or cs.get("m_gm")
    Iy, Iz, Az = cs.get("m_iy"), cs.get("m_iz"), cs.get("m_az")
    out(f"  raw CDB values: E {E} kN/m2, G {G} kN/m2, Iy {Iy} m4, Iz {Iz} m4, Az {Az} m2")
    check("E modulus stored in kN/m2", close(E, E_EXPECT, 0.01), f"{E} vs {E_EXPECT}")
    if not (E and Iy):
        return None

    out("\n3. Results against the hand calculation")
    observed: list[str] = []
    d_bend = P * L ** 3 / (3 * E * Iy) * 1000                       # mm
    d_shear = (P * L / (G * Az) * 1000) if (G and Az) else 0.0
    rot = P * L ** 2 / (2 * E * Iy) * 1000                           # mrad (shear does not rotate the section)
    out(f"  expected tip deflection: bending {d_bend:.4f} mm + shear {d_shear:.4f} mm = {d_bend + d_shear:.4f} mm")
    nr = call("node_results", {"lc": 1, "ids": "7"})
    tip = (nr.get("rows") or [{}])[0]
    out(f"  node 7: ux {tip.get('ux')} uy {tip.get('uy')} uz {tip.get('uz')} mm, ury {tip.get('ury')} mrad")
    uz = tip.get("uz")
    ok = close(uz, d_bend + d_shear, 0.01) or close(uz, d_bend, 0.01)
    check("tip deflection (units m -> mm)", ok, f"{uz} mm vs {d_bend + d_shear:.4f} mm (bending only {d_bend:.4f})")
    if not ok and Iz:
        out(f"    (bending about the weak axis would give {P * L ** 3 / (3 * E * Iz) * 1000:.3f} mm)")
    check("no sideways deflection",
          abs(tip.get("uy") or 0) < 1e-3 * abs(uz or 1) and abs(tip.get("ux") or 0) < 1e-3 * abs(uz or 1),
          f"ux {tip.get('ux')}, uy {tip.get('uy')}")
    # NODE 7 TYPE PZZ +1 kN is a load in global +Z: the tip should move in +Z.  Signs are recorded, not checked:
    # the server passes SOFiSTiK's values on unchanged, so a sign is a convention to document, not a reading error.
    info("tip moves in the direction of the load (global +Z)", f"uz {uz} mm for a load in +Z: "
         + ("yes" if (uz or 0) > 0 else "NO, the sign is opposite to the load"))
    ury = tip.get("ury")
    check("tip rotation = P L^2 / (2 E Iy) (units rad -> mrad)", close(ury, rot, 0.01), f"|{ury}| mrad vs {rot:.4f}")
    observed.append(f"tip rotation ury = {ury} mrad for a deflection in +Z of a beam along +X "
                    "(the right-hand rule about +Y predicts a negative value)")

    sr = call("support_reactions", {"lc": 1})
    rows = sr.get("rows") or []
    sup: dict = next((x for x in rows if x["node"] == 1), {})
    out(f"  support node 1: px {sup.get('px')} py {sup.get('py')} pz {sup.get('pz')} kN, "
        f"mx {sup.get('mx')} my {sup.get('my')} mz {sup.get('mz')} kNm")
    check("support reaction = P", close(sup.get("pz"), P, 0.005), f"{sup.get('pz')} kN vs {P}")
    check("support moment = P L", close(sup.get("my"), P * L, 0.005), f"{sup.get('my')} kNm vs {P * L}")
    check("only node 1 carries reactions", [x["node"] for x in rows] == [1], str([x["node"] for x in rows]))
    stored: Any = sr.get("sum_stored_by_sofistik_kN")
    out(f"  sum of reactions stored by SOFiSTiK: {stored}")
    check("SOFiSTiK's stored reaction sum = P", bool(stored) and close(stored[2], P, 0.005), str(stored))
    if stored and sup.get("pz"):
        info("stored reaction sum and support node reaction have the same sign",
             f"sum {stored[2]} kN, node 1 pz {sup.get('pz')} kN: "
             + ("same sign" if sign(stored[2]) == sign(sup.get("pz")) else "OPPOSITE signs"))
    pz = sup.get("pz") or 0
    observed.append(f"support pz = {sup.get('pz')} kN, my = {sup.get('my')} kNm for a load of +{P} kN in global +Z, "
                    "so SOFiSTiK reports support reactions as "
                    + ("the force the structure puts on the support (same sign as the load)" if pz > 0 else
                       "the force the support puts on the structure (opposite sign to the load)" if pz < 0 else
                       "zero (unexpected)"))
    observed.append(f"stored reaction sum (12/LC CLC_CTRL m_rz) = {stored[2] if stored else None} kN")

    bf = call("beam_forces", {"lc": 1})
    ext = bf.get("extremes", {})
    my = ext.get("My", {})
    mmax, _ = absmax(ext, "My")
    vmax, _ = absmax(ext, "Vz")
    out(f"  beam forces: {bf.get('beams')} beams, {bf.get('stations')} stations; "
        f"max |My| {mmax} kNm, max |Vz| {vmax} kN")
    out(f"    My extremes {my}")
    check("max beam moment = P L", close(mmax, P * L, 0.005), f"{mmax} kNm vs {P * L}")
    check("beam shear = P", close(vmax, P, 0.005), f"{vmax} kN vs {P}")
    brows = bf.get("rows", [])
    for comp in ("N", "Vy", "Mt", "Mz"):
        worst = max((abs(r.get(comp) or 0) for r in brows), default=0.0)   # None (undefined) counts as 0
        check(f"{comp} = 0 everywhere", bool(brows) and worst <= 1e-3 * P, f"max |{comp}| {worst}")
    seg = L / N_BEAMS
    at_tip = [r for r in brows if r["beam"] == N_BEAMS and r["x"] is not None and abs(r["x"] - seg) < 1e-3]
    check("moment is zero at the free end", bool(at_tip) and all(abs(r["My"] or 0) < 1e-3 for r in at_tip),
          f"My at beam {N_BEAMS} x = {seg} m: {[r['My'] for r in at_tip]}")
    bad = [(r["beam"], r["x"], r["My"]) for r in brows
           if r["x"] is None or r["My"] is None
           or abs(abs(r["My"]) - P * (L - ((r["beam"] - 1) * seg + r["x"]))) > 0.005 * P * L]
    signs = {sign(r["My"]) for r in brows if r["My"] and abs(r["My"]) > 1e-3}
    check("|My| grows linearly from the free end to the support (|My| = P (L - x))",
          bool(brows) and not bad and len(signs) <= 1, f"{len(brows)} stations, off: {bad[:5]}, signs {signs}")
    my_sup = next((r["My"] for r in brows if r["beam"] == 1 and r["x"] == 0), None)
    observed.append(f"beam My at the support = {my_sup} kNm (hogging moment of a cantilever under +Z load)")
    gr0 = call("beam_forces", {"lc": 1, "groups": "0"})
    gr1 = call("beam_forces", {"lc": 1, "groups": "1"})
    check("group filter: group 0 (GDIV 1000, beams 1-6) has all beams, group 1 none",
          gr0.get("beams") == 6 and gr1.get("beams") == 0, f"group 0: {gr0.get('beams')}, group 1: {gr1.get('beams')}")

    env = call("envelope", {"lcs": "1-2", "what": "beam"})
    e_my, e_best = absmax(env.get("overall", {}), "My")
    check("envelope LC 1-2: both load cases used", env.get("load_cases_found") == [1, 2],
          str(env.get("load_cases_found")))
    check("envelope LC 1-2: max |My| = 2 P L from LC 2", e_best.get("lc") == 2 and close(e_my, P2 * L, 0.005),
          f"{e_my} kNm from LC {e_best.get('lc')} vs {P2 * L} from LC 2")
    env_n = call("envelope", {"lcs": "1-2", "what": "node"})
    e_uz, n_best = absmax(env_n.get("overall", {}), "uz")
    check("envelope LC 1-2: max |uz| = 2 x tip deflection from LC 2, node 7",
          n_best.get("lc") == 2 and n_best.get("node") == 7 and close(e_uz, 2 * (uz or 0), 0.005),
          f"{e_uz} mm at node {n_best.get('node')} from LC {n_best.get('lc')} vs {2 * (uz or 0):.4f}")
    out("  (the shear part is about 0.4 % of the deflection, inside the 1 % tolerance, so this test does not")
    out("   tell whether SOFiSTiK includes shear deformation; it does check the units and the axis)")
    out("  Observed signs (for documenting SOFiSTiK's conventions; not checked against a convention):")
    for o in observed:
        out(f"    observed: {o}")
    return E, G, Iy, Az


def report_run(name, r):
    """What the calculation returned, including the facts not yet known for SOFiSTiK 2027: sps.exe's exit
    code on a clean run and whether every program prints its "n errors and m warnings" totals line."""
    out(f"  {name}: command {r.get('command')}")
    out(f"  exit code {r.get('exit_code')}, {r.get('seconds')} s, status '{r.get('status')}', "
        f"{r.get('errors')} errors, {r.get('warnings')} warnings")
    progs = r.get("programs") or []
    info("sps.exe exit code", f"{r.get('exit_code')} (SOFiSTiK does not document sps.exe's exit codes)")
    info("'n errors and m warnings' totals line per program",
         ", ".join(f"{p['program']} {'yes' if p.get('errors') is not None else 'NO'}" for p in progs) or "no programs")
    for wmsg in r.get("server_warnings", []):
        out(f"  warning: {wmsg}")
    for note in r.get("notes", []):
        out(f"  note: {note}")


def solve(sofi, name):
    os.makedirs(RUN_DIR, exist_ok=True)
    dat = os.path.join(RUN_DIR, name)
    for ext in (".cdb", ".prt", ".erg", ".plb", ".lst"):
        p = os.path.splitext(dat)[0] + ext
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    shutil.copyfile(os.path.join(ROOT, "selftest", name), dat)
    r = solver.run(dat, sofi["sps"], 600)
    report_run(name, r)
    for m in r.get("messages", [])[:10]:
        out(f"    {m['kind']} {m['number']} ({m['program']}): {m['text']}")
        erg_m: dict = next((e for e in r.get("erg_messages", []) if e["number"] == m["number"]), {})
        for ln in erg_m.get("input_before", [])[-3:]:
            out(f"       input: {ln}")
    if r.get("reason"):
        out(f"  {r['reason']}")
    check(f"{name} calculated without errors", r.get("status") in ("ok", "ok with warnings"),
          f"status {r.get('status')}")
    cdb = os.path.splitext(dat)[0] + ".cdb"
    check(f"{name}: .cdb written", os.path.isfile(cdb), cdb)
    return cdb if os.path.isfile(cdb) else None


def sln_checks(sofi, E, G, Iy, Az):
    """Second model built from two structural lines: are beams found by SLN number and group?"""
    out("\n4. Structural line model (SOFiMSHC: SLN 7 in group 3 with 1 kN/m, SLN 8 in group 4 with 2 kN/m)")
    cdb = solve(sofi, "selftest_sln.dat")
    if not cdb:
        return
    sln_result_checks(_caller(cdb), E, G, Iy, Az)
    group_rule_checks(_caller(cdb))


def sln_result_checks(call, E, G, Iy, Az):
    bf = call("beam_forces", {"lc": 1})
    if bf.get("error"):
        check("read beam forces", False, bf["error"])
        return
    rows = bf.get("rows", [])
    slns = sorted({r["sln"] for r in rows}, key=lambda v: (v is None, v))
    grps = sorted({str(r["group"]) for r in rows})
    out(f"  {bf.get('beams')} beams; structural line numbers seen: {slns}; groups seen: {grps}")
    check("beams know their structural line (m_nref = SLN 7 and 8)", slns == [7, 8], f"{slns}")
    total_w = 0.0
    for sln, grp, w in SLN_MODEL:
        total_w += w
        mine = {r["beam"] for r in rows if r["sln"] == sln}
        out(f"  SLN {sln}: beams {sorted(mine)}")
        by_sln = call("beam_forces", {"lc": 1, "slns": str(sln)})
        got = {r["beam"] for r in by_sln.get("rows", [])}
        check(f"filter by structural line {sln} returns exactly its beams", len(mine) >= 6 and got == mine,
              f"{len(got)} beams {sorted(got)[:12]} vs {len(mine)} on SLN {sln}")
        by_grp = call("beam_forces", {"lc": 1, "groups": str(grp)})
        got_g = {r["beam"] for r in by_grp.get("rows", [])}
        check(f"filter by group {grp} returns exactly the beams of SLN {sln}", len(mine) >= 6 and got_g == mine,
              f"{len(got_g)} beams {sorted(got_g)[:12]}; other lines' beams included: {sorted(got_g - mine)[:12]}"
              + (f"; warning: {by_grp['warning']}" if by_grp.get("warning") else ""))
        mmax, _ = absmax(by_grp.get("extremes", {}), "My")
        check(f"group {grp}: fixed-end moment = w L^2 / 2 with w = {w} kN/m", close(mmax, w * L * L / 2, 0.005),
              f"{mmax} kNm vs {w * L * L / 2}")
    sr = call("support_reactions", {"lc": 1})
    pz = (sr.get("sum_kN") or {}).get("pz")
    check("sum of reactions = (w7 + w8) L", close(pz, total_w * L, 0.005), f"{pz} kN vs {total_w * L}")
    nr = call("node_results", {"lc": 1})
    umax, _ = absmax(nr.get("extremes", {}), "uz")
    w = max(x[2] for x in SLN_MODEL)
    d_b = w * L ** 4 / (8 * E * Iy) * 1000
    d_s = (w * L * L / (2 * G * Az) * 1000) if (G and Az) else 0.0
    check(f"largest tip deflection = w L^4 / 8EI with w = {w} kN/m (SLN 8)",
          close(umax, d_b + d_s, 0.01) or close(umax, d_b, 0.01),
          f"{umax} mm vs {d_b + d_s:.4f} mm (bending only {d_b:.4f})")


def group_rule_checks(call):
    """The three ways the server can tell a beam's group (results._group_of), each on its own: 1. element
    number // GDIV, 2. the group of the beam's structural line (39/NR CSLN_BEAM m_nog via CBEAM m_nref),
    3. the one beam group whose 11/00 CGRP element range holds the beam.  The server uses rule 1 here
    (GDIV 1000), so rules 2 and 3 are otherwise never tried on a real .cdb."""
    out("\n   Group rules on this .cdb, each on its own (rule 1 GDIV, 2 structural line, 3 CGRP range)")
    gr = call("group_rules", {})
    if gr.get("error"):
        check("read the group rules", False, gr["error"])
        return
    cgrp = gr.get("cgrp") or []
    out("  CGRP (11/00): " + ("; ".join(f"group {g['group']} m_typ {g['element_code']} elements {g['min_element']}-"
                                        f"{g['max_element']} ({g['count']})" for g in cgrp) or "no records"))
    info("raw CGRP m_typ values", f"{sorted({g['element_code'] for g in cgrp})} (read as beam groups: "
         f"{gr.get('beam_element_codes')})")
    beams = gr.get("beams") or []
    out(f"  GDIV {gr.get('group_divisor')}, {len(beams)} beams")
    check("rule 1 (GDIV) gives every beam a group", bool(beams) and all(b["rule1_gdiv"] is not None for b in beams),
          f"{sum(b['rule1_gdiv'] is not None for b in beams)} of {len(beams)} beams")
    for key, name in (("rule2_sln", "rule 2 (structural line, CSLN_BEAM m_nog)"),
                      ("rule3_range", "rule 3 (the one beam group whose CGRP range holds the beam)")):
        have = [b for b in beams if b[key] is not None]
        if not have:
            info(name, "gives no group for any beam of this .cdb, so it cannot be compared")
            continue
        off = [(b["beam"], b["rule1_gdiv"], b[key]) for b in have if b[key] != b["rule1_gdiv"]]
        check(f"{name} agrees with rule 1", not off,
              f"{len(have)} beams compared; (beam, rule 1, this rule) that differ: {off[:12]}")
        if len(have) < len(beams):
            info(name, f"no group for {len(beams) - len(have)} beam(s): "
                       f"{[b['beam'] for b in beams if b[key] is None][:20]}")


async def mcp_smoke():
    """Start run_server.py exactly as Claude does (stdio) and call two tools."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=sys.executable, args=[os.path.join(ROOT, "run_server.py")])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as sess:
            await sess.initialize()
            tools = (await sess.list_tools()).tools
            st = await sess.call_tool("sofistik_status", {})
            return [t.name for t in tools], st.isError


def main():
    try:
        run_checks()
    except Exception:
        check("self-test ran", False, traceback.format_exc())
    out("\n5. MCP server answers like it will for Claude")
    try:
        names, is_err = asyncio.run(asyncio.wait_for(mcp_smoke(), 120))
        check("server starts and lists tools", len(names) >= 15, f"{len(names)} tools: {', '.join(names)}")
        check("sofistik_status tool works", not is_err, "ok" if not is_err else "returned an error")
    except Exception as e:
        check("server starts and lists tools", False, f"{type(e).__name__}: {e}")
    out("")
    out("RESULT: " + ("ALL CHECKS PASSED" if fails == 0 else f"{fails} CHECK(S) FAILED"))
    rep = os.path.join(ROOT, "selftest", "selftest_report.txt")
    with open(rep, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nReport saved to {rep}")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
