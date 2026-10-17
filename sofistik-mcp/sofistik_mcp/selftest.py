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
import traceback
from typing import Any

from . import config, install, solver
from . import server as srv

ROOT = config.ROOT
RUN_DIR = os.path.join(ROOT, "selftest", "run")

P = 1.0          # kN tip load
L = 6.0          # m
TABLE = {"A_cm2": 53.8, "Iy_cm4": 3692.0}   # HEA 200, Euronorm 53-62 tables
E_EXPECT = 2.1e8                            # kN/m2 (210 000 N/mm2)

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


def close(a, b, rel):
    return a is not None and b is not None and abs(abs(a) - abs(b)) <= rel * abs(b)


def run_checks():
    out("SOFiSTiK MCP self-test")
    out(f"  Python {sys.version.split()[0]}  ({sys.executable})")
    s = config.load_settings()
    out(f"  settings: {s.get('_path') or 'defaults'}")
    try:
        info = install.find(s)
    except install.SofistikNotFound as e:
        check("SOFiSTiK found", False, str(e))
        return
    check("SOFiSTiK found", bool(info["sps"]), f"sps.exe = {info['sps']}")
    check("CDB interface found", bool(info["dll"] and info["daten"]), f"{info['dll']} ; {info['daten']}")
    if not info["sps"] or not info["dll"]:
        return
    if not config.is_inside(RUN_DIR, s["work_folders"]):
        check("self-test folder is a work folder", False,
              f"{RUN_DIR} is not inside work_folders {s['work_folders']}; add it to settings.json")
        return

    out("\n1. Calculation with sps.exe (usually seconds; up to 10 minutes if the licence check is slow)")
    cdb = solve(info, "selftest_cantilever.dat")
    if not cdb:
        return

    out("\n2. Reading the .cdb (worker process)")
    ov = srv._cdb_call("overview", cdb, {})
    if ov.get("error"):
        check("read overview", False, ov["error"] + ("\n" + ov.get("traceback", "")))
        return
    cnt = ov["element_counts"]
    check("element counts", cnt["nodes"] == 7 and cnt["beams"] == 6, f"{cnt['nodes']} nodes, {cnt['beams']} beams")
    sec = next((x for x in ov["sections"] if x["nr"] == 1), None)
    if not sec:
        check("section 1 present", False, str(ov["sections"])[:300])
        return
    out(f"  section 1: '{sec['title']}' A {sec['A_cm2']} cm2, Iy {sec['Iy_cm4']} cm4, Iz {sec['Iz_cm4']} cm4")
    check("section area (units m2 -> cm2)", close(sec["A_cm2"], TABLE["A_cm2"], 0.03),
          f"{sec['A_cm2']} cm2 vs table {TABLE['A_cm2']}")
    check("section Iy (units m4 -> cm4)", close(sec["Iy_cm4"], TABLE["Iy_cm4"], 0.03),
          f"{sec['Iy_cm4']} cm4 vs table {TABLE['Iy_cm4']}")
    lc1: Any = next((x for x in ov["load_cases"] if x["lc"] == 1), None)
    check("load case 1 present with node and beam results",
          bool(lc1) and "nodes" in lc1["has_results"] and "beams" in lc1["has_results"], str(lc1))

    raw = srv._cdb_call("read_key", cdb, {"kwh": 9, "kwl": 1, "class_name": "CSECT", "max_records": 50})
    cs: dict = next((x for x in raw.get("records", []) if x.get("m_id") == 0), {})
    mat = srv._cdb_call("read_key", cdb, {"kwh": 1, "kwl": 1, "class_name": "CMAT_STEE", "max_records": 50})
    ms: dict = next((x for x in mat.get("records", []) if x.get("m_id") == 1), {})
    E = ms.get("m_emod") or cs.get("m_em")
    G = ms.get("m_gmod") or cs.get("m_gm")
    Iy, Iz, Az = cs.get("m_iy"), cs.get("m_iz"), cs.get("m_az")
    out(f"  raw CDB values: E {E} kN/m2, G {G} kN/m2, Iy {Iy} m4, Iz {Iz} m4, Az {Az} m2")
    check("E modulus stored in kN/m2", close(E, E_EXPECT, 0.01), f"{E} vs {E_EXPECT}")
    if not (E and Iy):
        return

    out("\n3. Results against the hand calculation")
    d_bend = P * L ** 3 / (3 * E * Iy) * 1000                       # mm
    d_shear = (P * L / (G * Az) * 1000) if (G and Az) else 0.0
    out(f"  expected tip deflection: bending {d_bend:.4f} mm + shear {d_shear:.4f} mm = {d_bend + d_shear:.4f} mm")
    nr = srv._cdb_call("node_results", cdb, {"lc": 1, "ids": "7"})
    tip = (nr.get("rows") or [{}])[0]
    out(f"  node 7: ux {tip.get('ux')} uy {tip.get('uy')} uz {tip.get('uz')} mm")
    uz = tip.get("uz")
    ok = close(uz, d_bend + d_shear, 0.01) or close(uz, d_bend, 0.01)
    check("tip deflection (units m -> mm)", ok, f"{uz} mm vs {d_bend + d_shear:.4f} mm (bending only {d_bend:.4f})")
    if not ok and Iz:
        out(f"    (bending about the weak axis would give {P * L ** 3 / (3 * E * Iz) * 1000:.3f} mm)")
    check("no sideways deflection",
          abs(tip.get("uy") or 0) < 1e-3 * abs(uz or 1) and abs(tip.get("ux") or 0) < 1e-3 * abs(uz or 1),
          f"ux {tip.get('ux')}, uy {tip.get('uy')}")
    sr = srv._cdb_call("support_reactions", cdb, {"lc": 1})
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
    bf = srv._cdb_call("beam_forces", cdb, {"lc": 1})
    ext = bf.get("extremes", {})
    my = ext.get("My", {})
    vz = ext.get("Vz", {})
    mmax = max(abs(my.get("max", {}).get("value") or 0), abs(my.get("min", {}).get("value") or 0))
    vmax = max(abs(vz.get("max", {}).get("value") or 0), abs(vz.get("min", {}).get("value") or 0))
    out(f"  beam forces: {bf.get('beams')} beams, {bf.get('stations')} stations; "
        f"max |My| {mmax} kNm, max |Vz| {vmax} kN")
    out(f"    My extremes {my}")
    check("max beam moment = P L", close(mmax, P * L, 0.005), f"{mmax} kNm vs {P * L}")
    check("beam shear = P", close(vmax, P, 0.005), f"{vmax} kN vs {P}")
    at_tip = [r for r in bf.get("rows", []) if r["My"] is not None and abs(r["My"]) < 1e-3]
    check("moment is zero at the free end", bool(at_tip), f"{len(at_tip)} station(s) with My = 0")
    out("  (the shear part is about 0.4 % of the deflection, inside the 1 % tolerance, so this test does not")
    out("   tell whether SOFiSTiK includes shear deformation; it does check the units and the axis)")
    sln_checks(info, E, G, Iy, Az)


