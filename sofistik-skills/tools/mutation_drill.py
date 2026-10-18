#!/usr/bin/env python3
"""Mutation drill (03 M1-M3): inject known faults into COPIES of the inputs and prove every checker catches each.

usage: python3 -I mutation_drill.py <file.dat> --workdir W [--expected expected.json] [--seed 1] [--only NAMES]

Never touches the given file: it is read once (NUL/CR stripped) and every mutant is written to W/mutants/.
Each checker runs as a separate process (python3 -I <tool> ...), exactly as the skill runs it, on a clean
baseline and on every mutant.  A mutant is CAUGHT when its target check (id prefix) gets a worse verdict than
in the baseline (or appears with a non-PASS verdict).  Catch matrix in "matrix" (one row per mutant):
  dat_lint      S1 S2 S3 S4 S5 S7(double atom) S7(COPY of FACD LC) S8 S9 S10 S11 S12 S14 on mutated .dat copies
  combo_check   results built from a faulted copy of the COPY table (double atom, factor x0.8, dropped COPY,
                sign flip, FACD x1.1, combination missing, stale warning, mixed own+COPY combination x1.5 (FI-4))
                checked against the clean .dat, plus a .dat copy with a non-EN 1990 factor (FACT 1.2 -> C4) and
                one with the favourable G variable of an uplift / EQU combination set to 1.35 / 1.1 (FI-6 -> C4).
                Every combo_check call gets --expected (needed for the mixed combinations and C5).
                Synthetic reactions: R = -F from --expected where known, else seeded random vectors; the clean
                table is built from the same model, so the baseline must PASS.  A fault whose effect on the sums is
                below the tolerance is reported as BLIND (the documented blind spot), not as a miss.
  equilibrium_check (needs --expected)  one LC x1.05, one LC sign flipped, one LC missing, stale warning,
                a lateral component 2 % short (FI-3)
  canary_check  synthetic clean self-test result (hand values) and 7 faults (pz sign, uz +5 %, ury sign, extra
                support node, envelope LC, stale warning, truncated, LC 1/2 reaction-sum sign)
  coverage_census (needs BDK members in the .dat)  BDK member dropped, AQB-only SLN dropped, empty exclusion
                reason, unknown BDK id, AQB-only group without a reason (A-04)
  receipts      value not in the raw file, value at the wrong JSON path, raw file edited after the receipt
  scorecard     gate missing, one ESCALATE, ledger not agreed, two versions of the .dat, picks not hand-checked
                and members over 1.0 (FI-5)
  member_check  hand: AQB value off by 0.2, member over capacity, section area wrong, elements out of order;
                AQB-only member whose buckling is ignored (FI-1), top-flange load ignored (FI-2);
                pick: LC outside the member set
Bash timeout: run it with timeout 300000 (5 min) or more; a 26016 file takes about 2-4 min.
Verdict: PASS when every baseline is as expected and every applicable mutant that is not BLIND is caught; FAIL
when a mutant is missed; ESCALATE when a baseline is not clean (e.g. the .dat has lint findings).
"""
from __future__ import annotations

import copy
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _cadinp as C  # noqa: E402
import combo_check as CC  # noqa: E402
from _common import RANK, Parser, Report, input_record, load_json, run_main, unwrap  # noqa: E402

TOOL = "mutation_drill"
PY = sys.executable or "python3"


def run_tool(script, args, cwd=None):
    p = subprocess.run([PY, "-I", os.path.join(HERE, script)] + [str(a) for a in args], capture_output=True,
                       text=True, cwd=cwd, timeout=900)
    try:
        o = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else None
    except (json.JSONDecodeError, IndexError):
        o = None
    if o is None:
        o = {"verdict": "CANNOT_RUN", "checks": [{"id": "crash", "verdict": "CANNOT_RUN",
                                                  "error": (p.stderr or p.stdout)[-600:]}]}
    o["_exit"] = p.returncode
    return o


def verdicts(o):
    return {c["id"]: c["verdict"] for c in o.get("checks", [])}


def caught(base, mut, target):
    b, m = verdicts(base), verdicts(mut)
    for cid, v in m.items():
        if not cid.startswith(target):
            continue
        if RANK[v] > RANK.get(b.get(cid, "PASS"), 0):
            return True, f"{cid} {b.get(cid, '-')} -> {v}"
    return False, "target check unchanged"


def lint_count(o, rule):
    for c in o.get("checks", []):
        if c["id"] == rule:
            return int(c.get("count") or 0)
    return 0


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
    return path


