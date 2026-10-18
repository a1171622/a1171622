#!/usr/bin/env python3
"""Member results: alpha_cr (G6), collection of BDK / AQB utilisations (H1), picks and hand-checks (G7).

usage:
  python3 -I member_check.py alpha <load_cases.json> --buckling-lcs "9201-9220,9221-9240" [--beam-map <bm.json>
                                   [--dat <dat_local>] [--compression-forces F.json ...] [--all-members]] --workdir W
  python3 -I member_check.py mesh <beam_map.json> [--dat <dat_local>] [--compression-forces F1.json ...]
                                  [--all-members] --workdir W
  python3 -I member_check.py calibrate-alpha <be13_load_cases.json> [--ref "101=38.553,102=38.553,..."] --workdir W
  python3 -I member_check.py calibrate-bdk --bdk P1.json [P2.json ...] --prt '{"<member>": [value, "<column>"], ...}'
                                           --workdir W
  python3 -I member_check.py collect --dat <dat_local> --bdk P1.json [P2.json ...] --aqb Q1.json [Q2.json ...]
                                     --beam-map <beam_forces.json> [--excluded excl.json] --workdir W
  python3 -I member_check.py pick <member_results.json> <env_uls_beam.json> --seed <run_id> --workdir W
  python3 -I member_check.py hand <forces.json> <overview.json> <member_results.json> --member M --lc LC
                                  [--extra-forces F_lc2.json F_lc3.json ...] --workdir W

Every subcommand prints ONE JSON object, appends it to W/proofs.jsonl and exits 0 PASS / 1 FAIL / 2 ESCALATE /
3 CANNOT_RUN.  Where the results live in the CDB is read from calibration.json (next to this script).  While a
source there says UNCALIBRATED, 'alpha' and 'collect' refuse (CANNOT_RUN, alpha_cr_min = "UNCALIBRATED"): the
skill then stops with S7-UNCALIBRATED.  README.md section 'member results' has the evidence and the calibration.
--calibration <other file> is refused (CANNOT_RUN) unless TOOLS_TEST=1 (tests only; review A-16 / L12): the
skills never pass it and never edit calibration.json.

alpha     cdb_load_cases rows of the buckling LCs (kind 4, eigen) -> lambda per mode by the calibrated rule ->
          alpha_cr_min = the lowest POSITIVE factor over all modes of all LCs, with its LC and mode.
          PASS >= 10; ESCALATE 3..10 and < 3 (sway: the lead decides); FAIL when a buckling LC is missing, is not
          an eigen LC or has no frequency.  G6_mesh (A-07): elements per structural line measured from --beam-map
          (cdb_beam_forces ends_only); PASS >= 8, else ESCALATE "alpha_cr NOT PROVEN"; no --beam-map -> ESCALATE.
          Tool name in proofs.jsonl: member_check_alpha.
mesh      G6_mesh alone (eigen_el_per_span = the smallest count) over SLNs with a section (--dat) that are in
          COMPRESSION: from --compression-forces when given, else from the beam map's own N values; neither ->
          ESCALATE "compression members unknown" (fail closed).  --all-members measures every SLN (old behaviour).
calibrate-alpha  tests every known rule (calibration.json alpha_cr.rules_known) on a run with known buckling
          factors (BE13: LC 101-104 = 38.553, 38.553, 154.215, 154.215); PASS if exactly one rule matches all
          within 0.5 %; prints the calibration.json block for the lead to paste.  It never edits calibration.json.
calibrate-bdk  (A-23) BDK pages against the .prt check values of >= 5 members whose governing columns differ
          (>= 2 different columns): PASS when exactly one record field matches every member within 0.01; prints
          the block for the lead to paste.  Fewer members / one column -> CANNOT_RUN; 0 or 2+ fields match -> FAIL.
collect   cdb_read_key pages of 127/<LCST> (BDK) and 107/<LC> (AQB) -> W/member_results.json and
          W/checked_members.json.  Every page set must be complete (sum of records = record_count).
          --excluded may also hold "aqb_only_reasons" {"<SLN>" or "G<group>": reason} (A-04, coverage_census H1).
pick      top 3 by BDK, top 3 by AQB, EVERY member with eta >= 0.9 (BDK or AQB, F-EX2), the member with the
          largest compression (env overall.N.min) under ITS OWN LC (A-13), then 1 random member per section
          (seeded by the run id).  Cap 20: only random picks are dropped by it; when the mandatory picks alone
          exceed 20 all are kept and G7_picks_over_cap ESCALATEs.  Picks are keyed (member, lc).  stats
          {n_members, eta_max, eta_min, n_eta_gt_1, lc_outside_set, members_gt_1}.  ESCALATE when
          lc_outside_set is not empty or a pick has no LC.
hand      sofrep ec3.design_member (EN 1993-1-1, UK NA, gamma_M0 = gamma_M1 = 1.0) on the beam forces of the
          member's structural lines.  --lc is the governing LC; --extra-forces adds the member's other LCs so
          eta_bdk is compared with the hand ENVELOPE over all member LCs (A-14; all_member_lcs_checked).
          hand_aqb = max ratio of the 6.2 (cross-section) checks, compared with eta_aqb within +-0.05.
          hand_bdk = max ratio of the 6.3 (member) checks; load height rule from calibration.json ltb_load_height:
          until that item is CALIBRATED as shear_centre the rule is max(shear centre, top flange) (A-03).
          Compared with eta_bdk within max(0.10, 10 %).
          No eta_bdk (AQB-only member, A-01): hand 6.3 governs: > 1.1 FAIL, > 0.9 ESCALATE, else PASS only
          when EVERY member LC was hand-checked (N-02), otherwise ESCALATE "give --extra-forces for all member
          LCs" (G7_bdk_hand_only); never PASS without a hand 6.3 value (CANNOT_RUN).
          exit 0 PASS; 2 ESCALATE (any eta 0.9-1.1, routes disagree, PASS/FAIL differs, only some LCs checked);
          1 FAIL (SOFiSTiK and hand both > 1.1, or hand-only 6.3 > 1.1); 3 not hand-checkable (shape, missing
          forces, elements out of order, section mismatch).  FAIL outranks CANNOT_RUN (A-22).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _common import (CannotRun, MissingField, Parser, Report, input_record, load_json, need, num,  # noqa: E402
                     parse_ids, rows_of, run_main, stale_of, unwrap)

TOOL = "member_check"
CALIB = os.path.join(HERE, "calibration.json")
SOFREP = "/mnt/project-files/reports/sofistik_report"
TOL_AQB = 0.05
TOL_BDK_ABS, TOL_BDK_REL = 0.10, 0.10
MARGIN = (0.9, 1.1)
ALPHA_PASS, ALPHA_LOW = 10.0, 3.0
BE13_REF = {101: 38.553, 102: 38.553, 103: 154.215, 104: 154.215}   # BENCHMARK_RESULTS.md (BE13)
RULES = {
    "omega": lambda f: 2 * math.pi * f,
    "omega2": lambda f: (2 * math.pi * f) ** 2,
    "hz": lambda f: f,
    "inv_omega": lambda f: 1.0 / (2 * math.pi * f) if f else float("nan"),
}
PICK_CAP = 20      # picks for hand checks; only random picks are ever dropped by it (F-EX2)
HIGH_ETA = 0.9     # every member at or above this utilisation is picked (F-EX2)
FU = {235: 360.0, 275: 430.0, 355: 470.0, 420: 520.0, 460: 540.0}   # EN 10025-2 Table 7 (t < 100 mm)


# ------------------------------------------------------------------------------------------------ helpers
def calibration(path, what):
    c = load_json(path)
    block = need(c, what, os.path.basename(path))
    return block, str(block.get("status", "UNCALIBRATED")).upper()


def calib_note(rep, path):
    """A calibration file other than tools/calibration.json is refused (review A-16) unless TOOLS_TEST=1 (tests)."""
    if os.path.abspath(path) != os.path.abspath(CALIB):
        if os.environ.get("TOOLS_TEST") != "1":
            rep.check("calibration_file", "CANNOT_RUN", got=os.path.abspath(path), expected=CALIB,
                      error="only tools/calibration.json may be used; never pass --calibration (tests set TOOLS_TEST=1)")
            rep.emit()
        rep.check("calibration_file", "ESCALATE", got=os.path.abspath(path), expected=CALIB,
                  error="test calibration file (TOOLS_TEST=1): never a clean PASS")


def lc_rows(path):
    obj = unwrap(load_json(path))
    rows = rows_of(obj, os.path.basename(path))
    return obj, rows


def _f(v):
    return None if v is None else float(v)


def eta_of(m):
    vals = [m[k] for k in ("eta_bdk", "eta_aqb") if m.get(k) is not None]
    return max(vals) if vals else None


# ------------------------------------------------------------------------------------------------ alpha
def cmd_alpha(a):
    rep = Report("member_check_alpha", a.workdir, {"load_cases": input_record(a.load_cases, "load_cases")})
    block, status = calibration(a.calibration, "alpha_cr")
    calib_note(rep, a.calibration)
    want = parse_ids(a.buckling_lcs)
    if not want:
        raise MissingField("--buckling-lcs is empty: give the buckling LC numbers (ASE EIGE ... ETYP BUCK LC)")
    if status != "CALIBRATED" or block.get("rule") not in RULES:
        rep.extra.update(alpha_cr_min="UNCALIBRATED", alpha_cr_lc=None, alpha_cr_mode=None)
        rep.check("G6_calibration", "CANNOT_RUN", got=status, expected="CALIBRATED with a known rule",
                  error="how the ASE buckling factor is stored in the CDB is not calibrated: STOP S7-UNCALIBRATED "
                        "(README 'member results')")
        rep.emit()
    rule = block["rule"]
    obj, rows = lc_rows(a.load_cases)
    if stale_of(obj):
        rep.check("R4_stale", "FAIL", error="stale_results_warning: " + " | ".join(stale_of(obj)))
    by = {}
    for r in rows:
        by[int(need(r, "lc", "load_cases row"))] = r
    modes, bad = [], []
    for lc in want:
        r = by.get(lc)
        if r is None:
            bad.append(f"LC {lc} not in load_cases")
            continue
        if int(need(r, "kind", f"LC {lc}")) != 4:
            bad.append(f"LC {lc} kind {r.get('kind')} is not an eigen LC (4)")
            continue
        f = r.get("frequency_Hz")
        if f is None:
            bad.append(f"LC {lc} has no frequency_Hz (m_omega 0)")
            continue
        lam = RULES[rule](num(f, f"LC {lc} frequency_Hz"))
        modes.append({"lc": lc, "mode": r.get("mode"), "frequency_Hz": f, "lambda": round(lam, 6),
                      "title": r.get("title")})
    if bad:
        rep.check("G6_buckling_lcs", "FAIL", count=len(bad), errors=bad[:40],
                  expected=f"{len(want)} eigen LCs", got=f"{len(want) - len(bad)}")
    pos = [m for m in modes if m["lambda"] > 0]
    if not pos:
        rep.extra.update(alpha_cr_min=None)
        rep.check("G6_alpha_cr", "FAIL", error="no positive buckling factor among the buckling LCs")
        rep.emit()
    lo = min(pos, key=lambda m: m["lambda"])
    v = lo["lambda"]
    verdict = "PASS" if v >= ALPHA_PASS else "ESCALATE"
    why = ("non-sway: first-order BDK valid" if v >= ALPHA_PASS else
           "S7-SWAY: alpha_cr < 10 (local mode or sway frame); the TH2 route is the lead's decision"
           if v >= ALPHA_LOW else "S7-SWAY: alpha_cr < 3: second-order with imperfections needed")
    rep.extra.update(alpha_cr_min=v, alpha_cr_lc=lo["lc"], alpha_cr_mode=lo["mode"], rule=rule,
                     modes_read=len(modes), negative_modes=len(modes) - len(pos),
                     lowest_five=sorted(pos, key=lambda m: m["lambda"])[:5])
    rep.check("G6_alpha_cr", verdict, expected=">= 10", got=v, lc=lo["lc"], mode=lo["mode"], meaning=why)
    if a.beam_map:
        mesh_check(rep, mesh_count(a.beam_map, a.dat, a.compression_forces or (), a.all_members))
    else:
        rep.check("G6_mesh", "ESCALATE", error="mesh not measured (give --beam-map): alpha_cr NOT PROVEN")
    rep.note(f"lambda = {rule}: {block.get('rules_known', {}).get(rule, '')}; evidence: {block.get('evidence')}")
    rep.note("Mesh rule: at least 8 (better 10+) elements per span in the eigen run, else the factors are too high.")
    rep.emit()


def cmd_calibrate_alpha(a):
    rep = Report("member_check_calibrate", a.workdir, {"load_cases": input_record(a.load_cases, "load_cases")})
    ref = BE13_REF
    if a.ref:
        ref = {}
        for part in a.ref.split(","):
            k, v = part.split("=")
            ref[int(k)] = float(v)
    obj, rows = lc_rows(a.load_cases)
    by = {int(need(r, "lc", "row")): r for r in rows}
    fs = {}
    for lc in ref:
        r = by.get(lc)
        if r is None or r.get("frequency_Hz") is None:
            raise MissingField(f"LC {lc}: no row or no frequency_Hz in {a.load_cases}")
        if int(need(r, "kind", f"LC {lc}")) != 4:
            raise MissingField(f"LC {lc} is kind {r.get('kind')}, not an eigen LC (4)")
        fs[lc] = num(r["frequency_Hz"], "frequency_Hz")
    table, ok = {}, []
    for name, fn in RULES.items():
        got = {lc: fn(f) for lc, f in fs.items()}
        dev = max(abs(got[lc] - ref[lc]) / ref[lc] for lc in ref)
        table[name] = {"lambda": {str(k): round(v, 4) for k, v in got.items()}, "max_dev": round(dev, 5)}
        if dev <= 0.005:
            ok.append(name)
    rep.extra["rules"] = table
    if len(ok) == 1:
        rep.extra["paste_into_calibration_json"] = {
            "alpha_cr": {"status": "CALIBRATED", "rule": ok[0],
                         "evidence": f"BE13 {sorted(ref)}: {table[ok[0]]['lambda']} vs {ref} "
                                     f"(max dev {table[ok[0]]['max_dev']}); file sha256 "
                                     f"{rep.inputs['load_cases']['sha256']}"}}
        rep.check("alpha_rule", "PASS", rule=ok[0], max_dev=table[ok[0]]["max_dev"])
    else:
        rep.check("alpha_rule", "FAIL", matching=ok, expected="exactly one rule within 0.5 %",
                  error="no single rule reproduces the known factors: read 12/LC CLC_EIGE with cdb_read_key and "
                        "look for the factor in the raw record")
    rep.emit()


# ------------------------------------------------------------------------------------------------ collect
def pages(paths, kwh, cls, what):
    """Read cdb_read_key pages -> {kwl: [records]}; FAIL loudly if a kwl's pages are incomplete."""
    by, counts = {}, {}
    for p in paths:
        o = unwrap(load_json(p))
        if not isinstance(o, dict):
            raise MissingField(f"{p} is not a cdb_read_key result")
        if o.get("error"):
            raise MissingField(f"{p} holds a tool error: {o['error']}")
        if int(need(o, "kwh", p)) != kwh:
            raise MissingField(f"{p} is key {o['kwh']}, expected {kwh} ({what})")
        kwl = int(need(o, "kwl", p))
        if int(need(o, "kexist", p)) < 2:
            raise MissingField(f"{p}: key {kwh}/{kwl} has no data (kexist {o['kexist']})")
        rc = int(need(o, "record_count", p))
        if counts.setdefault(kwl, rc) != rc:
            raise MissingField(f"{p}: record_count {rc} differs from another page of {kwh}/{kwl} "
                               f"({counts[kwl]}): pages from different runs")
        recs = need(o, "records", p)
        by.setdefault(kwl, []).extend(recs)
    for kwl, recs in by.items():
        if len(recs) != counts[kwl]:
            raise MissingField(f"{what} {kwh}/{kwl}: {len(recs)} of {counts[kwl]} records read; read every "
                               f"page (skip = 0, 500, 1000, ...) before collecting")
    return by