def solve(info, name):
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
    r = solver.run(dat, info["sps"], 600)
    out(f"  {name}: command {r.get('command')}")
    out(f"  exit code {r.get('exit_code')}, {r.get('seconds')} s, status '{r.get('status')}', "
        f"{r.get('errors')} errors, {r.get('warnings')} warnings")
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


def sln_checks(info, E, G, Iy, Az):
    """Second model built from a structural line: are beams found by SLN number and group?"""
    w = 1.0
    out("\n4. Structural line model (SOFiMSHC, SLN 7, group 3, 1 kN/m)")
    cdb = solve(info, "selftest_sln.dat")
    if not cdb:
        return
    bf = srv._cdb_call("beam_forces", cdb, {"lc": 1})
    if bf.get("error"):
        check("read beam forces", False, bf["error"])
        return
    rows = bf.get("rows", [])
    slns = sorted({r["sln"] for r in rows}, key=lambda v: (v is None, v))
    grps = sorted({str(r["group"]) for r in rows})
    out(f"  {bf.get('beams')} beams; structural line numbers seen: {slns}; groups seen: {grps}")
    check("beams know their structural line (m_nref = SLN 7)", slns == [7], f"{slns}")
    by_sln = srv._cdb_call("beam_forces", cdb, {"lc": 1, "slns": "7"})
    check("filter by structural line 7", by_sln.get("beams") == bf.get("beams") and (bf.get("beams") or 0) >= 6,
          f"{by_sln.get('beams')} of {bf.get('beams')} beams")
    by_grp = srv._cdb_call("beam_forces", cdb, {"lc": 1, "groups": "3"})
    check("filter by group 3", by_grp.get("beams") == bf.get("beams") and (bf.get("beams") or 0) >= 6,
          f"{by_grp.get('beams')} of {bf.get('beams')} beams")
    my = bf.get("extremes", {}).get("My", {})
    mmax = max(abs(my.get("max", {}).get("value") or 0), abs(my.get("min", {}).get("value") or 0))
    check("fixed-end moment = w L^2 / 2", close(mmax, w * L * L / 2, 0.005), f"{mmax} kNm vs {w * L * L / 2}")
    sr = srv._cdb_call("support_reactions", cdb, {"lc": 1})
    pz = (sr.get("sum_kN") or {}).get("pz")
    check("sum of reactions = w L", close(pz, w * L, 0.005), f"{pz} kN vs {w * L}")
    nr = srv._cdb_call("node_results", cdb, {"lc": 1})
    uz = nr.get("extremes", {}).get("uz", {})
    umax = max(abs(uz.get("max", {}).get("value") or 0), abs(uz.get("min", {}).get("value") or 0))
    d_b = w * L ** 4 / (8 * E * Iy) * 1000
    d_s = (w * L * L / (2 * G * Az) * 1000) if (G and Az) else 0.0
    check("tip deflection = w L^4 / 8EI", close(umax, d_b + d_s, 0.01) or close(umax, d_b, 0.01),
          f"{umax} mm vs {d_b + d_s:.4f} mm (bending only {d_b:.4f})")


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
