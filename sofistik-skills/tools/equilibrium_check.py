#!/usr/bin/env python3
"""G4 equilibrium per load case: SOFiSTiK's stored reaction sums against the independently computed applied
load totals.

usage: python3 -I equilibrium_check.py <load_cases.json> <expected.json> [--workdir W]

<load_cases.json> = saved cdb_load_cases result: {"rows": [{"lc", "kind", "sum_reactions_kN": [rx, ry, rz],
  "has_results", "title", ...}], "cdb", optional "stale_results_warning"}  (results.py load_cases).
<expected.json>  = {"load_cases": {"<lc>": {"F_kN": [fx, fy, fz], "gross_kN": g, "gross_kN_xyz": [gx, gy, gz],
  "kind": "applied" |
  "selfweight_estimate", "title": ...}}, "not_expected": {"<lc>": "reason"}, "combinations": [lc, ...],
  "selfweight_lcs": [lc, ...]}
  (make_expected_26016.py writes it for 26016; for another project the author stage writes it).

Sign (MCP README, self-test confirmed 17 Oct 2026): a reaction is the force of the support ON the structure,
+1 kN load in +Z gives pz = -1.  CLC_CTRL m_rx/ry/rz (sum_reactions_kN) has the same sign.  So R + F = 0.
Tolerances (fixed; review A-06: per component, so a short lateral component cannot hide behind a large vertical
gross).  ref_j = gross_kN_xyz[j] = sum over loaded objects of |F_j| (make_expected writes it; required):
  applied:              every |R_j+F_j| <= 0.1 % ref_j + 0.05 kN PASS; any > 1 % ref_j + 0.05 kN FAIL; else ESCALATE
  selfweight_estimate:  <= 1 % PASS; <= 2 % ESCALATE; else FAIL  (an estimate, not an exact total)
Vacuous-pass rule (03 rule 0.4): when |F| < 0.5 % of the gross load (self-equilibrating: barriers, temperature,
EHF pairs) or the gross load is 0, a matching net sum proves nothing -> ESCALATE "not proven by reactions" (no
member-force proof exists in v1).
Fail closed: an expected LC missing from the .cdb, a non-calculated kind, or a None sum -> FAIL; a calculated LC
in the .cdb with no expected value and not listed as a combination -> ESCALATE; a self-weight LC listed in
"selfweight_lcs" without an estimate -> note only (no default ESCALATE, A-17).
Combinations listed in "combinations" are NOT checked here: they are returned in "delegated_to_combo_check" and
scorecard.py turns RED when combo_check has no C1_<lc> line for one of them (A-02).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (MissingField, Parser, Report, input_record, load_json, need, num, rows_of,  # noqa: E402
                     run_main, stale_of, unwrap, worst)

TOOL = "equilibrium_check"
TOL = {"applied": (0.001, 0.01), "selfweight_estimate": (0.01, 0.02)}
ABS_KN = 0.05
VACUOUS = 0.005


def main():
    ap = Parser(TOOL, description="G4 equilibrium per load case",
                formatter_class=__import__("argparse").RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("load_cases")
    ap.add_argument("expected")
    ap.add_argument("--workdir")
    a = ap.parse_args()
    rep = Report(TOOL, a.workdir, {"load_cases": input_record(a.load_cases, "load_cases"),
                                   "expected": input_record(a.expected, "expected")})
    obj = load_json(a.load_cases)
    st = stale_of(obj)
    if st:
        rep.check("R4_fresh", "FAIL", error="stale_results_warning: " + " | ".join(st))
    rows = {}
    for r in rows_of(obj, a.load_cases):
        rows[int(need(r, "lc", "a load_cases row"))] = r
    exp = unwrap(load_json(a.expected))
    E = need(exp, "load_cases", a.expected)
    if not isinstance(E, dict) or not E:
        raise MissingField("expected.json 'load_cases' is empty")
    notexp = {int(k): v for k, v in (exp.get("not_expected") or {}).items()}
    combos = set(int(x) for x in (exp.get("combinations") or []))
    worst_rel = (0.0, None)
    counts = {"PASS": 0, "ESCALATE": 0, "FAIL": 0}
    for key in sorted(E, key=lambda k: int(k)):
        lc = int(key)
        e = E[key]
        cid = f"E1_{lc}"
        try:
            F = [num(x, f"expected LC {lc} F_kN") for x in need(e, "F_kN", f"expected LC {lc}")]
            gross = num(need(e, "gross_kN", f"expected LC {lc}"), f"expected LC {lc} gross_kN")
            gx = [num(x, f"expected LC {lc} gross_kN_xyz") for x in need(e, "gross_kN_xyz", f"expected LC {lc} "
                                                                        "(regenerate expected.json)")]
            kind = e.get("kind", "applied")
            if kind not in TOL:
                raise MissingField(f"expected LC {lc}: unknown kind {kind!r}")
            if len(F) != 3:
                raise MissingField(f"expected LC {lc}: F_kN must be [fx, fy, fz]")
        except MissingField as ex:
            rep.check(cid, "CANNOT_RUN", lc=lc, error=str(ex))
            continue
        row = rows.get(lc)
        if row is None:
            v = "FAIL"
            rep.check(cid, v, lc=lc, error="load case not in load_cases.json (not computed, or not read)")
            counts[v] += 1
            continue
        if row.get("kind") not in (0, 1):
            rep.check(cid, "FAIL", lc=lc, error=f"kind {row.get('kind')} is not a calculated load case")
            counts["FAIL"] += 1
            continue
        R = row.get("sum_reactions_kN")
        if not isinstance(R, list) or len(R) != 3 or any(x is None for x in R):
            rep.check(cid, "FAIL", lc=lc, error=f"sum_reactions_kN missing or incomplete: {R!r}")
            counts["FAIL"] += 1
            continue
        R = [num(x, f"LC {lc} sum_reactions_kN") for x in R]
        ref = max(gross, 1.0)
        refj = [max(g, 0.0) for g in gx]
        resid = [R[j] + F[j] for j in range(3)]
        rel = max(abs(resid[j]) / max(refj[j], 1.0) for j in range(3))
        p_tol, e_tol = TOL[kind]
        if all(abs(resid[j]) <= p_tol * refj[j] + ABS_KN for j in range(3)):
            v = "PASS"
        elif all(abs(resid[j]) <= e_tol * refj[j] + ABS_KN for j in range(3)):
            v = "ESCALATE"
        else:
            v = "FAIL"
        fnet = sum(x * x for x in F) ** 0.5
        vac = None
        if v == "PASS" and (gross <= 0 or fnet < VACUOUS * gross):
            v = "ESCALATE"
            vac = ("not proven by reactions: net applied load ~0 (self-equilibrating or no force), so the net sum "
                   "cannot show a missing or doubled load; no member-force proof in v1")
        if rel > worst_rel[0]:
            worst_rel = (rel, lc)
        counts[v] = counts.get(v, 0) + 1
        c = rep.check(cid, v, lc=lc, title=e.get("title", ""), expected_reaction_kN=[round(-x, 4) for x in F],
                      got_kN=R, residual_kN=[round(x, 4) for x in resid], gross_kN=gross,
                      ref_kN_xyz=refj, residual_pct_of_ref=round(100 * rel, 4), tol_pct=[100 * p_tol, 100 * e_tol],
                      kind=kind)
        if vac:
            c["vacuous"] = vac
    listed = set(int(k) for k in E)
    sw = set(int(x) for x in (exp.get("selfweight_lcs") or []))
    extra = sorted(lc for lc, r in rows.items()
                   if r.get("kind") in (0, 1) and lc not in listed and lc not in combos and "nodes" in (r.get("has_results") or []))
    for lc in [x for x in extra if x in sw]:
        rep.note(f"LC {lc} is self-weight with no estimate in expected.json: its sum is NOT checked here "
                 f"(stored {rows[lc].get('sum_reactions_kN')} kN). List it under 'not checked'.")
    extra = [x for x in extra if x not in sw]
    delegated = sorted(lc for lc in rows if lc in combos and lc not in listed)
    rep.extra["delegated_to_combo_check"] = delegated
    if delegated:
        rep.note(f"{len(delegated)} combinations are not checked here (expected.json 'combinations'); combo_check "
                 "must have a C1_<lc> line for each, the scorecard checks that.")
    for lc in extra:
        reason = notexp.get(lc)
        rep.check(f"E1_{lc}", "ESCALATE", lc=lc, error="no expected value: equilibrium not proven"
                  + (f" (expected.json says: {reason})" if reason else ""))
    rep.extra["summary"] = {"checked": len(listed), "counts": counts, "without_expected": extra,
                            "worst_lc": worst_rel[1], "worst_pct_of_ref": round(100 * worst_rel[0], 4)}
    rep.note("R + F = 0 with R = force of the supports on the structure (MCP self-test sign).")
    rep.emit()


if __name__ == "__main__":
    run_main(TOOL, main)