def cmd_collect(a):
    sys.path.insert(0, HERE)
    import _cadinp as C
    rep = Report("member_check_collect", a.workdir, {"dat": input_record(a.dat, "dat")})
    calib_note(rep, a.calibration)
    bblk, bst = calibration(a.calibration, "bdk")
    qblk, qst = calibration(a.calibration, "aqb")
    if bst != "CALIBRATED" or qst != "CALIBRATED":
        rep.check("H1_calibration", "CANNOT_RUN", got={"bdk": bst, "aqb": qst}, expected="CALIBRATED",
                  error="where BDK / AQB store utilisations is not calibrated: STOP S7-UNCALIBRATED")
        rep.emit()
    model = C.Model(C.Dat.from_file(a.dat))
    members = model.bdk_members()
    if not members:
        raise MissingField("no BDK MEMB records in the .dat")
    lcst = sorted({m["lcst"] for m in members if m["lcst"]})
    member_lcs = sorted({lc for m in members for lc in m["lcs"]})
    # BDK
    bdk = pages(a.bdk, int(bblk["kwh"]), bblk["class_name"], "BDK")
    miss_lcst = [s for s in lcst if s not in bdk]
    if miss_lcst:
        raise MissingField(f"BDK pages for LCST {miss_lcst} not given (have {sorted(bdk)})")
    eta_b = {}
    for kwl, recs in bdk.items():
        for r in recs:
            mid = int(need(r, bblk["id_field"], f"BDK {kwl} record"))
            if mid <= 0:
                continue
            v = num(need(r, bblk["eta_field"], f"BDK record {mid}"), bblk["eta_field"])
            eta_b[mid] = max(v, eta_b.get(mid, -1e9))
    # beam -> sln
    bm = unwrap(load_json(a.beam_map))
    b2s = {}
    for r in rows_of(bm, a.beam_map):
        if r.get("sln") is None:
            raise MissingField(f"beam {r.get('beam')} has no sln in {a.beam_map}")
        b2s[int(need(r, "beam", "beam row"))] = int(r["sln"])
    if isinstance(bm, dict) and bm.get("truncated"):
        raise MissingField(f"{a.beam_map} is truncated: re-read with a larger max_rows")
    # AQB
    aqb = pages(a.aqb, int(qblk["kwh"]), qblk["class_name"], "AQB")
    eta_q, lc_q, no_sln = {}, {}, set()
    for lc, recs in aqb.items():
        for r in recs:
            b = int(need(r, qblk["id_field"], f"AQB {lc} record"))
            if b <= 0:
                continue
            v = num(need(r, qblk["eta_field"], f"AQB record {b}"), qblk["eta_field"])
            s = b2s.get(b)
            if s is None:
                no_sln.add(b)
                continue
            if v > eta_q.get(s, -1e9):
                eta_q[s], lc_q[s] = v, lc
    if no_sln:
        rep.check("H1_aqb_beam_map", "FAIL", count=len(no_sln), beams=sorted(no_sln)[:40],
                  error="AQB beams not in the beam -> SLN map: read cdb_beam_forces of all beams for one LC")
    excluded, aqb_reasons = {}, {}
    if a.excluded:
        exf = unwrap(load_json(a.excluded))
        excluded = {str(k): v for k, v in need(exf, "excluded", a.excluded).items()}
        aqb_reasons = {str(k): v for k, v in (exf.get("aqb_only_reasons") or {}).items()}
    sec_name = model.sections
    mat_of = model.section_mno

    def section(sln):
        sno = (model.slns.get(sln) or {}).get("sno")
        if sno is None:
            raise MissingField(f"SLN {sln} has no SNO in the .dat")
        mno = mat_of.get(sno)
        if mno is None or mno not in model.materials:
            raise MissingField(f"section {sno}: material (MNO) not found in the .dat")
        # a section without AQUA PROF (e.g. a POLY plate section) keeps a plain name: hand gives 'not checkable'
        return sno, sec_name.get(sno, f"SECT {sno} (no PROF)"), model.materials[mno]

    out, in_bdk = [], set()
    for m in members:
        slns = [m["sln"]] + list(m["cont"])
        in_bdk.update(slns)
        sno, name, mat = section(m["sln"])
        qs = [(eta_q[s], lc_q[s]) for s in slns if s in eta_q]
        eq, lq = (max(qs) if qs else (None, None))
        cy = sorted(float(c["S"]) for c in (m.get("cvl") or []) if str(c.get("CY", "")).upper() == "FIX"
                    and isinstance(c.get("S"), float) and str(c.get("REF", "STRT")).upper() == "STRT")
        out.append({"member": str(m["id"]), "slns": slns, "section": name, "section_nr": sno, "material": mat,
                    "group": (model.slns.get(m["sln"]) or {}).get("grp"), "length_m": None,
                    "cy_fix_from_start_m": cy, "eta_bdk": eta_b.get(m["id"]), "lc_bdk": None,
                    "eta_aqb": eq, "lc_aqb": lq, "source": "BDK MEMB line %d" % m["line"]})
    for s, info in sorted(model.slns.items()):
        if info.get("sno") is None or s in in_bdk or s not in eta_q:
            continue
        sno, name, mat = section(s)
        out.append({"member": f"S{s}", "slns": [s], "section": name, "section_nr": sno, "material": mat,
                    "group": info.get("grp"), "length_m": None, "cy_fix_from_start_m": [],
                    "eta_bdk": None, "lc_bdk": None, "eta_aqb": eta_q[s], "lc_aqb": lc_q[s],
                    "source": "AQB only"})
    mr = {"calibration": {"bdk": bblk.get("evidence"), "aqb": qblk.get("evidence")},
          "source": {"bdk_pages": [input_record(p, "bdk") for p in a.bdk],
                     "aqb_pages": [input_record(p, "aqb") for p in a.aqb],
                     "beam_map": input_record(a.beam_map, "beam_map"), "dat": rep.inputs["dat"]},
          "member_lcs": member_lcs, "lcst": lcst,
          "lc_note": "BDK stores one envelope per LCST: lc_bdk is not stored; pick uses lc_aqb (governing AQB LC "
                     "of the member) as the hand-check LC [I]",
          "members": out}
    cm = {"source": f"member_check collect: {bblk['kwh']}/{lcst} {bblk['class_name']} + {qblk['kwh']}/LC "
                    f"{qblk['class_name']} ({len(aqb)} LCs)",
          "bdk_checked": sorted(eta_b), "aqb_checked_slns": sorted(eta_q), "excluded": excluded,
          "aqb_only_reasons": aqb_reasons}
    os.makedirs(a.workdir, exist_ok=True)
    for name, o in (("member_results.json", mr), ("checked_members.json", cm)):
        with open(os.path.join(a.workdir, name), "w", encoding="utf-8") as f:
            json.dump(o, f, indent=1)
    aqb_lcs = sorted(aqb)
    outside = [lc for lc in aqb_lcs if lc not in member_lcs]
    rep.check("R6_aqb_lcs", "ESCALATE" if outside else "PASS", lc_outside_set=outside, aqb_lcs=len(aqb_lcs))
    missing = [lc for lc in member_lcs if lc not in aqb]
    rep.check("H1_aqb_pages", "FAIL" if missing else "PASS", missing_lcs=missing[:40],
              expected=f"AQB pages for {len(member_lcs)} member LCs")
    rep.check("H1_collect", "PASS", members=len(out), bdk_members=len(eta_b), aqb_slns=len(eta_q))
    rep.emit()


