#!/usr/bin/env python3
"""Confidence scorecard (04 A11): proofs.jsonl -> GREEN / AMBER / RED with the reasons.

usage: python3 -I scorecard.py <workdir> [--ledger LEDGER_FILE]

Reads <workdir>/proofs.jsonl (one JSON object per line, written by the tools and by P-PROOF lines).
The LAST line of each gate counts (a re-run replaces an earlier result); for member_check every line since the
last 'pick' counts (one line per hand-checked member).
  RED    a mandatory gate is missing, or its verdict is FAIL / CANNOT_RUN, or the proofs used a genuinely different
         .dat or .cdb (see "Input families" below), or proofs.jsonl has an unreadable line, or
         (A-09) a pick (member, lc) has no hand line, a hand line FAILs, or pick stats.n_eta_gt_1 > 0, or (A-02) a
         combination that equilibrium_check delegated has no C1_<lc> line in combo_check
         (member_check: a hand line "not hand-checkable" (exit 3) counts as ESCALATE, as in the skill, A-22)
  AMBER  any ESCALATE, or the assumptions are not agreed: GREEN needs the ledger (--ledger W/LEDGER.md, or a file
         whose name contains "ledger" in any case in the workdir) to say 'assumptions_agreed: yes' AND an A12_assumptions line with PASS
  GREEN  otherwise
Exit codes: 0 GREEN, 2 AMBER, 1 RED, 3 nothing to score.
Gate names: member_check alpha writes tool "member_check_alpha"; it counts as the G6_alpha_cr gate (a P-PROOF line
with tool "G6_alpha_cr" is accepted too).
Input families (final check M1/F1):
  .dat  dat_lint records the master M ("dat") and, when it expanded #INCLUDEs, the expanded text ("dat_expanded",
        byte-identical to expand_master.py's X); expand_master records "master" and "expanded".  Checksums recorded
        together in one proof line are one family, so M (dat_lint) and X (combo_check, mutation_drill, collect,
        coverage_census) agree.  A checksum linked to none of them = another .dat -> RED.
  .cdb  every "load_cases" input (W/raw/load_cases.json, W/raw/buckling_lcs.json, ...) is grouped by the "cdb" path
        the server writes into each result.  Two .cdb paths -> RED.  The file must still have the recorded checksum,
        and an LC present in two files must carry the same stored values (else the .cdb changed between the reads
        -> RED).  A file without a "cdb" field is its own family (by checksum).
Mandatory gates: canary_check, G2_protocol, A7_run_identity, equilibrium_check, mutation_drill, combo_check,
R6_member_lcs, G6_alpha_cr, coverage_census, member_check, G8_plausibility, A12_assumptions, receipts (audit).
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import EXIT, Parser, Report, run_main, worst  # noqa: E402

TOOL = "scorecard"
MANDATORY = ("canary_check", "G2_protocol", "A7_run_identity", "equilibrium_check", "mutation_drill",
             "combo_check", "R6_member_lcs", "G6_alpha_cr", "coverage_census", "member_check",
             "G8_plausibility", "A12_assumptions", "receipts")
GRADE = {"GREEN": "PASS", "AMBER": "ESCALATE", "RED": "FAIL"}


DAT_ROLES = ("dat", "dat_expanded", "master", "expanded")
TOOL_ALIAS = {"member_check_alpha": "G6_alpha_cr"}   # member_check alpha writes tool member_check_alpha


def dat_families(objs):
    """Group the .dat checksums into families.  One proof line links every dat-like checksum it records:
    dat_lint {dat (master M), dat_expanded (X)}, expand_master {master M, expanded X}.  Two tools are on the same
    .dat when their checksums are linked; more than one family = a genuinely different .dat -> RED.
    Returns {family: [tools]} (one entry when consistent)."""
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    users = []
    for o in objs:
        ins = o.get("inputs") or {}
        shas = [ins[r]["sha256"] for r in DAT_ROLES if isinstance(ins.get(r), dict) and ins[r].get("sha256")]
        for x in shas[1:]:
            parent[find(x)] = find(shas[0])
        if shas:
            find(shas[0])
            users.append((o["tool"], shas[0]))
    fam = {}
    for tool, sha in users:
        fam.setdefault(find(sha)[:12], []).append(tool)
    return fam


def _norm_cdb(p):
    return str(p).replace("/", "\\").strip().lower() if p else None


def load_case_families(objs):
    """Load-case results (role load_cases: cdb_load_cases saved by hand, e.g. W/raw/load_cases.json and
    W/raw/buckling_lcs.json) are one family when they come from the same .cdb (the 'cdb' path the server adds
    to every result, server.py _cdb_call).  The file must still have the checksum the tool recorded, and an LC
    present in two files must have the same stored values (a re-run between the reads changes them).
    Returns ({family: [tools]}, [errors])."""
    import hashlib
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _common import load_json, unwrap
    fam, errs, seen = {}, [], {}
    for o in objs:
        r = (o.get("inputs") or {}).get("load_cases")
        if not isinstance(r, dict) or not r.get("sha256"):
            continue
        key, path = None, r.get("path")
        try:
            with open(path, "rb") as f:
                h = hashlib.sha256(f.read()).hexdigest()
            if h != r["sha256"]:
                errs.append(f"{o['tool']}: {path} changed after the proof was made (sha differs)")
            obj = unwrap(load_json(path))
            key = _norm_cdb(obj.get("cdb")) if isinstance(obj, dict) else None
            rows = obj.get("rows") if isinstance(obj, dict) else None
            for row in rows or []:
                if not isinstance(row, dict) or row.get("lc") is None:
                    continue
                sig = json.dumps([row.get("kind"), row.get("sum_reactions_kN"), row.get("dead_load_factors"),
                                  row.get("frequency_Hz")], sort_keys=True)
                k2 = (key, int(row["lc"]))
                if k2 in seen and seen[k2][0] != sig:
                    errs.append(f"LC {row['lc']} differs between {seen[k2][1]} and {path} (same .cdb {key}): "
                                "results changed between the reads")
                seen.setdefault(k2, (sig, path))
        except (OSError, ValueError, TypeError) as e:
            errs.append(f"{o['tool']}: cannot re-read {path} to check its .cdb ({e})")
        fam.setdefault(key or ("sha:" + r["sha256"][:12]), []).append(o["tool"])
    return fam, errs


def ledger_agreed(workdir, ledger):
    files = [ledger] if ledger else sorted(p for p in glob.glob(os.path.join(workdir, "*"))
                                           if "ledger" in os.path.basename(p).lower() and os.path.isfile(p))
    for p in files:
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                for ln in f:
                    m = re.match(r"\s*assumptions_agreed\s*:\s*(\S*)", ln, re.I)
                    if m:
                        return m.group(1).lower() == "yes", p
        except OSError:
            continue
    return False, (files[0] if files else None)


def main():
    import argparse
    ap = Parser(TOOL, description="GREEN / AMBER / RED from proofs.jsonl",
                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("workdir")
    ap.add_argument("--ledger")
    a = ap.parse_args()
    rep = Report(TOOL, None)
    path = os.path.join(a.workdir, "proofs.jsonl")
    lines = []
    bad = []
    if os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            for i, ln in enumerate(f, 1):
                if not ln.strip():
                    continue
                try:
                    o = json.loads(ln)
                    if not isinstance(o, dict) or "tool" not in o or "verdict" not in o:
                        raise ValueError("no tool/verdict")
                    lines.append(o)
                except ValueError as e:
                    bad.append(f"line {i}: {e}")
    if not lines:
        rep.check("proofs", "CANNOT_RUN", error=f"no proof lines in {path}")
        rep.workdir = None
        rep.emit()
    reasons, grade = [], "GREEN"

    def lower(to, why):
        nonlocal grade
        order = ["GREEN", "AMBER", "RED"]
        if order.index(to) > order.index(grade):
            grade = to
        reasons.append(f"{to}: {why}")

    if bad:
        lower("RED", f"unreadable proof lines: {bad[:3]}")
    latest, member = {}, []
    for o in lines:
        t = o["tool"]
        if t == TOOL:
            continue
        if t == "receipts" and o.get("action") not in (None, "audit"):
            continue
        if t == "member_check":
            if o.get("action") == "pick":
                member = [o]
            else:
                member.append(o)
            latest[t] = o
            continue
        latest[TOOL_ALIAS.get(t, t)] = o
    gates = {}
    member_v = None
    if member:
        pick = member[0] if member[0].get("action") == "pick" else None
        hands = [m for m in member if m.get("action") == "hand"]
        vs = [pick["verdict"]] if pick else []
        for h in hands:
            # A-22: "not hand-checkable" (CANNOT_RUN) is ESCALATE for the gate, as in the skill; FAIL stays FAIL
            vs.append("ESCALATE" if h["verdict"] == "CANNOT_RUN" else h["verdict"])
        member_v = worst(*vs) if vs else None
        if pick is None:
            lower("RED", "member_check: hand lines without a pick line")
        else:
            done = {(str(h.get("member")), h.get("lc")) for h in hands}
            done_m = {str(h.get("member")) for h in hands}
            missing, nolc = [], []
            for pk in pick.get("picks") or []:
                if pk.get("lc") is None:
                    nolc.append(str(pk.get("member")))
                elif (str(pk.get("member")), int(pk["lc"])) not in done and \
                        (str(pk.get("member")), pk.get("lc")) not in done:
                    missing.append(f"{pk.get('member')}@{pk.get('lc')}")
            if missing:
                lower("RED", f"picks not hand-checked (A-09): {missing[:12]}")
            if nolc:
                lower("AMBER", f"picks with no LC, not hand-checked: {nolc[:12]}")
            st = pick.get("stats") or {}
            if st.get("n_eta_gt_1") is None:
                lower("RED", "pick line has no stats.n_eta_gt_1")
            elif int(st["n_eta_gt_1"]) > 0:
                lower("RED", f"{st['n_eta_gt_1']} member(s) with utilisation > 1.0 (A-09; report only, the "
                             f"structure fails): {[x.get('member') for x in (st.get('members_gt_1') or [])][:12]}")
            for h in hands:
                if h["verdict"] == "FAIL":
                    lower("RED", f"member {h.get('member')} LC {h.get('lc')} fails the hand-check")
    # A-02: every combination equilibrium_check delegated must have a C1 line in combo_check
    eq, cc = latest.get("equilibrium_check"), latest.get("combo_check")
    if eq and eq.get("delegated_to_combo_check"):
        have = {c.get("id") for c in (cc or {}).get("checks", [])}
        miss = [lc for lc in eq["delegated_to_combo_check"] if f"C1_{lc}" not in have]
        if miss:
            lower("RED", f"combinations checked by neither G4 nor G5 (A-02): {miss[:20]}")
    for t in MANDATORY:
        if t == "member_check":
            v = member_v
        else:
            v = latest.get(t, {}).get("verdict")
        gates[t] = v
        if v is None:
            lower("RED", f"mandatory gate {t} missing")
        elif v in ("FAIL", "CANNOT_RUN"):
            lower("RED", f"{t} {v}")
        elif v == "ESCALATE":
            first = next(iter(latest.get(t, member[-1] if member else {}).get("notes") or []), "")
            lower("AMBER", f"{t} ESCALATE" + (f" ({first[:120]})" if first else ""))
    for t, o in latest.items():
        if t not in MANDATORY and o["verdict"] != "PASS":
            lower("RED" if o["verdict"] in ("FAIL", "CANNOT_RUN") else "AMBER", f"{t} {o['verdict']}")
    # same inputs everywhere (final check M1/F1: related inputs are one family, a different .dat/.cdb is RED)
    fam_dat = dat_families(latest.values())
    if len(fam_dat) > 1:
        lower("RED", f"proofs used different versions of the dat file: {fam_dat}")
    fam_lc, lc_errs = load_case_families(latest.values())
    if len(fam_lc) > 1:
        lower("RED", f"proofs used load-case results of different .cdb files: {fam_lc}")
    for e in lc_errs:
        lower("RED", e)
    agreed, lfile = ledger_agreed(a.workdir, a.ledger)
    if not agreed:
        lower("AMBER", "assumptions not agreed (ledger 'assumptions_agreed' is not 'yes'"
              + (f" in {lfile})" if lfile else ", no ledger found)"))
    elif gates.get("A12_assumptions") != "PASS":
        lower("AMBER", "ledger says assumptions agreed but the A12_assumptions proof line is not PASS")
    rep.verdict = GRADE[grade]
    rep.extra["score"] = grade
    rep.extra["gates"] = gates
    rep.check("score", GRADE[grade], score=grade, reasons=reasons)
    for r in reasons:
        rep.note(r)
    rep.workdir = a.workdir
    o = rep.emit(exit_now=False)
    sys.exit(EXIT[o["verdict"]])


if __name__ == "__main__":
    run_main(TOOL, main)
