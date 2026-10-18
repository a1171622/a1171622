#!/usr/bin/env python3
"""Coverage census (04 A9, 03 H1): every member of the model is accounted for.

usage: python3 -I coverage_census.py <file.dat> <checked_members.json> [--workdir W]

Members = structural lines with a cross-section (SOFiMSHC 'SLN ... SNO n') in the .dat.  Each one must be
  BDK      part of a BDK member (MEMB SLN / CONT, in a +PROG BDK block, after IF evaluation) that HAS a result
  AQB-only has an AQB result (cross-section check only) but no BDK result: it has NO member-buckling check, so
           it needs a reason in 'aqb_only_reasons' (per SLN, or "G<group>"), else ESCALATE (review A-04)
  EXCLUDED listed in 'excluded' with a non-empty reason (e.g. "stub 0.12 m < 0.3 m")
  UNACCOUNTED anything else -> FAIL (no "all members pass" while one is unaccounted)
Also FAIL: a member the .dat sends to BDK that has no BDK result (silent omission, the classic member-check
error).  ESCALATE: a BDK result for a member ID the .dat does not define.

<checked_members.json> (member_check.py collect writes it; every key required, lists may be empty):
  {"source": "<where the results were read: tool, key, file, lines>",
   "bdk_checked": [<BDK design-element ID = MEMB ID, default its first SLN>, ...],
   "aqb_checked_slns": [<SLN with AQB results>, ...],
   "excluded": {"<SLN>": "<reason>", ...},
   "aqb_only_reasons": {"<SLN>" | "G<group>": "<lead-written reason, e.g. short chord 0.66 m>", ...}  (optional;
                       a missing reason gives ESCALATE, never a default)}
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cadinp as C  # noqa: E402
from _common import MissingField, Parser, Report, input_record, load_json, need, run_main, unwrap  # noqa: E402

TOOL = "coverage_census"


def census(model, chk):
    bdk_ids = set(int(x) for x in need(chk, "bdk_checked", "checked_members.json"))
    aqb = set(int(x) for x in need(chk, "aqb_checked_slns", "checked_members.json"))
    exc_raw = need(chk, "excluded", "checked_members.json")
    if not isinstance(exc_raw, dict):
        raise MissingField("'excluded' must be an object {SLN: reason}")
    excluded = {int(k): (v or "").strip() for k, v in exc_raw.items()}
    reasons = chk.get("aqb_only_reasons") or {}
    if not isinstance(reasons, dict):
        raise MissingField("'aqb_only_reasons' must be an object {\"<SLN>\" or \"G<group>\": reason}")
    reasons = {str(k): (v or "") for k, v in reasons.items()}
    members = model.bdk_members()
    sln_to_member = {}
    intended = {}
    for m in members:
        intended[m["id"]] = m
        for s in [m["sln"]] + m["cont"]:
            sln_to_member.setdefault(s, set()).add(m["id"])
    status = {}
    for sln, info in sorted(model.slns.items()):
        if info.get("sno") is None:
            status[sln] = ("NOT_A_MEMBER", "no cross-section (SNO) on this structural line")
            continue
        mids = sln_to_member.get(sln, set())
        if mids & bdk_ids:
            status[sln] = ("BDK", f"member {sorted(mids & bdk_ids)}")
        elif sln in aqb:
            why = reasons.get(str(sln)) or reasons.get(f"G{info.get('grp')}")
            status[sln] = ("AQB_ONLY", (why or "").strip())
        elif sln in excluded and excluded[sln]:
            status[sln] = ("EXCLUDED", excluded[sln])
        else:
            why = "no BDK result, no AQB result, no exclusion reason"
            if mids:
                why = f"BDK member {sorted(mids)} intended but has no result"
            if sln in excluded and not excluded[sln]:
                why = "excluded with an EMPTY reason"
            status[sln] = ("UNACCOUNTED", why)
    omitted = sorted(i for i in intended if i not in bdk_ids)
    unknown = sorted(i for i in bdk_ids if i not in intended)
    return status, omitted, unknown, intended


def main():
    ap = Parser(TOOL, description="coverage census of members",
                formatter_class=__import__("argparse").RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("dat")
    ap.add_argument("checked")
    ap.add_argument("--workdir")
    a = ap.parse_args()
    rep = Report(TOOL, a.workdir, {"dat": input_record(a.dat, "dat"), "checked": input_record(a.checked, "checked")})
    model = C.Model(C.Dat.from_file(a.dat))
    chk = unwrap(load_json(a.checked))
    if not model.slns:
        raise MissingField("no structural lines (SOFiMSHC SLN) in the .dat: give the .dat that holds the model")
    status, omitted, unknown, intended = census(model, chk)
    by = {}
    for sln, (st, why) in status.items():
        by.setdefault(st, []).append(sln)
    counts = {k: len(v) for k, v in by.items()}
    un = by.get("UNACCOUNTED", [])
    rep.check("H1_unaccounted", "FAIL" if un else "PASS", count=len(un),
              members=[{"sln": s, "why": status[s][1]} for s in un[:80]])
    rep.check("H1_bdk_omitted", "FAIL" if omitted else "PASS", count=len(omitted), member_ids=omitted[:80],
              expected=f"{len(intended)} BDK members in the .dat", got=f"{len(intended) - len(omitted)} with results")
    rep.check("H1_bdk_unknown", "ESCALATE" if unknown else "PASS", count=len(unknown), member_ids=unknown[:80])
    # review A-04: an AQB-only member has NO member-buckling check; it needs a lead-written reason
    noreason = [s for s in by.get("AQB_ONLY", []) if not status[s][1]]
    groups = {}
    for s_ in noreason:
        groups.setdefault(f"G{model.slns[s_].get('grp')}", []).append(s_)
    rep.check("H1_aqb_only_reason", "ESCALATE" if noreason else "PASS", count=len(noreason),
              groups={g: v[:30] for g, v in groups.items()},
              meaning="AQB-only = cross-section check only, no member-buckling (6.3) check; give a reason per SLN "
                      "or group in checked_members.json 'aqb_only_reasons'")
    rep.extra["summary"] = {"counts": counts, "bdk_members_intended": len(intended),
                            "aqb_only_no_buckling_check": {str(s_): status[s_][1] for s_ in by.get("AQB_ONLY", [])},
                            "excluded": {str(s): status[s][1] for s in by.get("EXCLUDED", [])},
                            "source": chk.get("source")}
    rep.emit()


if __name__ == "__main__":
    run_main(TOOL, main)