# ------------------------------------------------------------------------------------------------ pick
def load_members(path):
    mr = unwrap(load_json(path))
    ms = need(mr, "members", path)
    if not isinstance(ms, list) or not ms:
        raise MissingField(f"{path}: 'members' is empty")
    for m in ms:
        for k in ("member", "slns", "section", "eta_bdk", "eta_aqb"):
            if k not in m:
                raise MissingField(f"member {m.get('member')}: field '{k}' missing in {path}")
        if m["eta_bdk"] is None and m["eta_aqb"] is None:
            raise MissingField(f"member {m['member']}: neither eta_bdk nor eta_aqb")
    return mr, ms




def cmd_pick(a):
    rep = Report(TOOL, a.workdir, {"member_results": input_record(a.member_results, "member_results"),
                                   "env": input_record(a.env, "env")})
    rep.extra["action"] = "pick"
    mr, ms = load_members(a.member_results)
    member_lcs = set(int(x) for x in need(mr, "member_lcs", a.member_results))
    env = unwrap(load_json(a.env))
    if not isinstance(env, dict) or env.get("error"):
        raise MissingField(f"{a.env}: not an envelope result ({(env or {}).get('error') if isinstance(env, dict) else env})")
    nmin = need(need(need(env, "overall", a.env), "N", "overall"), "min", "overall.N")
    found = [int(x) for x in need(env, "load_cases_found", a.env)]

    def lc_of(m):
        return m.get("lc_bdk") if m.get("lc_bdk") is not None else m.get("lc_aqb")

    picks, order = {}, []

    def add(m, reason, lc=None):
        lc = lc_of(m) if lc is None else lc
        k = (str(m["member"]), lc)
        if k not in picks:
            picks[k] = {"member": k[0], "sln": ",".join(str(s) for s in m["slns"]), "section": m["section"],
                        "lc": lc, "eta_bdk": m["eta_bdk"], "eta_aqb": m["eta_aqb"], "reason": reason}
            order.append(k)
        elif reason not in picks[k]["reason"]:
            picks[k]["reason"] += "; " + reason

    bd = sorted((m for m in ms if m["eta_bdk"] is not None), key=lambda m: -m["eta_bdk"])
    for i, m in enumerate(bd[:3], 1):
        add(m, f"BDK top {i}")
    aq = sorted((m for m in ms if m["eta_aqb"] is not None), key=lambda m: -m["eta_aqb"])
    for i, m in enumerate(aq[:3], 1):
        add(m, f"AQB top {i}")
    # every member with eta >= 0.9 (BDK or AQB) is picked (review F-EX2); never dropped by the cap
    hi = sorted((m for m in ms if (eta_of(m) or 0) >= HIGH_ETA), key=lambda m: -(eta_of(m) or 0))
    for m in hi:
        tag = [f"BDK {m['eta_bdk']}" for _ in [0] if m["eta_bdk"] is not None and m["eta_bdk"] >= HIGH_ETA] + \
              [f"AQB {m['eta_aqb']}" for _ in [0] if m["eta_aqb"] is not None and m["eta_aqb"] >= HIGH_ETA]
        add(m, f"eta >= {HIGH_ETA} ({', '.join(tag)})")
    # largest compression BEFORE the random picks (review A-13), checked under its own LC
    s, v = nmin.get("sln"), nmin.get("value")
    if s is None or v is None:
        rep.check("G7_compression_pick", "ESCALATE", error="env overall.N.min has no sln/value: compression "
                                                           "member not picked", got=nmin)
    else:
        comp = next((m for m in ms if int(s) in [int(x) for x in m["slns"]]), None)
        if comp is None:
            rep.check("G7_compression_pick", "ESCALATE", error=f"SLN {s} of N min not in member_results")
        else:
            lcc = nmin.get("lc") if (v < 0 and nmin.get("lc") is not None) else None
            add(comp, f"largest compression N = {v} kN (LC {nmin.get('lc')}, SLN {s})",
                int(lcc) if lcc is not None else None)
    n_mandatory = len(order)          # top-3s, every eta >= 0.9, the compression pick: never capped
    seed = int(hashlib.sha256(str(a.seed).encode()).hexdigest()[:16], 16)
    rng = random.Random(seed)
    by_sec = {}
    for m in ms:
        by_sec.setdefault(m["section"], []).append(m)
    for sec in sorted(by_sec):
        cand = sorted(by_sec[sec], key=lambda m: str(m["member"]))
        add(rng.choice(cand), f"random {sec}")
    lst = [picks[k] for k in order][:max(PICK_CAP, n_mandatory)]
    dropped_random = len(order) - len(lst)
    etas = [eta_of(m) for m in ms if eta_of(m) is not None]
    outside = sorted({lc for lc in [lc_of(m) for m in ms] + found + [nmin.get("lc")]
                      if lc is not None and int(lc) not in member_lcs})
    gt1 = sorted((m for m in ms if (eta_of(m) or 0) > 1.0), key=lambda m: -eta_of(m))
    stats = {"n_members": len(ms), "eta_max": max(etas), "eta_min": min(etas), "n_eta_gt_1": len(gt1),
             "lc_outside_set": outside,
             "members_gt_1": [{"member": m["member"], "eta": eta_of(m), "section": m["section"]} for m in gt1[:40]]}
    nolc = [p["member"] for p in lst if p["lc"] is None]
    rep.extra.update(picks=lst, stats=stats, seed=str(a.seed))
    rep.check("G7_lc_set", "ESCALATE" if outside else "PASS", lc_outside_set=outside,
              expected="every governing / envelope LC in member_lcs")
    if nolc:
        rep.check("G7_pick_lc", "ESCALATE", members=nolc, error="no governing LC known for these picks")
    hi_keys = {str(m["member"]) for m in hi}
    lost = sorted(hi_keys - {p["member"] for p in lst})
    rep.check("G7_high_eta_picked", "FAIL" if lost else "PASS", members_eta_ge_0_9=len(hi_keys), not_picked=lost)
    if n_mandatory > PICK_CAP:
        rep.check("G7_picks_over_cap", "ESCALATE", picks_over_cap=n_mandatory - PICK_CAP, cap=PICK_CAP,
                  count=len(lst), meaning=f"{n_mandatory} mandatory picks (top-3, every eta >= {HIGH_ETA}, "
                  "compression) exceed the cap; all are kept, the lead decides whether to hand-check them all")
    rep.extra.update(n_mandatory=n_mandatory, n_eta_ge_0_9=len(hi_keys), random_dropped_by_cap=dropped_random)
    rep.check("G7_picks", "PASS" if lst else "FAIL", count=len(lst))
    rep.emit()


