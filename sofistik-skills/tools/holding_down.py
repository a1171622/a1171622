#!/usr/bin/env python3
"""G8 holding-down / uplift (review A-10): which support reactions pull the structure down, with the gravity
direction read from the self-weight reaction, not assumed.

usage: python3 -I holding_down.py <load_cases.json> <env_support.json> [--sw-lc 1] --workdir W

<load_cases.json>  saved cdb_load_cases result (needs the self-weight LC row with sum_reactions_kN)
<env_support.json> saved cdb_envelope(load_cases="<lcs>", what="support") result: overall.pz {max, min} each
                   {value, lc, node, ...}
Rule: the self-weight reaction sum gives the gravity reaction sign s = sign(Rz of LC sw) (Z up, GDIR NEGZ:
s = +1; Z down, GDIR POSZ: s = -1).  An uplift (holding-down) reaction is a support reaction pz with the
OPPOSITE sign to s.  It is reported as a holding-down force (ESCALATE, report only: anchorage / holding-down
bolts are not checked by any tool), never as a model error.  PASS when no reaction has the opposite sign.
CANNOT_RUN when the self-weight LC is missing, its sum is ~0, or gravity is not along Z (|Rz| < 0.9 |R|).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (MissingField, Parser, Report, input_record, load_json, need, num, rows_of,  # noqa: E402
                     run_main, stale_of, unwrap)

TOOL = "holding_down"


def main():
    ap = Parser(TOOL, description="holding-down (uplift) reactions with the gravity sign from the self-weight LC",
                formatter_class=__import__("argparse").RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("load_cases")
    ap.add_argument("env_support")
    ap.add_argument("--sw-lc", dest="sw_lc", type=int, default=1)
    ap.add_argument("--workdir")
    a = ap.parse_args()
    rep = Report(TOOL, a.workdir, {"load_cases": input_record(a.load_cases, "load_cases"),
                                   "env_support": input_record(a.env_support, "env_support")})
    lc_obj = load_json(a.load_cases)
    row = next((r for r in rows_of(lc_obj, a.load_cases) if int(need(r, "lc", "row")) == a.sw_lc), None)
    if row is None:
        raise MissingField(f"self-weight LC {a.sw_lc} not in {a.load_cases}")
    R = [num(x, "sum_reactions_kN") for x in need(row, "sum_reactions_kN", f"LC {a.sw_lc}")]
    mag = sum(x * x for x in R) ** 0.5
    if mag < 1e-6:
        raise MissingField(f"LC {a.sw_lc} reaction sum is 0: gravity direction unknown")
    if abs(R[2]) < 0.9 * mag:
        raise MissingField(f"LC {a.sw_lc} reaction {R} is not along Z: gravity direction not Z, rule does not apply")
    s = 1 if R[2] > 0 else -1
    env = unwrap(load_json(a.env_support))
    if not isinstance(env, dict) or env.get("error"):
        raise MissingField(f"{a.env_support} is not an envelope result")
    if stale_of(env) or stale_of(lc_obj):
        rep.check("R4_fresh", "FAIL", error="stale_results_warning")
    pz = need(need(env, "overall", a.env_support), "pz", "overall")
    ext = pz.get("min") if s > 0 else pz.get("max")
    if not ext or ext.get("value") is None:
        raise MissingField(f"overall.pz.{'min' if s > 0 else 'max'} missing in {a.env_support}")
    v = num(ext["value"], "pz")
    rep.extra.update(gravity_reaction_sign=s, sw_reaction_kN=R)
    if v * s < 0:
        rep.extra.update(uplift_kN=abs(v), uplift_lc=ext.get("lc"), uplift_node=ext.get("node"))
        rep.check("G8_holding_down", "ESCALATE", uplift_kN=abs(v), lc=ext.get("lc"), node=ext.get("node"),
                  meaning="holding-down force (report only): anchorage / holding-down bolts are not checked")
    else:
        rep.extra.update(uplift_kN=0.0)
        rep.check("G8_holding_down", "PASS", got=v, meaning="no reaction opposite to the gravity reaction")
    rep.note(f"Gravity reaction sign from LC {a.sw_lc}: Rz = {R[2]:g} kN -> uplift = pz with sign {-s:+d}.")
    rep.emit()


if __name__ == "__main__":
    run_main(TOOL, main)