class Drill:
    def __init__(self, dat, workdir, expected, seed, only):
        self.dat, self.W, self.seed, self.only = dat, workdir, seed, only
        self.M = os.path.join(workdir, "mutants")
        if os.path.isdir(self.M):
            shutil.rmtree(self.M)
        os.makedirs(self.M)
        self.text, self.info = C.read_text(dat)
        self.clean = os.path.join(self.M, "clean.dat")
        with open(self.clean, "w", encoding="utf-8") as f:
            f.write(self.text)
        self.model = C.Model(C.Dat(self.text, self.clean))
        self.expected = unwrap(load_json(expected)) if expected else None
        self.expected_path = expected
        self.cx = ["--expected", expected] if expected else []
        self.matrix, self.baselines = [], {}

    def want(self, checker):
        return not self.only or checker in self.only

    def row(self, checker, mutant, target, status, detail=""):
        self.matrix.append({"checker": checker, "mutant": mutant, "target": target, "result": status,
                            "detail": detail})

    def baseline(self, checker, o, ok, why=""):
        self.baselines[checker] = {"verdict": o.get("verdict"), "exit": o.get("_exit"), "as_expected": ok,
                                   "note": why}

    # ------------------------------------------------------------------ dat_lint
    def lint_mutants(self):
        lines = self.text.split("\n")
        m = self.model
        defined = set(m.lcs)
        out = {}

        def put(name, ls):
            out[name] = "\n".join(ls)

        def after_first_sto(extra):
            ls = list(lines)
            for i, ln in enumerate(ls):
                if re.match(r"\s*STO#", ln, re.I):
                    ls[i + 1:i + 1] = extra
                    return ls
            return None

        # S1 hard-coded load value in a live (not superseded) LC
        for n, lc in sorted(m.lcs.items()):
            hit = None
            for line, text, toks, vals in lc.loads:
                up = [t.upper() for t in toks]
                if "TYPE" in up and up.index("TYPE") + 2 < len(toks) and toks[up.index("TYPE") + 2].startswith("#"):
                    hit = (line, toks[up.index("TYPE") + 2])
                    break
            if hit:
                ls = list(lines)
                ls[hit[0] - 1] = ls[hit[0] - 1].replace(hit[1], "0.89", 1)
                put("S1", ls)
                break
        undefined = next(x for x in range(8999, 1, -1) if x not in defined)
        combos = {n: lc for n, lc in m.combos().items() if lc.copies and not lc.loads}
        cpline = None
        for n, lc in sorted(combos.items()):
            for src, fact, line, raw_no, raw_fact in lc.copies:
                if src is not None and re.search(r"\bCOPY\b", lines[line - 1], re.I) and \
                        not re.search(r"\bLOOP\b", lines[line - 1], re.I):
                    cpline = (n, src, line)
                    break
            if cpline:
                break
        if cpline:
            n, src, line = cpline
            ls = list(lines)
            ls[line - 1] = re.sub(r"(\bNO\s+)(\S+)", lambda mm: mm.group(1) + str(undefined), ls[line - 1], count=1, flags=re.I)
            put("S2", ls)
            ls = list(lines)
            ls.insert(line, lines[line - 1])
            put("S7_double_atom", ls)
            refs = [k for k, v in m.lcs.items() if v.facd and not v.loads and not v.copies]
            if refs:
                ls = list(lines)
                ls.insert(line, f"  COPY NO {refs[0]} FACT 1")
                put("S7_copy_of_facd", ls)
            ls = list(lines)
            new = re.sub(r"(\bFACT\s+)(\S+)", r"\g<1>1.0*1", ls[line - 1], count=1, flags=re.I)
            if new != ls[line - 1]:
                ls[line - 1] = new
                put("S8", ls)
        for name, extra in (("S3", ["$ " + "x" * 290]), ("S4", ["STO#NDIV 8"]),
                            ("S5", ["STO#LST " + ",".join(str(i) for i in range(1, 27))]),
                            ("S12", ["+SYS dir"]), ("S14", ["STO#ZZQ #UNDEFVAR+1"])):
            ls = after_first_sto(extra)
            if ls is not None:
                put(name, ls)
        put("S9", lines + ["+PROG SOFILOAD", f"LC {undefined} TYPE 'IMP' TITL 'drill'", "END",
                           "+PROG ASE", f"LC {undefined}", "END"])
        first = min(n for n, lc in m.lcs.items() if not lc.copies) if m.lcs else 2
        put("S10", lines + ["+PROG ASE", f"EIGE 3 ETYP BUCK LC {first}", "END"])
        # S11 BDK LC list missing one ULS case (first generation list or first plain LC record in a BDK block)
        bdk_lines = [b["line"] for b in m.bdk] if m.bdk else []
        if bdk_lines:
            for i in range(min(bdk_lines) - 1, len(lines)):
                mm = re.match(r"(\s*LC\s+\(\s*)(\d+)(\s+)(\d+)(.*)", lines[i], re.I)
                if mm and int(mm.group(4)) > int(mm.group(2)):
                    ls = list(lines)
                    ls[i] = f"{mm.group(1)}{mm.group(2)}{mm.group(3)}{int(mm.group(4)) - 1}{mm.group(5)}"
                    put("S11", ls)
                    break
                mm = re.match(r"(\s*LC\s+)(\d+(?:\s*,\s*\d+)+)(.*)", lines[i], re.I)
                if mm:
                    ls = list(lines)
                    ls[i] = mm.group(1) + ",".join(re.split(r"\s*,\s*", mm.group(2))[:-1]) + mm.group(3)
                    put("S11", ls)
                    break
        return out

    def drill_lint(self):
        base = run_tool("dat_lint.py", [self.clean])
        self.baseline("dat_lint", base, base["verdict"] == "PASS",
                      "" if base["verdict"] == "PASS" else "the .dat has lint findings: counts compared per rule")
        muts = self.lint_mutants()
        for name in ("S1", "S2", "S3", "S4", "S5", "S7_double_atom", "S7_copy_of_facd", "S8", "S9", "S10", "S11",
                     "S12", "S14"):
            rule = name.split("_")[0]
            if name not in muts:
                self.row("dat_lint", name, rule, "n/a", "no place for this fault in this .dat")
                continue
            p = os.path.join(self.M, f"lint_{name}.dat")
            with open(p, "w", encoding="utf-8") as f:
                f.write(muts[name])
            o = run_tool("dat_lint.py", [p])
            b, n = lint_count(base, rule), lint_count(o, rule)
            self.row("dat_lint", name, rule, "caught" if n > b else "MISSED", f"{rule} findings {b} -> {n}")

    # ------------------------------------------------------------------ combo_check
    def reactions(self, faults=None):
        """Synthetic stored sums for every LC: atoms R = -F (expected) or seeded random; combinations superposed
        from a (possibly faulted) COPY table."""
        m = self.model
        rnd = random.Random(self.seed)
        E = (self.expected or {}).get("load_cases", {}) if self.expected else {}
        refs = sorted(n for n, lc in m.lcs.items() if lc.facd and not lc.loads and not lc.copies)
        ref = refs[0] if refs else None
        R, own = {}, {}
        for n in sorted(m.lcs):
            e = E.get(str(n))
            if e and e.get("F_kN"):
                own[n] = [-float(x) for x in e["F_kN"]]
            else:
                own[n] = [rnd.uniform(-50, 50), rnd.uniform(-50, 50), rnd.uniform(100, 900)]
        for n, lc in m.lcs.items():           # mixed LCs: own part only (expected F of a mixed LC is its total)
            if lc.loads and lc.copies:
                if CC.own_force_free(lc):
                    own[n] = [0.0, 0.0, 0.0]
                elif str(n) in E and all(str(s) in E for s, *_ in lc.copies if s is not None):
                    F = [float(x) for x in E[str(n)]["F_kN"]]
                    for s, f, *_ in lc.copies:
                        F = [F[j] - f * float(E[str(s)]["F_kN"][j]) for j in range(3)]
                    own[n] = [-x for x in F]
        table = faults(copy.deepcopy({n: list(lc.copies) for n, lc in m.lcs.items()})) if faults else \
            {n: list(lc.copies) for n, lc in m.lcs.items()}
        facd = {n: (lc.facd or 0.0) for n, lc in m.lcs.items()}
        if faults and getattr(faults, "facd", None):
            facd.update(faults.facd)

        def val(n, depth=0):
            if n in R:
                return R[n]
            lc = m.lcs.get(n)
            if lc is None or depth > 40:
                return [0.0, 0.0, 0.0]
            cps = table.get(n) or []
            if not cps:
                if lc.facd and not lc.loads:
                    r = list(own[n]) if n == ref else [x * lc.facd / m.lcs[ref].facd for x in val(ref, depth + 1)] \
                        if ref is not None else list(own[n])
                else:
                    r = list(own[n])
            else:
                r = list(own[n]) if lc.loads else [0.0, 0.0, 0.0]
                for src, fact, *_ in cps:
                    if src is None:
                        continue
                    s = val(src, depth + 1)
                    r = [r[j] + fact * s[j] for j in range(3)]
                if abs(facd[n]) > 1e-12 and ref is not None and n != ref:
                    s = val(ref, depth + 1)
                    r = [r[j] + facd[n] / m.lcs[ref].facd * s[j] for j in range(3)]
            R[n] = r
            return r

        rows = []
        for n in sorted(m.lcs):
            r = val(n)
            f = facd[n]
            rows.append({"lc": n, "title": m.lcs[n].title, "kind": 1, "kind_name": "calculated", "action": "",
                         "factor": 1.0, "dead_load_factors": [0.0, 0.0, -abs(f) if f else 0.0],
                         "sum_reactions_kN": [round(x, 4) for x in r], "has_results": ["nodes", "beams"]})
        return {"rows": rows, "cdb": "drill.cdb"}

    def combo_targets(self):
        m = self.model
        nonlin = m.nonlinear_lcs()
        base = self.reactions()
        R = {r["lc"]: r["sum_reactions_kN"] for r in base["rows"]}
        cands = []
        for n, lc in m.combos().items():
            if lc.loads or n in nonlin or any(s is None for s, *_ in lc.copies):
                continue
            for i, (src, fact, *_rest) in enumerate(lc.copies):
                mag = max(abs(fact * x) for x in R.get(src, [0, 0, 0]))
                cands.append((mag, n, i, src, fact))
        cands.sort(reverse=True)
        return base, cands

    def drill_combo(self):
        base_t, cands = self.combo_targets()
        if not cands:
            self.row("combo_check", "all", "C1", "n/a", "no COPY combination in this .dat")
            return
        p0 = dump(os.path.join(self.M, "combo_clean.json"), base_t)
        base = run_tool("combo_check.py", [self.clean, p0] + self.cx)
        bad = [c["id"] for c in base["checks"] if c["verdict"] in ("FAIL", "CANNOT_RUN")]
        self.baseline("combo_check", base, not bad, "ESCALATE only from C5 (self-equilibrating parts, stated blind "
                      "spot)" if not bad else f"baseline findings: {bad[:5]}")
        mag, n, i, src, fact = cands[0]
        psi = next((c for c in cands if abs(abs(c[4]) - 1) > 1e-6 and abs(c[4]) > 1e-6), cands[0])
        facd_c = next((k for k, lc in sorted(self.model.combos().items()) if lc.facd and not lc.loads
                       and k not in self.model.nonlinear_lcs()), None)

        def fault(fn, facd=None):
            fn.facd = facd
            return fn

        muts = {
            "double_atom": ("C1_%d" % n, fault(lambda t: {**t, n: t[n] + [t[n][i]]})),
            "psi_x0.8": ("C1_%d" % psi[1], fault(lambda t: {**t, psi[1]: [
                (s, f * 0.8 if j == psi[2] else f, *r) for j, (s, f, *r) in enumerate(t[psi[1]])]})),
            "drop_copy": ("C1_%d" % n, fault(lambda t: {**t, n: [c for j, c in enumerate(t[n]) if j != i]})),
            "sign_flip": ("C1_%d" % n, fault(lambda t: {**t, n: [
                (s, -f if j == i else f, *r) for j, (s, f, *r) in enumerate(t[n])]})),
        }
        if facd_c is not None:
            muts["facd_x1.1"] = ("C1_%d" % facd_c, fault(lambda t: t, {facd_c: self.model.lcs[facd_c].facd * 1.1}))
        tiny = [c for c in cands if c[0] < 0.05]
        if tiny:
            t0 = tiny[0]
            muts["double_self_equilibrating"] = ("C1_%d" % t0[1], fault(lambda t: {**t, t0[1]: t[t0[1]] + [t[t0[1]][t0[2]]]}))
        for name, (target, fn) in muts.items():
            tbl = self.reactions(fn)
            p = dump(os.path.join(self.M, f"combo_{name}.json"), tbl)
            o = run_tool("combo_check.py", [self.clean, p] + self.cx)
            ok, why = caught(base, o, target)
            blind = False
            if not ok:
                lc = int(target.split("_")[1])
                a = next(r["sum_reactions_kN"] for r in base_t["rows"] if r["lc"] == lc)
                b = next(r["sum_reactions_kN"] for r in tbl["rows"] if r["lc"] == lc)
                blind = max(abs(a[j] - b[j]) for j in range(3)) <= 0.05 + 1e-3 * max(abs(x) for x in a)
            self.row("combo_check", name, target, "caught" if ok else ("BLIND" if blind else "MISSED"),
                     why if ok else ("effect on the reaction sums below tolerance (documented blind spot)"
                                     if blind else why))
        t = copy.deepcopy(base_t)
        t["rows"] = [r for r in t["rows"] if r["lc"] != n]
        o = run_tool("combo_check.py", [self.clean, dump(os.path.join(self.M, "combo_missing.json"), t)] + self.cx)
        ok, why = caught(base, o, f"C1_{n}")
        self.row("combo_check", "combination_missing", f"C1_{n}", "caught" if ok else "MISSED", why)
        t = copy.deepcopy(base_t)
        t["stale_results_warning"] = ["drill: results older than the .dat"]
        o = run_tool("combo_check.py", [self.clean, dump(os.path.join(self.M, "combo_stale.json"), t)] + self.cx)
        ok, why = caught(base, o, "R4")
        self.row("combo_check", "stale_warning", "R4", "caught" if ok else "MISSED", why)
        # FI-4 (review A-02): a mixed combination (own loads + COPY) x1.5
        nonlin = self.model.nonlinear_lcs()
        mixed = [k for k, lc in sorted(self.model.lcs.items()) if lc.loads and lc.copies and k not in nonlin]
        if mixed:
            k = mixed[-1]
            t = copy.deepcopy(base_t)
            for r in t["rows"]:
                if r["lc"] == k:
                    r["sum_reactions_kN"] = [x * 1.5 for x in r["sum_reactions_kN"]]
            o = run_tool("combo_check.py", [self.clean, dump(os.path.join(self.M, "combo_mixed.json"), t)] + self.cx)
            ok, why = caught(base, o, f"C1_{k}")
            self.row("combo_check", "mixed_combination_x1.5", f"C1_{k}", "caught" if ok else "MISSED", why)
        else:
            self.row("combo_check", "mixed_combination_x1.5", "C1", "n/a", "no mixed combination in this .dat")
        # A-05: a factor that is not an EN 1990 / UK NA factor (results consistent with the faulty .dat)
        lines = self.text.split("\n")
        hit = None
        for k, lc in sorted(self.model.combos().items()):
            if CC.cls_of(lc) != "STR" or lc.loads:
                continue
            for src, fact, line, *_ in lc.copies:
                fam = CC.family(self.model, src, {})
                if fam not in (None, "G") and re.search(r"\bCOPY\b.*\bFACT\b", lines[line - 1], re.I) and \
                        not re.search(r"\bLOOP\b", lines[line - 1], re.I):
                    hit = (k, line)
                    break
            if hit:
                break
        if hit:
            k, line = hit
            ls = list(lines)
            ls[line - 1] = re.sub(r"(\bFACT\s+)(\S+)", r"\g<1>1.2", ls[line - 1], count=1, flags=re.I)
            pd = os.path.join(self.M, "combo_factor.dat")
            with open(pd, "w", encoding="utf-8") as f:
                f.write("\n".join(ls))
            mut = C.Model(C.Dat("\n".join(ls), pd))
            keep = self.model
            self.model = mut
            try:
                tbl = self.reactions()
            finally:
                self.model = keep
            o = run_tool("combo_check.py", [pd, dump(os.path.join(self.M, "combo_factor.json"), tbl)] + self.cx)
            ok, why = caught(base, o, f"C4_{k}")
            self.row("combo_check", "factor_not_EN1990", f"C4_{k}", "caught" if ok else "MISSED", why)
        else:
            self.row("combo_check", "factor_not_EN1990", "C4", "n/a", "no STR combination with a plain COPY line")
        # N-01 / FI-6: the favourable (inferior) G variable of an uplift / EQU combination set to the unfavourable
        # value: still an allowed EN 1990 factor, but not the intended one
        hit = None
        for k, lc in sorted(self.model.combos().items()):
            tg = CC.title_g(lc.title)
            cls = CC.cls_of(lc)
            if tg is None or cls not in ("STR", "EQU") or tg not in (1.0, 0.9):
                continue
            ms = re.findall(r"^\s*LC\s+%d\b[^\n]*?\bFACD\s+#(\w+)" % k, self.text, re.I | re.M)
            if not ms:
                continue
            name = ms[-1]
            sto = list(re.finditer(r"^(\s*STO#%s\s+)(\S+)" % re.escape(name), self.text, re.I | re.M))
            if sto:
                hit = (k, name, sto[-1], 1.35 if cls == "STR" else 1.1)
                break
        if hit:
            k, name, mm, newv = hit
            t2 = self.text[:mm.start(2)] + str(newv) + self.text[mm.end(2):]
            pd = os.path.join(self.M, "combo_unfav_g.dat")
            with open(pd, "w", encoding="utf-8") as f:
                f.write(t2)
            keep = self.model
            self.model = C.Model(C.Dat(t2, pd))
            try:
                tbl = self.reactions()
            finally:
                self.model = keep
            o = run_tool("combo_check.py", [pd, dump(os.path.join(self.M, "combo_unfav_g.json"), tbl)] + self.cx)
            ok, why = caught(base, o, f"C4_{k}")
            self.row("combo_check", "FI6_unfavourable_G_intended_favourable", f"C4_{k}",
                     "caught" if ok else "MISSED", f"STO#{name} -> {newv}; " + why)
        else:
            self.row("combo_check", "FI6_unfavourable_G_intended_favourable", "C4", "n/a",
                     "no combination with a stated favourable G factor ('1.0G' / '0.9G') and a FACD #name")

    # ------------------------------------------------------------------ equilibrium_check
    def drill_equilibrium(self, expected_path):
        E = self.expected["load_cases"]
        rows = []
        for k, e in E.items():
            rows.append({"lc": int(k), "title": e.get("title", ""), "kind": 1, "factor": 1.0,
                         "dead_load_factors": [0, 0, 0], "sum_reactions_kN": [-float(x) for x in e["F_kN"]],
                         "has_results": ["nodes"]})
        clean = {"rows": rows, "cdb": "drill.cdb"}
        base = run_tool("equilibrium_check.py", [dump(os.path.join(self.M, "eq_clean.json"), clean), expected_path])
        bad = [c for c in base["checks"] if c["verdict"] in ("FAIL", "CANNOT_RUN")]
        self.baseline("equilibrium_check", base, not bad, "ESCALATE only from vacuous (self-equilibrating) LCs"
                      if base["verdict"] == "ESCALATE" else "")
        big = max(E, key=lambda k: max(abs(float(x)) for x in E[k]["F_kN"]))
        lc = int(big)

        def mut(name, fn, target):
            t = copy.deepcopy(clean)
            fn(t)
            o = run_tool("equilibrium_check.py", [dump(os.path.join(self.M, f"eq_{name}.json"), t), expected_path])
            ok, why = caught(base, o, target)
            self.row("equilibrium_check", name, target, "caught" if ok else "MISSED", why)

        def scale(t, f):
            for r in t["rows"]:
                if r["lc"] == lc:
                    r["sum_reactions_kN"] = [x * f for x in r["sum_reactions_kN"]]
        mut("lc_x1.05", lambda t: scale(t, 1.05), f"E1_{lc}")
        mut("sign_flip", lambda t: scale(t, -1.0), f"E1_{lc}")
        mut("lc_missing", lambda t: t.update(rows=[r for r in t["rows"] if r["lc"] != lc]), f"E1_{lc}")
        mut("stale_warning", lambda t: t.update(stale_results_warning=["drill"]), "R4")
        lat = [k for k, e in E.items() if abs(float(e["F_kN"][0])) > 50 and abs(float(e["F_kN"][2])) > 2 * abs(float(e["F_kN"][0]))]
        if lat:
            kl = int(lat[0])

            def short(t):
                for r in t["rows"]:
                    if r["lc"] == kl:
                        r["sum_reactions_kN"][0] *= 0.978      # FI-3: lateral 2.2 % short, vertical exact
            mut("FI3_lateral_2pct_short", short, f"E1_{kl}")

    # ------------------------------------------------------------------ canary_check
    @staticmethod
    def canary_clean():
        P, L, E, Iy = 1.0, 6.0, 2.1e8, 3692e-8
        ury = -P * L ** 2 / (2 * E * Iy) * 1e3

        def sup(lc, f):
            return {"lc": lc, "supports_with_reaction": 1, "sum_kN": {"px": 0.0, "py": 0.0, "pz": -f},
                    "sum_stored_by_sofistik_kN": [0.0, 0.0, -f], "truncated": False,
                    "rows": [{"node": 1, "px": 0.0, "py": 0.0, "pz": -f, "mx": 0.0, "my": 6.0 * f, "mz": 0.0}]}
        brows = []
        for b in range(1, 7):
            for x in (0.0, 0.5, 1.0):
                xg = (b - 1) + x
                brows.append({"beam": b, "sln": None, "group": 0, "x": x, "N": 0.0, "Vy": 0.0, "Vz": 1.0,
                              "Mt": 0.0, "My": round(-P * (L - xg), 4), "Mz": 0.0})
        return {
            "g0_node_lc1": {"lc": 1, "rows": [{"node": 7, "ux": 0.0, "uy": 0.0, "uz": 9.31, "urx": 0.0,
                                               "ury": round(ury, 4), "urz": 0.0}], "truncated": False},
            "g0_support_lc1": sup(1, 1.0), "g0_support_lc2": sup(2, 2.0),
            "g0_beam_lc1": {"lc": 1, "rows": brows, "truncated": False},
            "g0_env_1_2": {"load_cases_found": [1, 2], "load_cases_without_data": [], "load_cases_missing": [],
                           "overall": {"My": {"max": {"value": 0.0, "lc": 1, "beam": 6},
                                              "min": {"value": -12.0, "lc": 2, "beam": 1}}}},
            "g0_load_cases_1_2": {"rows": [
                {"lc": lc, "title": f"P = {f:g} kN", "kind": 1, "kind_name": "calculated", "action": "",
                 "factor": 1.0, "dead_load_factors": [0.0, 0.0, 0.0], "sum_reactions_kN": [0.0, 0.0, -f],
                 "has_results": ["nodes", "beams"]} for lc, f in ((1, 1.0), (2, 2.0))], "cdb": "selftest.cdb"},
        }

    def drill_canary(self):
        clean = self.canary_clean()
        base = run_tool("canary_check.py", [dump(os.path.join(self.M, "canary_clean.json"), clean)])
        self.baseline("canary_check", base, base["verdict"] == "PASS")

        def m(name, target, fn):
            t = copy.deepcopy(clean)
            fn(t)
            o = run_tool("canary_check.py", [dump(os.path.join(self.M, f"canary_{name}.json"), t)])
            ok, why = caught(base, o, target)
            self.row("canary_check", name, target, "caught" if ok else "MISSED", why)

        def flip_pz(t):
            for k in ("g0_support_lc1", "g0_support_lc2"):
                for r in t[k]["rows"]:
                    r["pz"] = -r["pz"]
        m("pz_sign", "K3_support", flip_pz)
        m("uz_plus5pct", "K2_tip_uz", lambda t: t["g0_node_lc1"]["rows"][0].update(uz=9.31 * 1.05))
        m("ury_sign", "K3_tip_ury", lambda t: t["g0_node_lc1"]["rows"][0].update(ury=-t["g0_node_lc1"]["rows"][0]["ury"]))
        m("extra_support", "K2_support_lc1_nodes", lambda t: t["g0_support_lc1"]["rows"].append(
            {"node": 7, "px": 0.0, "py": 0.0, "pz": 0.0, "mx": 0.0, "my": 0.0, "mz": 0.0}))
        m("envelope_lc", "K2_env_My", lambda t: t["g0_env_1_2"]["overall"]["My"]["min"].update(lc=1))
        m("stale_warning", "R4", lambda t: t["g0_beam_lc1"].update(stale_results_warning=["drill"]))
        m("truncated", "P_", lambda t: t["g0_beam_lc1"].update(truncated=True))
        m("lc_sum_sign", "K3_lc1_sum", lambda t: t["g0_load_cases_1_2"]["rows"][0].update(sum_reactions_kN=[0.0, 0.0, 1.0]))

    # ------------------------------------------------------------------ coverage_census
    def drill_coverage(self):
        m = self.model
        mem = m.bdk_members()
        if not mem or not m.slns:
            self.row("coverage_census", "all", "H1", "n/a", "no BDK members / structural lines in this .dat")
            return
        in_bdk = {s for x in mem for s in [x["sln"]] + x["cont"]}
        aq = sorted(s for s, v in m.slns.items() if v.get("sno") is not None and s not in in_bdk)
        clean = {"source": "drill", "bdk_checked": sorted(x["id"] for x in mem), "aqb_checked_slns": aq,
                 "excluded": {}, "aqb_only_reasons": {str(s_): "drill reason" for s_ in aq}}
        base = run_tool("coverage_census.py", [self.clean, dump(os.path.join(self.M, "cov_clean.json"), clean)])
        self.baseline("coverage_census", base, base["verdict"] == "PASS")

        def mt(name, target, fn):
            t = copy.deepcopy(clean)
            fn(t)
            o = run_tool("coverage_census.py", [self.clean, dump(os.path.join(self.M, f"cov_{name}.json"), t)])
            ok, why = caught(base, o, target)
            self.row("coverage_census", name, target, "caught" if ok else "MISSED", why)
        mt("bdk_member_dropped", "H1_bdk_omitted", lambda t: t["bdk_checked"].pop(0))
        if aq:
            mt("aqb_sln_dropped", "H1_unaccounted", lambda t: t["aqb_checked_slns"].pop(0))
            mt("empty_exclusion_reason", "H1_unaccounted",
               lambda t: (t["aqb_checked_slns"].remove(aq[0]), t["excluded"].update({str(aq[0]): ""})))
        mt("unknown_bdk_id", "H1_bdk_unknown", lambda t: t["bdk_checked"].append(987654))
        if aq:
            mt("aqb_only_without_reason", "H1_aqb_only_reason", lambda t: t["aqb_only_reasons"].pop(str(aq[0])))

    # ------------------------------------------------------------------ receipts
    def drill_receipts(self):
        d = os.path.join(self.M, "receipts")
        os.makedirs(d, exist_ok=True)
        raw = dump(os.path.join(d, "raw_lc.json"), {"rows": [{"lc": 2, "sum_reactions_kN": [0.0, 0.0, 886.6139]}]})
        args = ["--value", "886.6139", "--unit", "kN", "--tool", "cdb_load_cases", "--args", '{"load_cases": "2"}',
                "--cdb", "drill.cdb", "--cdb-mtime", "2026-10-18T00:00:00", "--path", "rows[0].sum_reactions_kN[2]"]
        base = run_tool("receipts.py", ["add", "--workdir", d, "--raw", raw] + args)
        aud = run_tool("receipts.py", ["audit", "--workdir", d, "--n", "1", "--seed", "1"])
        self.baseline("receipts", aud, base["verdict"] == "PASS" and aud["verdict"] == "PASS")
        a2 = list(args)
        a2[1] = "886.7"
        o = run_tool("receipts.py", ["add", "--workdir", d, "--raw", raw] + a2)
        ok, why = caught(base, o, "receipt_add")
        self.row("receipts", "value_not_in_raw", "receipt_add", "caught" if ok else "MISSED", why)
        a3 = list(args)
        a3[-1] = "rows[0].sum_reactions_kN[0]"          # A-18: right number, wrong meaning (path)
        o = run_tool("receipts.py", ["add", "--workdir", d, "--raw", raw] + a3)
        ok, why = caught(base, o, "receipt_add")
        self.row("receipts", "value_at_wrong_path", "receipt_add", "caught" if ok else "MISSED", why)
        dump(raw, {"rows": [{"lc": 2, "sum_reactions_kN": [0.0, 0.0, 880.0]}]})
        o = run_tool("receipts.py", ["audit", "--workdir", d, "--n", "1", "--seed", "1"])
        ok, why = caught(aud, o, "receipt_r")
        self.row("receipts", "raw_edited_after_receipt", "receipt_r", "caught" if ok else "MISSED", why)

    # ------------------------------------------------------------------ scorecard
    def drill_scorecard(self):
        gates = ("canary_check", "G2_protocol", "A7_run_identity", "equilibrium_check", "mutation_drill",
                 "combo_check", "R6_member_lcs", "G6_alpha_cr", "coverage_census", "G8_plausibility",
                 "A12_assumptions")
        dat = {"path": "x.dat", "sha256": "a" * 64}

        def make(name, lines, ledger="yes"):
            d = os.path.join(self.M, "score_" + name)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "proofs.jsonl"), "w", encoding="utf-8") as f:
                for o in lines:
                    f.write(json.dumps(o) + "\n")
            with open(os.path.join(d, "ledger.md"), "w", encoding="utf-8") as f:
                f.write(f"assumptions_agreed: {ledger}\n")
            return run_tool("scorecard.py", [d])

        clean = [{"tool": g, "verdict": "PASS", "checks": [], "inputs": {"dat": dat}} for g in gates]
        picks = [{"member": str(i), "lc": 101} for i in range(7)]
        clean += [{"tool": "member_check", "action": "pick", "verdict": "PASS", "checks": [], "picks": picks,
                   "stats": {"n_eta_gt_1": 0, "eta_max": 0.8}}]
        clean += [{"tool": "member_check", "action": "hand", "member": str(i), "lc": 101, "verdict": "PASS",
                   "checks": []} for i in range(7)]
        clean += [{"tool": "receipts", "action": "audit", "verdict": "PASS", "checks": []}]
        base = make("clean", clean)
        self.baseline("scorecard", base, base["verdict"] == "PASS")

        def mt(name, lines, ledger="yes"):
            o = make(name, lines, ledger)
            ok, why = caught(base, o, "score")
            self.row("scorecard", name, "score", "caught" if ok else "MISSED", why + f" ({o.get('score')})")
        mt("gate_missing", [x for x in clean if x["tool"] != "equilibrium_check"])
        mt("one_escalate", [dict(x, verdict="ESCALATE") if x["tool"] == "combo_check" else x for x in clean])
        mt("ledger_not_agreed", clean, "no")
        mt("FI5_picks_not_hand_checked", [x for x in clean if not (x["tool"] == "member_check" and
                                                                  x.get("action") == "hand" and x["member"] != "0")])
        mt("FI5_members_over_1", [dict(x, stats={"n_eta_gt_1": 3, "eta_max": 1.4}) if x.get("action") == "pick"
                                  else x for x in clean])
        mt("two_dat_versions", [dict(x, inputs={"dat": {"path": "x.dat", "sha256": "b" * 64}})
                                if x["tool"] == "combo_check" else x for x in clean])

    # ------------------------------------------------------------------ member_check
    def drill_member(self):
        d = os.path.join(self.M, "member")
        L, w = 6.0, 20.0
        rows = []
        for e in range(3):
            for k in range(5):
                xl = k * 0.5
                x = e * 2 + xl
                rows.append({"beam": 101 + e, "sln": 10, "group": 1, "x": xl, "N": -50.0, "Vy": 0.0,
                             "Vz": w * (L / 2 - x), "Mt": 0.0, "My": w * x * (L - x) / 2, "Mz": 0.0})
        forces = {"lc": 101, "rows": rows, "truncated": False}
        ov = {"sections": [{"nr": 2, "title": "UB 254x146x43", "A_cm2": 54.77, "Iy_cm4": 6544.0, "Iz_cm4": 677.0}]}
        mr = {"member_lcs": [101], "members": [{"member": "10", "slns": [10], "section": "UB 254x146x43",
                                                "section_nr": 2, "material": "S 275", "cy_fix_from_start_m": [3.0],
                                                "eta_bdk": 0.735, "lc_bdk": None, "eta_aqb": 0.578,
                                                "lc_aqb": 101}]}
        env = {"load_cases_found": [101], "overall": {"N": {"min": {"value": -50.0, "lc": 101, "sln": 10}}}}

        def hand(name, f, o_, m_):
            pf = dump(os.path.join(d, name, "forces.json"), f)
            po = dump(os.path.join(d, name, "overview.json"), o_)
            pm = dump(os.path.join(d, name, "mr.json"), m_)
            return run_tool("member_check.py", ["hand", pf, po, pm, "--member", "10", "--lc", "101", "--workdir",
                                                os.path.join(d, name)])
        base = hand("clean", forces, ov, mr)
        if any("sofrep not importable" in str(c.get("error", "")) for c in base["checks"]):
            self.row("member_check", "all", "G7", "n/a", "sofrep not importable here")
            return
        pb = run_tool("member_check.py", ["pick", dump(os.path.join(d, "pick", "mr.json"), mr),
                                          dump(os.path.join(d, "pick", "env.json"), env), "--seed", "drill",
                                          "--workdir", os.path.join(d, "pick")])
        self.baseline("member_check", base, base["verdict"] == "PASS" and pb["verdict"] == "PASS")

        def mh(name, target, f=forces, o_=ov, m_=mr):
            o = hand(name, f, o_, m_)
            ok, why = caught(base, o, target)
            self.row("member_check", name, target, "caught" if ok else "MISSED", why)
        m2 = copy.deepcopy(mr)
        m2["members"][0]["eta_aqb"] = 0.778
        mh("aqb_off_by_0.2", "G7_aqb", m_=m2)
        f3 = copy.deepcopy(forces)
        for r in f3["rows"]:
            for k in ("Vz", "My"):
                r[k] *= 2.2
        m3 = copy.deepcopy(mr)
        m3["members"][0].update(eta_aqb=1.27, eta_bdk=1.6)
        mh("over_capacity", "G7_", f=f3, m_=m3)
        o4 = copy.deepcopy(ov)
        o4["sections"][0]["A_cm2"] = 64.0
        mh("section_area_wrong", "G7_hand", o_=o4)
        f5 = copy.deepcopy(forces)
        for r in f5["rows"]:
            r["beam"] = {101: 103, 103: 101}.get(r["beam"], r["beam"])
        mh("elements_out_of_order", "G7_hand", f=f5)
        # review FI-1 / FI-2: an 8 m unrestrained UB 254 (reviewer A's data)
        L8, w8, r8 = 8.0, 9.4, []
        for e in range(4):
            for k in range(5):
                xl = k * 0.5
                x = e * 2 + xl
                r8.append({"beam": 201 + e, "sln": 10, "group": 1, "x": xl, "N": -30.0, "Vy": 0.0,
                           "Vz": w8 * (L8 / 2 - x), "Mt": 0.0, "My": w8 * x * (L8 - x) / 2, "Mz": 0.0})
        f8 = {"lc": 101, "rows": r8, "truncated": False}
        m7 = copy.deepcopy(mr)
        m7["members"][0].update(cy_fix_from_start_m=[], eta_bdk=None, eta_aqb=0.5)
        mh("FI1_aqb_only_buckling_ignored", "G7_bdk_hand_only", f=f8, m_=m7)
        m8 = copy.deepcopy(mr)
        m8["members"][0].update(cy_fix_from_start_m=[], eta_bdk=0.86, eta_aqb=0.36)
        mh("FI2_top_flange_load_ignored", "G7_bdk", f=f8, m_=m8)
        e6 = copy.deepcopy(env)
        e6["overall"]["N"]["min"]["lc"] = 999
        o = run_tool("member_check.py", ["pick", os.path.join(d, "pick", "mr.json"),
                                         dump(os.path.join(d, "pick6", "env.json"), e6), "--seed", "drill",
                                         "--workdir", os.path.join(d, "pick6")])
        ok, why = caught(pb, o, "G7_lc_set")
        self.row("member_check", "pick_lc_outside_set", "G7_lc_set", "caught" if ok else "MISSED", why)