# ------------------------------------------------------------------------------------------------ hand
def stitch(rows, slns):
    """Element rows of one member -> member stations [x, N, Vy, Vz, Mt, My, Mz] (beams in SLN order, then by beam
    number; x offset by the preceding element lengths) [I: geometry not in the forces; continuity is checked]."""
    rank = {s: i for i, s in enumerate(slns)}
    by = {}
    for r in rows:
        by.setdefault(int(r["beam"]), []).append(r)
    beams = sorted(by, key=lambda b: (rank[int(by[b][0]["sln"])], b))
    out, off, joints = [], 0.0, []
    prev_end = None
    for b in beams:
        rs = sorted(by[b], key=lambda r: num(r["x"], "x"))
        L = num(rs[-1]["x"], "x")
        if prev_end is not None:
            joints.append((b, prev_end, num(rs[0]["My"], "My")))
        for r in rs:
            out.append([off + num(r["x"], "x")] + [num(need(r, k, f"beam {b}"), k)
                                                   for k in ("N", "Vy", "Vz", "Mt", "My", "Mz")])
        prev_end = num(rs[-1]["My"], "My")
        off += L
    return out, off, joints, beams


def ltb_rule(path):
    try:
        blk, st = calibration(path, "ltb_load_height")
    except MissingField:
        return "max", "no ltb_load_height item"
    if st == "CALIBRATED" and blk.get("rule") == "shear_centre":
        return "shear_centre", blk.get("evidence")
    return "max", "UNCALIBRATED: max(shear centre, top flange) is used (review A-03)"


