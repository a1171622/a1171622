#!/usr/bin/env python3
"""G5 combinations: (1) every COPY-built combination's stored reaction sum equals the sum the .dat says it is made
of, (2) the .dat's combination factors are EN 1990 + UK NA factors, (3) what reaction sums cannot prove is said.

usage: python3 -I combo_check.py <file.dat> <load_cases.json> --expected <expected.json> [--families JSON]
                                 [--workdir W]

<load_cases.json> = the saved result of cdb_load_cases (all load cases, or at least every combination and
every load case they COPY).  Shape (sofistik_mcp results.load_cases, server wraps the list as {"rows": [...]}):
  {"rows": [{"lc": 103, "title": "...", "kind": 1, "factor": 1.0, "dead_load_factors": [0, 0, -1.35],
             "sum_reactions_kN": [rx, ry, rz], "has_results": ["nodes", "beams"]}, ...], "cdb": "...",
   "stale_results_warning": [...]   (only when stale -> FAIL)}
<expected.json> = make_expected_26016.py output (used for mixed combinations and to find self-equilibrating
  parts).  Without --expected: C2 (mixed with forces of their own) and C5 give ESCALATE.

C1 forward superposition (never back-solved; 03 section 7 shows the LC basis is rank deficient):
  R_c = (FACD_c / FACD_ref) * R_ref  +  sum_b f_b * R_b  [ + R_own ]
  f_b from the .dat with its STO#/LET# values, LOOPs and IFs; R_b the stored sums of the copied LCs; ref = the pure
  self-weight LC (FACD, no loads, no COPY).  Tolerance (fixed): per component
  |R_c - pred| <= 0.1 % * (sum_b |f_b R_b| + |FACD part| + |R_own|) + 0.05 kN.
  C3: |dead_load_factors| = |FACD| of the .dat (1e-4).
  Mixed combinations (own load records + COPY, review A-02): R_own = 0 when every own record is force-free
  (temperature DT/DTXY, line moments: net reaction 0); otherwise R_own = -(F_c - sum_b f_b F_b) from expected.json;
  neither possible -> ESCALATE "not superposition-checked" (never a silent note).
C4 factors (review A-05): every COPY factor (and FACD) against EN 1990 Table A1.2 with the UK NA (NA.A1.1/NA.A1.2):
  class from the combination TYPE: (D) + 'EQU' in the title = EQU, (D) = STR (6.10), (R) characteristic,
  (F) frequent, (P) quasi-permanent; action family from the copied LC's TYPE (G, Q*, QH, W, S, T) or its title
  (EHF G / EHF Q / WL / wind / temperature), or --families '{"25": "W"}'.
    STR  G 1.35 / 1.25 / 1.0, variable 1.5 or 1.5*psi0 or 0     EQU  G 1.10 / 0.90, variable 1.5 / 1.5*psi0 / 0
    (R)  G 1.0, variable 1.0 / psi0 / 0    (F) G 1.0, variable psi1 / psi2 / 0    (P) G 1.0, variable psi2 / 0
    psi (UK NA Table NA.A1.1): imposed Cat A-E psi0 0.7 (E 1.0), psi1 0.5/0.7/0.9, psi2 0.3/0.6/0.8; roof Cat H
    (TYPE QH) 0.7/0/0; wind 0.5/0.2/0; snow 0.5/0.2/0; temperature 0.6/0.5/0.
  FAIL: a factor outside the set, FACD 0 in a classed combination, or two variable families at their full leading
  factor.  INTENDED factor (review N-01; set membership cannot tell favourable from unfavourable G):
    (a) a G factor stated in the title ('107 ULS 1.0G+W', '131 EQU 0.9G+W') must equal FACD and every G COPY factor;
    (b) with --expected holding "combination_factors" {"<combo>": {"facd", "copies": {"<lc>": factor}}}
        (make_expected_26016.py, from the generator's combination table) FACD and every COPY factor must equal the
        intended value (1e-4) and the set of copied LCs must be the intended set.  A copied LC the .dat writes as
        the combination's own force-free records (26016 temperature 91/92 in 136-139, 222-223) is listed under
        not_compared.  Without (b) a PASS means only "allowed EN 1990 + UK NA values" (intended_compared false).  ESCALATE: a copied LC whose action family is unknown.  Factors inside own load expressions (e.g.
  temperature #DTP*#GQT) are not separable: noted, not checked.
C5 self-equilibrating parts (review A-05): a copied atom whose applied net force is < 0.5 % of its gross
  (barriers, EHF pairs) and force-free own records (temperature) are NOT proven by reaction sums -> ESCALATE
  "not proven by reactions" (no member-force proof in v1).
Skipped with ESCALATE (never PASS): combinations solved by a TH2/TH3 ASE block.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cadinp as C  # noqa: E402
from _common import (MissingField, Parser, Report, input_record, load_json, num, rows_of, run_main,  # noqa: E402
                     stale_of, unwrap)

TOOL = "combo_check"
REL, ABS_KN, FACD_TOL, FTOL = 1e-3, 0.05, 1e-4, 1e-3
VACUOUS = 0.005
ZERO_FORCE_TYPES = {"DT", "DTX", "DTY", "DTZ", "DTXY", "MXX", "MYY", "MZZ"}
# UK NA to BS EN 1990 Table NA.A1.1: (psi0 set, psi1 set, psi2 set)
PSI = {"Q": ({0.7, 1.0}, {0.5, 0.7, 0.9}, {0.3, 0.6, 0.8}), "QH": ({0.7}, {0.0}, {0.0}),
       "W": ({0.5}, {0.2}, {0.0}), "S": ({0.5}, {0.2}, {0.0}), "T": ({0.6}, {0.5}, {0.0})}
G_SET = {"STR": {1.35, 1.25, 1.0}, "EQU": {1.1, 0.9}, "CHAR": {1.0}, "FREQ": {1.0}, "QP": {1.0}}


def lc_table(obj, where):
    rows = rows_of(obj, where)
    out = {}
    for r in rows:
        if not isinstance(r, dict) or "lc" not in r:
            raise MissingField(f"a row without 'lc' in {where}")
        out[int(r["lc"])] = r
    return out


def reactions(row, lc):
    v = row.get("sum_reactions_kN")
    if v is None:
        raise MissingField(f"LC {lc}: sum_reactions_kN missing (kind {row.get('kind')}); cannot superpose")
    if not isinstance(v, list) or len(v) != 3:
        raise MissingField(f"LC {lc}: sum_reactions_kN is not [rx, ry, rz]")
    return [num(x, f"LC {lc} sum_reactions_kN") for x in v]


def own_force_free(lc):
    """True when every own load record of the LC carries no net force (temperature, moments)."""
    for line, text, toks, *_ in lc.loads:
        up = [str(t).upper() for t in toks]
        if "TYPE" not in up or up.index("TYPE") + 1 >= len(up):
            return False
        if up[up.index("TYPE") + 1].strip("'") not in ZERO_FORCE_TYPES:
            return False
    return True


def family(m, n, over):
    if str(n) in over:
        return over[str(n)]
    lc = m.lcs.get(n)
    if lc is None:
        return None
    t = str(lc.type or "").upper().strip("'")
    if lc.facd and not lc.loads and not lc.copies:
        return "G"
    if t == "G" or t.startswith("G_"):
        return "G"
    if t == "QH":
        return "QH"
    if t.startswith("Q"):
        return "Q"
    if t in ("W", "S", "T"):
        return t
    ti = lc.title or ""
    if re.search(r"\bEHF\s+G\b", ti, re.I):
        return "G"
    if re.search(r"\bEHF\s+Q\b", ti, re.I):
        return "Q"
    if re.match(r"\s*WL\b", ti, re.I) or re.search(r"\bwind\b", ti, re.I):
        return "W"
    if re.search(r"temperature|\bT\s+uniform\b", ti, re.I):
        return "T"
    return None


def cls_of(lc):
    t = str(lc.type or "").upper().strip("'")
    if t == "(D)":
        return "EQU" if re.search(r"\bEQU\b", lc.title or "", re.I) else "STR"
    return {"(R)": "CHAR", "(F)": "FREQ", "(P)": "QP"}.get(t)


def allowed(cls, fam):
    if fam == "G":
        return G_SET[cls]
    p0, p1, p2 = PSI[fam]
    if cls in ("STR", "EQU"):
        return {0.0, 1.5} | {round(1.5 * p, 6) for p in p0}
    if cls == "CHAR":
        return {0.0, 1.0} | p0
    if cls == "FREQ":
        return {0.0} | p1 | p2
    return {0.0} | p2


def lead_factor(cls):
    return {"STR": 1.5, "EQU": 1.5, "CHAR": 1.0}.get(cls)


TITLE_G_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)G(?![A-Za-z0-9])")


def title_g(title):
    """The G factor a combination title states ('1.0G+W', '0.9G', '1.35G+1.5Q'), else None."""
    m_ = TITLE_G_RE.search(title or "")
    return float(m_.group(1)) if m_ else None


def factor_check(m, n, lc, over, intended=None):
    """-> (verdict, detail) of C4 for combination n."""
    cls = cls_of(lc)
    if cls is None:
        return None, f"TYPE {lc.type!r}: no EN 1990 class, factors not checked"
    bad, unknown, leads = [], [], set()
    if abs(lc.facd or 0.0) < 1e-12:
        bad.append("FACD 0: no self-weight in a design combination")
    elif not any(abs(abs(lc.facd) - g) <= FTOL for g in G_SET[cls]):
        bad.append(f"FACD {lc.facd:g} not in G {sorted(G_SET[cls])}")
    for src, fact, line, *_ in lc.copies:
        fam = family(m, src, over)
        if fam is None:
            unknown.append(src)
            continue
        ok = any(abs(fact - a) <= FTOL for a in allowed(cls, fam))
        if not ok:
            bad.append(f"COPY {src} ({fam}) FACT {fact:g} not in {sorted(allowed(cls, fam))} (line {line})")
        lf = lead_factor(cls)
        if fam != "G" and lf is not None and abs(fact - lf) <= FTOL:
            leads.add("Q" if fam in ("Q", "QH") else fam)
    if len(leads) > 1:
        bad.append(f"two leading variable actions at the full factor: {sorted(leads)}")
    # N-01: the INTENDED factor, not only an allowed one.
    # (a) a G factor written in the title ("107 ULS 1.0G+W", "131 EQU 0.9G+W") is the intended G factor
    tg = title_g(lc.title)
    if tg is not None:
        gf = [("FACD", abs(lc.facd or 0.0))] + [(f"COPY {src}", fact) for src, fact, *_ in lc.copies
                                                if family(m, src, over) == "G"]
        for what, v in gf:
            if abs(v - tg) > FTOL:
                bad.append(f"{what} G factor {v:g} but the title says {tg:g}G (favourable / inferior G intended)")
    # (b) exact factors per combination from expected.json combination_factors (generator table)
    checked_exact = False
    inlined = []
    if intended is not None:
        checked_exact = True
        got = {}
        for src, fact, *_ in lc.copies:
            got[str(src)] = got.get(str(src), 0.0) + fact
        want = {str(k): float(v) for k, v in intended.get("copies", {}).items()}
        if "facd" in intended and abs(abs(lc.facd or 0.0) - abs(float(intended["facd"]))) > FTOL:
            bad.append(f"FACD {lc.facd:g}, intended {float(intended['facd']):g} (expected.json combination_factors)")
        for k in sorted(set(got) | set(want), key=lambda x: int(x) if x.isdigit() else 10 ** 9):
            g_, w_ = got.get(k), want.get(k)
            if g_ is None:
                src_lc = m.lcs.get(int(k)) if k.isdigit() else None
                if lc.loads and own_force_free(lc) and src_lc is not None and src_lc.loads and \
                        own_force_free(src_lc):
                    inlined.append(f"LC {k} (intended FACT {w_:g}) is written as the combination's own force-free "
                                   "records: factor inside the load expression, not separable, not compared")
                else:
                    bad.append(f"COPY {k} missing, intended FACT {w_:g}")
            elif w_ is None:
                bad.append(f"COPY {k} FACT {g_:g} not in the intended combination")
            elif abs(g_ - w_) > FTOL:
                bad.append(f"COPY {k} FACT {g_:g}, intended {w_:g}")
    if bad:
        return "FAIL", {"class": cls, "errors": bad[:10], "intended_compared": checked_exact}
    if unknown and not checked_exact:
        return "ESCALATE", {"class": cls, "unknown_action_of_lcs": unknown[:20]}
    return "PASS", {"class": cls, "intended_compared": checked_exact, **({"not_compared": inlined} if inlined else {}),
                    "meaning": ("COPY factors and FACD equal the intended (generator) factors" + ("; own force-free records not compared"
                     if inlined else "")) if checked_exact else
                    "factors are allowed EN 1990 + UK NA values (no intended factors given: not proven per combination)"}


def check(model, table, rep, exp, over):
    nonlin = model.nonlinear_lcs()
    refs = [n for n, lc in model.lcs.items() if lc.facd and not lc.loads and not lc.copies]
    ref = next((n for n in sorted(refs) if n in table), None)
    E = (exp or {}).get("load_cases", {}) if exp else {}
    combos = model.combos()
    worst = (0.0, None)
    n_ok = 0
    selfeq = {}
    fact_bad = []
    for n in sorted(combos):
        lc = combos[n]
        cid = f"C1_{n}"
        cfac = ((exp or {}).get("combination_factors") or {}).get(str(n)) if exp else None
        fv, fd = factor_check(model, n, lc, over, cfac)
        if fv is not None:
            rep.check(f"C4_{n}", fv, lc=n, title=lc.title, **fd)
            if fv != "PASS":
                fact_bad.append(n)
        if n in nonlin:
            rep.check(cid, "ESCALATE", lc=n, skipped=f"solved by ASE {nonlin[n][0]} (line {nonlin[n][1]}): "
                      "non-linear results are not superposable; A5 check instead")
            continue
        own = [0.0, 0.0, 0.0]
        own_note = None
        if lc.loads:
            if own_force_free(lc):
                own_note = "own records force-free (temperature/moments): R_own = 0"
                selfeq.setdefault(n, []).append("own force-free records (temperature): factor inside the load "
                                                "expression, not checked")
            elif str(n) in E and all(str(s) in E for s, *_ in lc.copies if s is not None):
                Fn = [float(x) for x in E[str(n)]["F_kN"]]
                for s, f, *_ in lc.copies:
                    Fs = [float(x) for x in E[str(s)]["F_kN"]]
                    Fn = [Fn[j] - f * Fs[j] for j in range(3)]
                own = [-x for x in Fn]
                own_note = "R_own = -(F_c - sum f F_b) from expected.json"
            else:
                rep.check(cid, "ESCALATE", lc=n, title=lc.title,
                          error="mixed combination (own loads + COPY): not superposition-checked (own load totals "
                                "unknown: give --expected with this LC and its parts)")
                continue
        if any(s is None for s, *_ in lc.copies):
            rep.check(cid, "FAIL", lc=n, error="a COPY in this combination is not statically resolvable")
            continue
        if n not in table:
            rep.check(cid, "FAIL", lc=n, error="combination not in load_cases.json (not computed or not read)")
            continue
        row = table[n]
        try:
            if row.get("kind") not in (0, 1):
                raise MissingField(f"kind {row.get('kind')} is not a calculated load case (0/1)")
            got = reactions(row, n)
            pred = list(own)
            gross = [abs(x) for x in own]
            parts = []
            for src, fact, line, _, _ in lc.copies:
                if src not in table:
                    raise MissingField(f"copied LC {src} (line {line}) not in load_cases.json")
                rs = reactions(table[src], src)
                s_lc = model.lcs.get(src)
                if s_lc is not None and s_lc.facd and abs(fact) > 1e-12:
                    raise MissingField(f"copied LC {src} carries FACD {s_lc.facd:g}: whether COPY repeats the "
                                       "self-weight is not established (lint S7)")
                for j in range(3):
                    pred[j] += fact * rs[j]
                    gross[j] += abs(fact * rs[j])
                parts.append([src, fact])
            facd = lc.facd or 0.0
            if abs(facd) > 1e-12:
                if ref is None:
                    raise MissingField(f"FACD {facd:g} needs a pure self-weight load case (FACD, no loads) in "
                                       "load_cases.json; none found")
                rr = reactions(table[ref], ref)
                fref = model.lcs[ref].facd
                for j in range(3):
                    pred[j] += facd / fref * rr[j]
                    gross[j] += abs(facd / fref * rr[j])
                parts.append([f"FACD x LC {ref}", facd / fref])
            dlf = row.get("dead_load_factors")
            if dlf is None:
                raise MissingField("dead_load_factors missing")
            dl = sum(num(x, "dead_load_factors") ** 2 for x in dlf) ** 0.5
        except MissingField as e:
            rep.check(cid, "FAIL", lc=n, error=str(e))
            continue
        tol = [REL * g + ABS_KN for g in gross]
        diff = [got[j] - pred[j] for j in range(3)]
        ok = all(abs(diff[j]) <= tol[j] for j in range(3))
        c3 = abs(dl - abs(facd)) <= FACD_TOL * max(1.0, abs(facd))
        rel = max(abs(diff[j]) / max(gross[j], 1e-9) for j in range(3))
        if rel > worst[0]:
            worst = (rel, n)
        v = "PASS" if ok and c3 else "FAIL"
        n_ok += v == "PASS"
        c = rep.check(cid, v, lc=n, title=lc.title, expected_kN=[round(x, 4) for x in pred],
                      got_kN=got, tol_kN=[round(x, 4) for x in tol], diff_kN=[round(x, 4) for x in diff],
                      facd_dat=facd, facd_cdb=round(dl, 6), c3=("PASS" if c3 else "FAIL"),
                      parts=parts if v != "PASS" else len(parts))
        if own_note:
            c["mixed"] = own_note
        # C5: parts that reaction sums cannot see
        if E:
            atoms, _ = model.atoms(n)
            for at in atoms:
                e = E.get(str(at))
                if e and float(e.get("gross_kN") or 0) > 0:
                    fn = sum(float(x) ** 2 for x in e["F_kN"]) ** 0.5
                    if fn < VACUOUS * float(e["gross_kN"]):
                        selfeq.setdefault(n, []).append(f"LC {at} ({e.get('title', '')})")
    if E:
        if selfeq:
            rep.check("C5_self_equilibrating", "ESCALATE", combinations=len(selfeq),
                      parts={str(k): v for k, v in list(selfeq.items())[:60]},
                      meaning="not proven by reactions: a doubled or missing self-equilibrating part does not "
                              "change the reaction sum; no member-force proof in v1")
        else:
            rep.check("C5_self_equilibrating", "PASS", combinations=0)
    else:
        rep.check("C5_self_equilibrating", "ESCALATE",
                  error="no --expected: self-equilibrating parts cannot be identified, so they are not proven")
    rep.extra["summary"] = {"combinations": len(combos), "passed": n_ok, "worst_rel": round(worst[0], 6),
                            "worst_lc": worst[1], "self_weight_ref_lc": ref, "factor_findings": fact_bad[:40],
                            "self_equilibrating_combinations": sorted(selfeq)}
    if not combos:
        rep.check("C1", "CANNOT_RUN", error="no COPY-built combination found in the .dat")


def main():
    ap = Parser(TOOL, description="G5 combinations: superposition, EN 1990 factors, blind spots",
                formatter_class=__import__("argparse").RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("dat")
    ap.add_argument("load_cases")
    ap.add_argument("--expected")
    ap.add_argument("--families", help='JSON object {"<lc>": "G|Q|QH|W|S|T"} for LCs whose action is not in '
                                       'their TYPE or title')
    ap.add_argument("--workdir")
    a = ap.parse_args()
    ins = {"dat": input_record(a.dat, "dat"), "load_cases": input_record(a.load_cases, "load_cases")}
    if a.expected:
        ins["expected"] = input_record(a.expected, "expected")
    rep = Report(TOOL, a.workdir, ins)
    obj = load_json(a.load_cases)
    st = stale_of(obj)
    table = lc_table(obj, a.load_cases)
    model = C.Model(C.Dat.from_file(a.dat))
    exp = unwrap(load_json(a.expected)) if a.expected else None
    try:
        over = json.loads(a.families) if a.families else {}
    except json.JSONDecodeError as e:
        raise MissingField(f"--families is not JSON: {e}")
    if st:
        rep.check("R4_fresh", "FAIL", error="stale_results_warning in load_cases.json: " + " | ".join(st))
    check(model, table, rep, exp, over)
    rep.emit()


if __name__ == "__main__":
    run_main(TOOL, main)