def main():
    import argparse
    ap = Parser(TOOL, description="mutation drill: every checker catches every injected fault",
                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("dat")
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--expected")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--only", help="comma list of checkers (tests)")
    a = ap.parse_args()
    rep = Report(TOOL, a.workdir, {"dat": input_record(a.dat, "dat")})
    only = set(a.only.split(",")) if a.only else None
    D = Drill(a.dat, a.workdir, a.expected, a.seed, only)
    steps = [("dat_lint", D.drill_lint), ("combo_check", D.drill_combo), ("canary_check", D.drill_canary),
             ("coverage_census", D.drill_coverage), ("receipts", D.drill_receipts),
             ("scorecard", D.drill_scorecard), ("member_check", D.drill_member)]
    if a.expected:
        steps.insert(2, ("equilibrium_check", lambda: D.drill_equilibrium(a.expected)))
    else:
        D.row("equilibrium_check", "all", "E1", "n/a", "no --expected given")
    for name, fn in steps:
        if D.want(name):
            fn()
    missed = [r for r in D.matrix if r["result"] == "MISSED"]
    blind = [r for r in D.matrix if r["result"] == "BLIND"]
    applied = [r for r in D.matrix if r["result"] in ("caught", "MISSED")]
    for checker, b in D.baselines.items():
        rep.check(f"M_baseline_{checker}", "PASS" if b["as_expected"] else "ESCALATE", tool_verdict=b["verdict"],
                  note=b["note"])
    rep.check("M_catch", "FAIL" if missed else ("PASS" if applied else "CANNOT_RUN"),
              caught=len(applied) - len(missed), applied=len(applied), missed=[f"{r['checker']}:{r['mutant']}"
                                                                              for r in missed],
              blind=[f"{r['checker']}:{r['mutant']}" for r in blind])
    by = {}
    for r in D.matrix:
        by.setdefault(r["checker"], {})[r["mutant"]] = r["result"]
    rep.extra["matrix"] = D.matrix
    rep.extra["matrix_summary"] = by
    rep.extra["read_info"] = D.info
    if blind:
        rep.note("BLIND = the fault does not change the reaction sums beyond tolerance (self-equilibrating load): "
                 "the documented blind spot of G4/G5; the member-force proof (E3/C4) covers it.")
    rep.note(f"Mutants and their results are in {D.M}; the given .dat was not modified.")
    rep.emit()


if __name__ == "__main__":
    run_main(TOOL, main)