def route_verdict(sof, hand, tol, governing_lc_checked):
    """Compare one SOFiSTiK envelope value with the hand maximum.  governing_lc_checked False = the hand value
    covers only some LCs, so a LOWER hand value proves nothing (A-14)."""
    d = hand - sof
    if sof > MARGIN[1] and hand > MARGIN[1]:
        return "FAIL", "both routes > 1.1: member fails (report only)"
    if MARGIN[0] <= sof <= MARGIN[1] or MARGIN[0] <= hand <= MARGIN[1]:
        return "ESCALATE", "marginal 0.9-1.1, engineer to judge"
    if abs(d) > tol:
        if d < 0 and not governing_lc_checked:
            return "ESCALATE", (f"hand {hand:.3f} below the SOFiSTiK envelope {sof:.3f} but the governing LC was not "
                                "hand-checked: give --extra-forces for all member LCs")
        return "ESCALATE", f"routes disagree by {abs(d):.3f} > {tol:.3f}"
    if (sof > 1.0) != (hand > 1.0):
        return "ESCALATE", "routes differ on PASS/FAIL"
    return "PASS", "agree"


def design_lc(a, nc, m, fpath, ov, sec, mat, dp, ec3):
    """One forces file -> (lc, {lp: MemberDesign}, info)."""
    fo = unwrap(load_json(fpath))
    if isinstance(fo, dict) and fo.get("error"):
        nc(f"beam forces {os.path.basename(fpath)}: {fo['error']}")
    lc = int(need(fo, "lc", fpath))
    rows_all = rows_of(fo, fpath)
    if fo.get("truncated") or (fo.get("max_rows") and len(rows_all) >= int(fo["max_rows"])):
        nc(f"forces truncated in {os.path.basename(fpath)}: re-read with a narrower request")
    slns = [int(s) for s in m["slns"]]
    rows = [r for r in rows_all if r.get("sln") is not None and int(r["sln"]) in slns]
    if not rows:
        nc(f"no beam rows of SLN {slns} in {os.path.basename(fpath)}")
    st, L, joints, beams = stitch(rows, slns)
    mmax = max(abs(r[5]) for r in st)
    jumps = [(b, pe, ps) for b, pe, ps in joints if abs(pe - ps) > 0.05 * mmax + 0.5]
    if jumps:
        nc("My jumps where elements meet (element order unknown without node coordinates)",
           jumps=[{"beam": b, "My_end_prev": pe, "My_start": ps} for b, pe, ps in jumps[:10]])
    rotated = False
    iy, iz = ov.get("Iy_cm4"), ov.get("Iz_cm4")
    if iy is not None and iz is not None and sec["props"]["Iy"] > 1.05 * sec["props"]["Iz"] and iy < iz / 1.05:
        rotated = True     # same as sofrep cdb_reader.rotate_rows_to_major: Vy'=Vz, Vz'=-Vy, My'=Mz, Mz'=-My
        st = [[r[0], r[1], r[3], -r[2], r[4], r[6], -r[5]] for r in st]
    cy = sorted(x for x in (m.get("cy_fix_from_start_m") or []) if 0 < x < L)
    pts = [0.0] + cy + [L]
    seg = max(b - a_ for a_, b in zip(pts, pts[1:]))
    member = {"member_id": str(a.member), "length": L, "role": "beam"}
    res = {}
    for lp in ("shear_centre", "top_flange"):
        p = dp.defaults(member, sec, "EC3")
        p.update(national_annex="UK", load_position=lp, L_y=L, L_z=seg, L_LT=seg,
                 _source="member_check hand: UK NA; L_y = member length; L_z = L_LT = longest span between "
                         "BDK CVL CY FIX points [I]")
        res[lp] = ec3.design_member(member, sec, mat, p, str(lc), st)
    if stale_of(fo):
        nc("stale results: " + " | ".join(stale_of(fo)))
    return lc, res, {"length_m": round(L, 4), "L_LT_m": round(seg, 4), "beams": beams, "rotated": rotated}


