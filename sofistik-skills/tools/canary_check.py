#!/usr/bin/env python3
"""G0 canary: the MCP self-test cantilever read back through this session's tools must give the hand values.

usage: python3 -I canary_check.py <selftest_results.json> [--workdir W]

<selftest_results.json> = ONE merged JSON object; each key holds the raw saved result of one cdb_* call on the
self-test database (selftest\\run\\selftest_cantilever.cdb, from selftest/selftest_cantilever.dat):
  g0_node_lc1     cdb_node_results(load_case=1, nodes="7")
  g0_support_lc1  cdb_support_reactions(load_case=1)
  g0_support_lc2  cdb_support_reactions(load_case=2)
  g0_beam_lc1     cdb_beam_forces(load_case=1)
  g0_env_1_2      cdb_envelope(load_cases="1-2", what="beam")
  g0_load_cases_1_2  cdb_load_cases(load_cases="1-2")   (review A-24: the CLC_CTRL sums that G4/G5 read)
Hand values (sofistik_mcp/selftest.py, README "Confirmed on SOFiSTiK 2027", ALL CHECKS PASSED 17 Oct 2026):
HEA 200 (Iy 3692 cm4), E 210000 N/mm2, L 6 m, tip load P = +1 kN (LC 1) / +2 kN (LC 2) in global +Z.
  tip uz  = P L^3 / 3EIy = 9.2867 mm bending (+ ~0.4 % shear)  -> +9.29 mm within 1 %, positive (moves with +Z)
  tip ury = P L^2 / 2EIy = 2.3216 mrad within 1 %, NEGATIVE (right-hand rule, beam along +X)
  support node 1: pz = -1.000 / -2.000 kN within 0.5 % (support force ON the structure), the only node with a
    reaction; sum_kN.pz and sum_stored_by_sofistik_kN[2] the same; |my| = 6 / 12 kNm within 0.5 %
  beam forces LC 1: My at beam 1, x = 0 = -6 kNm within 0.1 % (hogging, negative), |My| = P (L - x) at every
    station within 0.5 %, max |Vz| = 1 kN within 0.5 %, |N|, |Vy|, |Mt|, |Mz| <= 1e-3 (the tools round to 4 dp)
  envelope 1-2: load_cases_found [1, 2]; |My| max 12 kNm from LC 2 within 0.5 %
  load cases 1-2: kind 0/1, sum_reactions_kN = [0, 0, -1] / [0, 0, -2] (x, y <= 1e-3, z within 0.5 %): the
    stored sums used by equilibrium_check and combo_check have the node-reaction sign
Any missing key or field -> CANNOT_RUN; any stale warning, tool error or truncated result -> FAIL.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (MissingField, Parser, Report, input_record, load_json, need, num, run_main,  # noqa: E402
                     stale_of, unwrap)

TOOL = "canary_check"
P, L, E, IY = 1.0, 6.0, 2.1e8, 3692e-8
UZ = 9.29                                    # mm, 03 K2 / skill (bending part 9.2867)
URY = P * L ** 2 / (2 * E * IY) * 1e3        # mrad
KEYS = ("g0_node_lc1", "g0_support_lc1", "g0_support_lc2", "g0_beam_lc1", "g0_env_1_2", "g0_load_cases_1_2")


def close(a, b, rel):
    return abs(a - b) <= rel * abs(b)


def main():
    ap = Parser(TOOL, description="G0 canary against the self-test hand values",
                formatter_class=__import__("argparse").RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("merged")
    ap.add_argument("--workdir")
    a = ap.parse_args()
    rep = Report(TOOL, a.workdir, {"merged": input_record(a.merged, "canary")})
    m = unwrap(load_json(a.merged))
    if not isinstance(m, dict):
        raise MissingField("the merged file must be one JSON object with the g0_* keys")
    low = {k.lower().removesuffix(".json"): v for k, v in m.items()}
    parts = {}
    for k in KEYS:
        if k not in low:
            raise MissingField(f"key '{k}' missing (keys present: {sorted(m)})")
        p = unwrap(low[k])
        if not isinstance(p, dict):
            raise MissingField(f"{k} is not a tool result object")
        parts[k] = p
    # tool health of every part
    for k, p in parts.items():
        if p.get("error"):
            rep.check(f"K1_{k}", "FAIL", error=f"tool error: {p['error']}")
        st = stale_of(p)
        if st:
            rep.check(f"R4_{k}", "FAIL", error="stale_results_warning: " + " | ".join(st))
        if p.get("truncated") is True:
            rep.check(f"P_{k}", "FAIL", error="result truncated: re-read with a larger max_rows")

    def chk(cid, ok, expected, got, **kw):
        rep.check(cid, "PASS" if ok else "FAIL", expected=expected, got=got, **kw)

    # node 7 LC 1
    n = parts["g0_node_lc1"]
    rows = need(n, "rows", "g0_node_lc1")
    tip = next((r for r in rows if r.get("node") == 7), None)
    if tip is None:
        raise MissingField("g0_node_lc1 has no row for node 7")
    uz = num(need(tip, "uz", "node 7"), "uz")
    ury = num(need(tip, "ury", "node 7"), "ury")
    chk("K2_tip_uz", close(uz, UZ, 0.01), f"+{UZ} mm +-1 % (bending part 9.2867)", uz, unit="mm")
    chk("K3_tip_ury_sign", ury < 0, "ury < 0 (right-hand rule)", ury, unit="mrad")
    chk("K2_tip_ury", close(abs(ury), URY, 0.01), f"|ury| = {URY:.4f} mrad +-1 %", ury, unit="mrad")
    # supports
    for lc, k, f in ((1, "g0_support_lc1", 1.0), (2, "g0_support_lc2", 2.0)):
        s = parts[k]
        if int(need(s, "lc", k)) != lc:
            rep.check(f"K2_support_lc{lc}", "FAIL", error=f"{k} is for LC {s.get('lc')}, not {lc}")
            continue
        srows = need(s, "rows", k)
        nodes = [r.get("node") for r in srows]
        chk(f"K2_support_lc{lc}_nodes", nodes == [1], "only node 1 carries a reaction", nodes)
        r1 = next((r for r in srows if r.get("node") == 1), None)
        if r1 is None:
            raise MissingField(f"{k}: no row for node 1")
        pz = num(need(r1, "pz", f"{k} node 1"), "pz")
        my = num(need(r1, "my", f"{k} node 1"), "my")
        chk(f"K3_support_lc{lc}_pz", close(pz, -P * f, 0.005), f"pz = {-P * f:.3f} kN (support force on the "
            "structure, opposite to the +Z load)", pz, unit="kN")
        chk(f"K2_support_lc{lc}_my", close(abs(my), P * f * L, 0.005), f"|my| = {P * f * L:g} kNm +-0.5 %", my,
            unit="kNm", sign_note="sign recorded only (selftest checks |my|)")
        sk = need(s, "sum_kN", k)
        spz = num(need(sk, "pz", f"{k} sum_kN"), "sum pz")
        chk(f"K2_support_lc{lc}_sum", close(spz, -P * f, 0.005), f"sum_kN.pz = {-P * f:.3f}", spz, unit="kN")
        stored = need(s, "sum_stored_by_sofistik_kN", k)
        if not isinstance(stored, list) or len(stored) != 3 or stored[2] is None:
            raise MissingField(f"{k}: sum_stored_by_sofistik_kN is not [rx, ry, rz]")
        chk(f"K2_support_lc{lc}_stored", close(num(stored[2], "stored rz"), -P * f, 0.005),
            f"stored rz = {-P * f:.3f} (same sign as the node reactions)", stored[2], unit="kN")
    # beam forces LC 1
    b = parts["g0_beam_lc1"]
    brows = need(b, "rows", "g0_beam_lc1")
    if not brows:
        raise MissingField("g0_beam_lc1 has no rows")
    seg = L / 6
    bad, maxv = [], 0.0
    for r in brows:
        x = num(need(r, "x", "beam row"), "x")
        my = num(need(r, "My", "beam row"), "My")
        beam = int(need(r, "beam", "beam row"))
        if abs(abs(my) - P * (L - ((beam - 1) * seg + x))) > 0.005 * P * L:
            bad.append([beam, x, my])
        maxv = max(maxv, abs(num(need(r, "Vz", "beam row"), "Vz")))
    chk("K2_beam_My_linear", not bad, "|My| = P (L - x) at every station +-0.5 %", bad[:5] or "all stations",
        stations=len(brows))
    sup = next((r for r in brows if r.get("beam") == 1 and abs((r.get("x") or 0)) < 1e-6), None)
    if sup is None:
        raise MissingField("g0_beam_lc1: no row for beam 1 at x = 0")
    chk("K3_beam_My_support", close(sup["My"], -P * L, 0.001), f"My(beam 1, x 0) = {-P * L:g} kNm +-0.1 % "
        "(hogging negative)", sup["My"], unit="kNm")
    chk("K2_beam_Vz", close(maxv, P, 0.005), f"max |Vz| = {P:g} kN +-0.5 %", maxv, unit="kN")
    for comp in ("N", "Vy", "Mt", "Mz"):
        w = max(abs(num(need(r, comp, "beam row"), comp)) for r in brows)
        chk(f"K2_beam_{comp}_zero", w <= 1e-3, f"|{comp}| <= 1e-3", w)
    # envelope
    env = parts["g0_env_1_2"]
    found = need(env, "load_cases_found", "g0_env_1_2")
    chk("K2_env_found", list(found) == [1, 2], "[1, 2]", found)
    for key in ("load_cases_missing", "load_cases_without_data"):
        if env.get(key):
            rep.check(f"K2_env_{key}", "FAIL", got=env[key])
    ov = need(need(env, "overall", "g0_env_1_2"), "My", "g0_env_1_2 overall")
    cands = [x for x in (ov.get("max"), ov.get("min")) if x and x.get("value") is not None]
    if not cands:
        raise MissingField("g0_env_1_2 overall.My has no max/min value")
    best = max(cands, key=lambda x: abs(x["value"]))
    chk("K2_env_My", best.get("lc") == 2 and close(abs(best["value"]), 2 * P * L, 0.005),
        f"|My| = {2 * P * L:g} kNm from LC 2", {"value": best["value"], "lc": best.get("lc")})
    # load case sums (A-24)
    lcp = parts["g0_load_cases_1_2"]
    lrows = {int(need(r, "lc", "g0_load_cases_1_2 row")): r for r in (lcp.get("rows") or [])}
    for lc, f in ((1, 1.0), (2, 2.0)):
        r = lrows.get(lc)
        if r is None:
            raise MissingField(f"g0_load_cases_1_2 has no row for LC {lc}")
        if r.get("kind") not in (0, 1):
            rep.check(f"K2_lc{lc}_kind", "FAIL", got=r.get("kind"), expected="0/1 (calculated)")
        sr = need(r, "sum_reactions_kN", f"LC {lc}")
        if not isinstance(sr, list) or len(sr) != 3 or any(x is None for x in sr):
            raise MissingField(f"LC {lc}: sum_reactions_kN is not [rx, ry, rz]")
        sr = [num(x, "sum_reactions_kN") for x in sr]
        chk(f"K3_lc{lc}_sum_reactions", close(sr[2], -P * f, 0.005) and abs(sr[0]) <= 1e-3 and abs(sr[1]) <= 1e-3,
            f"[0, 0, {-P * f:g}] (CLC_CTRL sums have the node-reaction sign)", sr, unit="kN")
    rep.note("Signs proven here (K3): +Z load -> support pz < 0; ury < 0; beam My at the support < 0. Only after "
             "a PASS may project reactions be read with R + F = 0.")
    rep.emit()


if __name__ == "__main__":
    run_main(TOOL, main)