def cmd_hand(a):
    files = [a.forces] + list(a.extra_forces or [])
    ins = {"forces": input_record(a.forces, "forces"), "overview": input_record(a.overview, "overview"),
           "member_results": input_record(a.member_results, "member_results")}
    rep = Report(TOOL, a.workdir, ins)
    rep.extra.update(action="hand", member=str(a.member), lc=int(a.lc))

    def nc(why, **kw):
        rep.check("G7_hand", "CANNOT_RUN", error="not hand-checkable: " + why, **kw)
        rep.emit()

    mr, ms = load_members(a.member_results)
    member_lcs = set(int(x) for x in (mr.get("member_lcs") or []))
    m = next((x for x in ms if str(x["member"]) == str(a.member)), None)
    if m is None:
        raise MissingField(f"member {a.member} not in {a.member_results}")
    for k in ("section_nr", "material"):
        need(m, k, f"member {a.member}")
    fo0 = unwrap(load_json(a.forces))
    if isinstance(fo0, dict) and not fo0.get("error") and int(need(fo0, "lc", a.forces)) != int(a.lc):
        rep.check("G7_forces_lc", "FAIL", expected=int(a.lc), got=fo0["lc"], error="forces are for another LC")
        rep.emit()
    sys.path.insert(0, a.sofrep)
    try:
        from sofrep import design_params as dp
        from sofrep import sections as secs
        from sofrep.codes import ec3
    except Exception as e:  # noqa: BLE001
        nc(f"sofrep not importable from {a.sofrep}: {type(e).__name__}: {e}")
    sec = secs.from_name(m["section"])
    if not sec:
        nc(f"section '{m['section']}' not in the sofrep catalogue")
    ov = unwrap(load_json(a.overview))
    osec = next((s for s in need(ov, "sections", a.overview) if int(s.get("nr", -1)) == int(m["section_nr"])), None)
    if osec is None:
        raise MissingField(f"section {m['section_nr']} not in {a.overview}")
    A_cdb = num(need(osec, "A_cm2", f"overview section {m['section_nr']}"), "A_cm2") * 100.0
    A_cat = float(sec["props"]["A"])
    if abs(A_cdb - A_cat) > 0.03 * A_cat:
        nc(f"section area differs: CDB {A_cdb:.0f} mm2 vs catalogue {m['section']} {A_cat:.0f} mm2 (> 3 %)")
    g = re.search(r"(\d{3})", str(m["material"]))
    if not g:
        raise MissingField(f"material '{m['material']}' has no grade number")
    fy = float(g.group(1))
    if int(fy) not in FU:
        nc(f"grade {fy:g} not in the fu table")
    mat = {"name": f"S{int(fy)}", "fy": fy, "fu": FU[int(fy)], "E": 210000.0, "G": 81000.0,
           "thickness_dependent": True}
    rule, rule_why = ltb_rule(a.calibration)

    def mx(md_, pre):
        rs = [c.ratio for c in md_.checks if str(c.clause).startswith(pre) and c.status in ("PASS", "FAIL")]
        return round(max(rs), 4) if rs else None

    hand_dir = os.path.join(a.workdir, "hand")
    os.makedirs(hand_dir, exist_ok=True)
    per_lc, info0 = {}, None
    for fp in files:
        lc, res, info = design_lc(a, nc, m, fp, osec, sec, mat, dp, ec3)
        info0 = info0 or info
        with open(os.path.join(hand_dir, f"{a.member}_{lc}.json"), "w", encoding="utf-8") as f:
            json.dump({lp: r.to_dict() for lp, r in res.items()}, f, indent=1, default=str)
        sc, tf = res["shear_centre"], res["top_flange"]
        b_sc, b_tf = mx(sc, "6.3"), mx(tf, "6.3")
        b_eff = b_sc if rule == "shear_centre" else (max(x for x in (b_sc, b_tf) if x is not None)
                                                     if (b_sc is not None or b_tf is not None) else None)
        per_lc[lc] = {"aqb": mx(sc, "6.2"), "bdk_sc": b_sc, "bdk_tf": b_tf, "bdk": b_eff,
                      "governing": sc.governing_check, "warnings": sc.warnings[:4]}
    lcs_done = sorted(per_lc)
    h_aqb_lc = per_lc[int(a.lc)]["aqb"]
    bdk_vals = [v["bdk"] for v in per_lc.values() if v["bdk"] is not None]
    h_bdk = max(bdk_vals) if bdk_vals else None
    h_bdk_lc = max(per_lc, key=lambda k: per_lc[k]["bdk"] if per_lc[k]["bdk"] is not None else -1)
    e_aqb, e_bdk = m.get("eta_aqb"), m.get("eta_bdk")
    all_lcs = bool(member_lcs) and member_lcs <= set(lcs_done)
    rep.extra.update(hand_aqb=h_aqb_lc, hand_bdk=h_bdk, hand_bdk_lc=h_bdk_lc,
                     hand_bdk_shear_centre=per_lc[int(a.lc)]["bdk_sc"],
                     hand_bdk_top_flange=per_lc[int(a.lc)]["bdk_tf"], load_height_rule=rule,
                     eta_aqb=e_aqb, eta_bdk=e_bdk, lcs_hand_checked=lcs_done, all_member_lcs_checked=all_lcs,
                     length_m=info0["length_m"], L_LT_m=info0["L_LT_m"], beams=info0["beams"],
                     rotated_to_major=info0["rotated"], governing=per_lc[int(a.lc)]["governing"],
                     warnings=per_lc[int(a.lc)]["warnings"], per_lc=per_lc,
                     saved=os.path.join(hand_dir, f"{a.member}_{a.lc}.json"))
    # AQB (6.2): the hand value at the AQB-governing LC, if it was checked
    if e_aqb is not None:
        if h_aqb_lc is None:
            nc("AQB has a utilisation but sofrep gave no 6.2 ratio")
        gov = m.get("lc_aqb") is not None and int(m["lc_aqb"]) in per_lc
        hv = per_lc[int(m["lc_aqb"])]["aqb"] if gov else max(v["aqb"] for v in per_lc.values() if v["aqb"] is not None)
        v, why = route_verdict(float(e_aqb), hv, TOL_AQB, gov)
        rep.check("G7_aqb", v, eta_sofistik=float(e_aqb), eta_hand=hv, tolerance=TOL_AQB, meaning=why)
    # member buckling (6.3)
    if e_bdk is not None:
        if h_bdk is None:
            nc("BDK has a utilisation but sofrep gave no 6.3 ratio: member buckling not hand-checked")
        tol = max(TOL_BDK_ABS, TOL_BDK_REL * float(e_bdk))
        v, why = route_verdict(float(e_bdk), h_bdk, tol, all_lcs)
        rep.check("G7_bdk", v, eta_sofistik=float(e_bdk), eta_hand=h_bdk, hand_lc=h_bdk_lc, tolerance=round(tol, 4),
                  meaning=why, load_height=rule)
    else:
        # review A-01: no SOFiSTiK buckling value -> the hand 6.3 value governs; never PASS without it
        if h_bdk is None:
            nc("no member-buckling value at all: SOFiSTiK has no BDK result and sofrep gave no 6.3 ratio")
        if h_bdk > MARGIN[1]:
            v, why = "FAIL", f"member buckling not checked by SOFiSTiK; hand 6.3 = {h_bdk:.3f} > 1.1"
        elif h_bdk > MARGIN[0]:
            v, why = "ESCALATE", f"member buckling not checked by SOFiSTiK; hand 6.3 = {h_bdk:.3f} > 0.9"
        elif not all_lcs:
            # review N-02: one LC (usually the AQB / cross-section governing one) says nothing about buckling
            # under the other member LCs (FI-7: 0.398 at LC 102, 2.249 at LC 145)
            missing = sorted(member_lcs - set(lcs_done))
            v, why = "ESCALATE", (f"member buckling not checked by SOFiSTiK; hand 6.3 = {h_bdk:.3f} at LCs {lcs_done} "
                                  f"only: give --extra-forces for all member LCs ({len(missing)} missing, e.g. "
                                  f"{missing[:8]})")
        else:
            v, why = "PASS", (f"member buckling not checked by SOFiSTiK; hand 6.3 = {h_bdk:.3f} <= 0.9 over all "
                              f"{len(lcs_done)} member LCs")
        rep.check("G7_bdk_hand_only", v, eta_hand=h_bdk, hand_lc=h_bdk_lc, load_height=rule, meaning=why)
    if rule != "shear_centre":
        rep.note("Load height: " + rule_why)
    if not all_lcs:
        rep.note(f"Hand-checked LCs {lcs_done}; eta_bdk is BDK's envelope over all member LCs [I]. A hand value "
                 "below it is consistent only when every member LC is checked (--extra-forces).")
    if info0["rotated"]:
        rep.note("CDB section has Iy < Iz: forces rotated to the major axis (as sofrep cdb_reader).")
    rep.emit()


# ------------------------------------------------------------------------------------------------ mesh (A-07)
def mesh_count(beam_map, dat=None, forces=(), all_members=False):
    """-> (counts {sln: elements}, basis text).  Default (review round 2): only SLNs in COMPRESSION are measured
    (the short ring chords in bending do not decide alpha_cr).  Compression comes from --compression-forces
    (rows with sln and N < 0), else from the N values of the beam map itself; with neither, counts = None
    (fail closed: alpha_cr NOT PROVEN).  all_members=True measures every SLN (the old behaviour)."""
    bm = unwrap(load_json(beam_map))
    rows = rows_of(bm, beam_map)
    if isinstance(bm, dict) and (bm.get("truncated") or (bm.get("max_rows") and len(rows) >= int(bm["max_rows"]))):
        raise MissingField(f"{beam_map} is truncated: re-read (ends_only=true)")
    per = {}
    for r in rows:
        if r.get("sln") is None:
            continue
        per.setdefault(int(r["sln"]), set()).add(int(need(r, "beam", "beam row")))
    want = set(per)
    if dat:
        import _cadinp as C
        model = C.Model(C.Dat.from_file(dat))
        want &= {s for s, v in model.slns.items() if v.get("sno") is not None}
    if all_members:
        return {s: len(per[s]) for s in want}, "all structural lines (--all-members)"

    def comp_of(rs):
        return {int(r["sln"]) for r in rs if r.get("sln") is not None and r.get("N") is not None
                and num(r["N"], "N") < 0}
    if forces:
        comp = set()
        lcs = []
        for fp in forces:
            fo = unwrap(load_json(fp))
            comp |= comp_of(rows_of(fo, fp))
            lcs.append(fo.get("lc") if isinstance(fo, dict) else None)
        basis = f"SLNs in compression in --compression-forces (LC {lcs})"
    elif rows and all(r.get("N") is not None for r in rows):
        comp = comp_of(rows)
        basis = (f"SLNs in compression in the beam map's own LC {bm.get('lc') if isinstance(bm, dict) else None} "
                 "only; pass --compression-forces for every primary combination (SYST PLC) to cover them all")
    else:
        return None, "no forces: neither --compression-forces nor N in the beam map"
    want &= comp
    return {s: len(per[s]) for s in want}, basis


def mesh_check(rep, counted, cid="G6_mesh"):
    counts, basis = counted if isinstance(counted, tuple) else (counted, None)
    rep.extra["mesh_basis"] = basis
    if counts is None:
        rep.check(cid, "ESCALATE", error=f"{basis}: compression members unknown, alpha_cr NOT PROVEN (fail closed)")
        return None
    if not counts:
        rep.check(cid, "ESCALATE", error="no structural line to measure: alpha_cr NOT PROVEN")
        return None
    lo = min(counts.values())
    worst = sorted(counts, key=lambda s: counts[s])[:10]
    v = "PASS" if lo >= 8 else "ESCALATE"
    rep.check(cid, v, expected=">= 8 elements per structural line", got=lo, basis=basis,
              worst=[{"sln": s, "elements": counts[s]} for s in worst],
              meaning="mesh adequate" if v == "PASS" else "eigen mesh below 8 elements per span: alpha_cr NOT PROVEN")
    rep.extra["eigen_el_per_span"] = lo
    return lo


def cmd_mesh(a):
    rep = Report("member_check_mesh", a.workdir, {"beam_map": input_record(a.beam_map, "beam_map")})
    mesh_check(rep, mesh_count(a.beam_map, a.dat, a.compression_forces or (), a.all_members))
    rep.note("Elements per structural line from the beam map (cdb_beam_forces ends_only) [I: an SLN is one span "
             "between joints]. Restricted to SLNs with a section (--dat) and, by default, to SLNs in compression "
             "(--compression-forces, else the beam map's own N); --all-members measures every SLN.")
    rep.emit()


# ------------------------------------------------------------------------------------------------ calibrate-bdk (A-23)
def cmd_calibrate_bdk(a):
    rep = Report("member_check_calibrate", a.workdir)
    blk, _ = calibration(CALIB, "bdk")
    by = pages(a.bdk, int(blk["kwh"]), blk["class_name"], "BDK")
    try:
        prt = json.loads(a.prt)
    except json.JSONDecodeError as e:
        raise MissingField(f"--prt is not JSON: {e}")
    if len(prt) < 5:
        raise MissingField("--prt needs at least 5 members (A-23)")
    cols = {str(v[1]).lower() for v in prt.values()}
    if len(cols) < 2:
        raise MissingField("--prt members must have at least 2 different governing ECHO SUM columns (A-23)")
    recs = {}
    for kwl, rs in by.items():
        for r in rs:
            mid = r.get(blk["id_field"])
            if isinstance(mid, int) and mid > 0:
                recs.setdefault(mid, []).append(r)
    fields = sorted({k for rs in recs.values() for r in rs for k, x in r.items()
                     if isinstance(x, (int, float)) and not isinstance(x, bool) and k != blk["id_field"]})
    match = {}
    for fld in fields:
        ok = True
        for mid, (val, _col) in prt.items():
            rs = recs.get(int(mid))
            if not rs:
                raise MissingField(f"member {mid} has no record in the BDK pages")
            got = max(float(r.get(fld) or 0) for r in rs)
            if abs(got - float(val)) > 0.01:
                ok = False
                break
        if ok:
            match[fld] = True
    if len(match) == 1:
        f0 = next(iter(match))
        rep.extra["paste_into_calibration_json"] = {"bdk": {"status": "CALIBRATED", "eta_field": f0,
                                                            "evidence": f"{len(prt)} members, columns {sorted(cols)}"}}
        rep.check("bdk_field", "PASS", field=f0)
    else:
        rep.check("bdk_field", "FAIL", matching=sorted(match), expected="exactly one field equal to the ECHO SUM "
                                                                         "'Check' value within 0.01 on every member")
    rep.emit()


def main():
    import argparse
    ap = Parser(TOOL, description="member results: alpha_cr, mesh, collect, pick, hand-check",
                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("alpha")
    p.add_argument("load_cases")
    p.add_argument("--buckling-lcs", dest="buckling_lcs", required=True)
    p.add_argument("--beam-map", dest="beam_map", help="cdb_beam_forces ends_only result: measures the mesh (A-07)")
    p.add_argument("--dat")
    p.add_argument("--compression-forces", dest="compression_forces", nargs="+")
    p.add_argument("--all-members", dest="all_members", action="store_true")
    c = sub.add_parser("calibrate-alpha")
    c.add_argument("load_cases")
    c.add_argument("--ref")
    cb = sub.add_parser("calibrate-bdk")
    cb.add_argument("--bdk", nargs="+", required=True)
    cb.add_argument("--prt", required=True, help='JSON {"<member>": [check_value, "<ECHO SUM column>"], ...} >= 5')
    me = sub.add_parser("mesh")
    me.add_argument("beam_map")
    me.add_argument("--dat")
    me.add_argument("--compression-forces", dest="compression_forces", nargs="+")
    me.add_argument("--all-members", dest="all_members", action="store_true",
                    help="measure every structural line, not only those in compression")
    k = sub.add_parser("collect")
    k.add_argument("--dat", required=True)
    k.add_argument("--bdk", nargs="+", required=True)
    k.add_argument("--aqb", nargs="+", required=True)
    k.add_argument("--beam-map", dest="beam_map", required=True)
    k.add_argument("--excluded")
    q = sub.add_parser("pick")
    q.add_argument("member_results")
    q.add_argument("env")
    q.add_argument("--seed", required=True)
    h = sub.add_parser("hand")
    h.add_argument("forces")
    h.add_argument("overview")
    h.add_argument("member_results")
    h.add_argument("--member", required=True)
    h.add_argument("--lc", required=True, type=int)
    h.add_argument("--extra-forces", dest="extra_forces", nargs="+",
                   help="cdb_beam_forces results of the same member for the other member LCs (A-14)")
    h.add_argument("--sofrep", default=os.environ.get("SOFREP_PATH", SOFREP))
    for sp in (p, c, cb, me, k, q, h):
        sp.add_argument("--workdir", required=True)
        sp.add_argument("--calibration", default=CALIB, help="tests only (TOOLS_TEST=1); otherwise refused")
        sp.error = ap.error
    a = ap.parse_args()
    if not a.cmd:
        ap.error("give a subcommand: alpha, calibrate-alpha, calibrate-bdk, mesh, collect, pick or hand")
    if a.cmd in ("pick", "hand", "mesh", "calibrate-alpha", "calibrate-bdk") and \
            os.path.abspath(a.calibration) != os.path.abspath(CALIB) and os.environ.get("TOOLS_TEST") != "1":
        r = Report(TOOL, a.workdir)
        r.check("calibration_file", "CANNOT_RUN", error="never pass --calibration (tests set TOOLS_TEST=1)")
        r.emit()
    {"alpha": cmd_alpha, "calibrate-alpha": cmd_calibrate_alpha, "calibrate-bdk": cmd_calibrate_bdk,
     "mesh": cmd_mesh, "collect": cmd_collect, "pick": cmd_pick, "hand": cmd_hand}[a.cmd](a)


if __name__ == "__main__":
    run_main(TOOL, main)
