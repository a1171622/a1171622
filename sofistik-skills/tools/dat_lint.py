#!/usr/bin/env python3
"""G1 static lint of a SOFiSTiK .dat (no SOFiSTiK needed).

usage: python3 -I dat_lint.py <file.dat> [--workdir W] [--uls "101-130,135-139"] [--upstream other.dat ...]
                              [--sources W/sources.tsv] [--no-include]

#INCLUDE (native expansion, the server's rule sofistik_mcp/solver.py:56,74,289-297): every #INCLUDE / #INCL line
is replaced by the file it names, looked up first in --sources (sources.tsv '<PC name><TAB><cloud path>'), then
as <name> / <name>.dat next to the including file and next to the main file, three levels deep.  Findings
then carry "src": "<file>:<line>" (the line in the included file) next to "line" (the line of the expanded
text).  --no-include lints the file exactly as written (the old behaviour).  An expanded X file (expand_master.py)
has no #INCLUDE lines left, so linting X and linting M --sources give the same findings.

Rules (03_proof_checks.md section 3; evidence there):
  S1  hard-coded load value in a SOFiLOAD load record (only #names, 0, 1, -1 allowed)
  S2  load case used (COPY, ASE/BDK/AQB/MAXIMA LC lists, SYST PLC) but never defined
  S3  line longer than 255 characters (CADINP limit)
  S4  STO#/LET#/DEL# name containing an operator word (DIV SIN COS SQR TAN EXP LOG ABS MOD ATN POW)
  S5  comma list with more than 25 items
  S6  SV/SVAL IY/IZ/IT/IYZ without an explicit unit (default m4)
  S7  load atom counted twice in a combination (COPY tree expanded), COPY of a self-weight (FACD) LC,
      COPY cycle or COPY of an undefined LC inside the tree
  S8  COPY NO / FACT not a plain #name or number (expressions are not evaluated there)
  S9  TYPE 'IMP' load case in a linear ASE list; QUAD temperature written TYPE DT (must be DTXY)
  S10 load-case number written by two producers (SOFiLOAD, ASE EIGE, MAXIMA BASE+1..99, BDK/AQB LCST)
  S11 BDK CTRL group without its own LC list, or a BDK/AQB LC list that is not the intended ULS set
  S12 +SYS / *SYS / SYS records and $(...)-built record names (the server refuses them too)
  S14 variable used but never defined, or a CADINP structure/evaluation error (IF/LOOP nesting)
  S15 an #INCLUDE that cannot be found (the server refuses such a run: solver.py:18-19) or is nested deeper
      than 3 levels
S13 (load totals vs the generator) is not a lint rule: see make_expected_26016.py + equilibrium_check.py.
Every finding is FAIL (fix and re-run the lint); there is no tolerance to widen.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cadinp as C  # noqa: E402
from _common import Parser, Report, input_record, parse_ids, run_main  # noqa: E402

TOOL = "dat_lint"
RULES = {
    "S1": "parametric loads (no hard-coded load values)",
    "S2": "every load case used is defined",
    "S3": "line length <= 255",
    "S4": "variable names without operator words",
    "S5": "comma lists <= 25 items",
    "S6": "explicit units on SV/SVAL IY IZ IT IYZ",
    "S7": "no load atom twice in a combination, no COPY of a FACD (self-weight) LC",
    "S8": "COPY NO/FACT take a plain #name or a number",
    "S9": "no IMP load case in linear ASE, QUAD temperature is DTXY",
    "S10": "no load-case number written by two producers",
    "S11": "BDK/AQB LC lists restated per CTRL and equal to the ULS set",
    "S12": "no SYS commands or $(...) record names",
    "S14": "all variables defined, CADINP structure readable",
    "S15": "every #INCLUDE found (sources.tsv or next to the file), at most 3 levels deep",
}
VALUE_KEYS = {"P", "P1", "P2", "P3", "P4", "PA", "PE", "PM", "P5", "P6"}
MAX_SHOWN = 60


def lint(dat: C.Dat, model: C.Model, uls=None, upstream=()):
    F = {r: [] for r in RULES}
    notes = []

    def add(rule, line, msg):
        F[rule].append({"line": line, "msg": msg})

    # S3, S12 (physical lines, every block, enabled or not)
    for no, raw in enumerate(dat.lines, 1):
        if len(raw) > 255:
            add("S3", no, f"line has {len(raw)} characters")
        code = C.strip_comment(raw)
        for rec in C.split_records(code):
            r = rec.strip()
            if re.match(r"^[+*]?SYS\b", r, re.I):
                add("S12", no, f"SYS command: {r[:60]}")
            first = r.split()[0] if r.split() else ""
            if "$(" in first:
                add("S12", no, f"record name built with $(...): {first}")
            if re.match(r"^#DEFINE\b.*=\s*SYS", r, re.I):
                add("S12", no, "#define value starting with SYS")
    # S4
    for line, name, _raw in dat.stos + dat.lets:
        if any(o in name.upper() for o in C.OPERATOR_WORDS):
            add("S4", line, f"variable name {name} contains an operator word")
    for no, raw in enumerate(dat.lines, 1):
        code = C.strip_comment(raw)
        for m in re.finditer(r"\bDEL#(\w+)", code, re.I):
            if any(o in m.group(1).upper() for o in C.OPERATOR_WORDS):
                add("S4", no, f"variable name {m.group(1)} contains an operator word")
        # S5 comma lists
        for rec in C.split_records(code):
            for tok in C.tokenize(rec):
                if tok.count(",") >= 25 and not tok.startswith(("'", '"')):
                    add("S5", no, f"comma list with {tok.count(',') + 1} items")
        # S6
        if re.match(r"\s*(SV|SVAL)\b", code, re.I):
            for k in ("IY", "IZ", "IT", "IYZ"):
                mm = re.search(r"\b" + k + r"\s+([-\d.Ee+]+)(\[[^\]]+\])?", code)
                if mm and not mm.group(2):
                    add("S6", no, f"{k} {mm.group(1)} without an explicit unit (default m4)")
    # S1, S9 (load records of the final load-case definitions)
    suppressed = 0
    for n, lc in model.lcs.items():
        for line, text, toks, vals in lc.loads:
            up = [t.upper() for t in toks]
            if "TYPE" in up:
                i = up.index("TYPE")
                ltype = up[i + 1] if i + 1 < len(up) else ""
                cand = []
                if i + 2 < len(toks) and up[i + 2] not in VALUE_KEYS and up[i + 2] not in ("A", "L", "EZA", "EYA"):
                    cand.append(toks[i + 2])
                for j in range(i + 2, len(toks) - 1):
                    if up[j] in VALUE_KEYS:
                        cand.append(toks[j + 1])
                for t in cand:
                    if C.is_literal_number(t) and abs(float(re.sub(r"\[.*\]", "", t))) not in (0.0, 1.0):
                        add("S1", line, f"LC {n}: hard-coded load value {t} in '{text[:70]}'")
                if toks[0].upper() == "QUAD" and ltype == "DT":
                    add("S9", line, f"LC {n}: QUAD temperature TYPE DT (use DTXY)")
    for line in model.superseded_lines:
        suppressed += 1
    if suppressed:
        notes.append(f"{suppressed} load/COPY records belong to load-case definitions that a later SOFiLOAD block "
                     "replaces; S1 is not applied to them.")
    # S2
    defined = model.defined() | set(upstream)
    produced = set()
    for lo, hi, _p, _l in model.result_ranges():
        produced.update(range(lo, hi + 1))
    for lc, line, where in model.refs:
        if lc not in defined and lc not in produced:
            add("S2", line, f"LC {lc} used by {where} but not defined in a SOFiLOAD block of this file")
    # S7
    for n, lc in sorted(model.combos().items()):
        atoms, problems = model.atoms(n)
        for p in problems:
            add("S7", lc.line, f"LC {n}: {p}")
        for a, uses in sorted(atoms.items()):
            live = [(f, path) for f, path in uses if abs(f) > 1e-12]
            if len(live) > 1:
                add("S7", lc.line, f"LC {n}: load atom LC {a} counted {len(live)} times: "
                    + "; ".join(f"{' > '.join(map(str, p))} x{f:.4g}" for f, p in live))
        for src, fact, line, _, _ in lc.copies:
            s = model.lcs.get(src)
            if s is not None and s.facd and abs(fact or 0) > 1e-12:
                add("S7", line, f"LC {n}: COPY of LC {src}, which carries FACD {s.facd:g} (self-weight belongs in "
                    "FACD of the combination, not in a COPY)")
    # S8
    for n, lc in model.lcs.items():
        for src, fact, line, raw_no, raw_f in lc.copies:
            for item, raw in (("NO", raw_no), ("FACT", raw_f)):
                if raw is None:
                    continue
                if not (re.fullmatch(r"#\w+", raw) or C.is_literal_number(raw)):
                    add("S8", line, f"LC {n}: COPY {item} {raw} is not a plain #name or number")
    for line, msg in model.copy_notes:
        add("S8", line, msg)
    # S9 IMP in linear ASE
    for a in model.ase:
        if a["prob"] in ("LINE",):
            for n in a["lcs"]:
                lc = model.lcs.get(n)
                if lc is not None and isinstance(lc.type, str) and lc.type.upper() == "IMP":
                    add("S9", a["line"], f"LC {n} has TYPE 'IMP' but is in a linear ASE list")
    # S10
    ranges = model.result_ranges()
    for lo, hi, prod, line in ranges:
        clash = sorted(x for x in model.defined() if lo <= x <= hi)
        if clash:
            add("S10", line, f"{prod} writes LC {lo}-{hi}, which overlaps SOFiLOAD LC {clash[:8]}")
    for i, (lo, hi, prod, line) in enumerate(ranges):
        for lo2, hi2, prod2, line2 in ranges[i + 1:]:
            if lo <= hi2 and lo2 <= hi:
                add("S10", line2, f"{prod2} ({lo2}-{hi2}) overlaps {prod} ({lo}-{hi}, line {line})")
    # S11
    if uls is None:
        uls = sorted(n for n, lc in model.lcs.items()
                     if isinstance(lc.type, str) and lc.type.upper() == "(D)" and "EQU" not in lc.title.upper())
        notes.append("S11 intended ULS set derived from the .dat: load cases of TYPE '(D)' without 'EQU' in the "
                     f"title ({len(uls)} cases). Pass --uls to state it explicitly.")
    U = set(uls)
    for b in model.bdk:
        for g in b["groups"]:
            if not g["membs"]:
                continue
            if not g["lcs"]:
                add("S11", g["ctrl_line"] or b["line"], "BDK CTRL group without its own LC list before MEMB")
                continue
            s = set(g["lcs"])
            if U and s != U:
                add("S11", g["ctrl_line"] or b["line"], f"BDK LC list differs from the ULS set: missing "
                    f"{sorted(U - s)[:10]}, extra {sorted(s - U)[:10]}")
    for q in model.aqb:
        s = set(q["lcs"])
        if U and s and s != U:
            add("S11", q["line"], f"AQB LC list differs from the ULS set: missing {sorted(U - s)[:10]}, "
                f"extra {sorted(s - U)[:10]}")
    # S14
    for line, msg in dat.undefined:
        add("S14", line, f"undefined variable: {msg}")
    for line, msg in dat.errors:
        add("S14", line, msg)
    return F, notes


def main():
    ap = Parser(TOOL, description=__doc__.split("\n")[1], formatter_class=__import__("argparse").RawDescriptionHelpFormatter,
                epilog=__doc__)
    ap.add_argument("dat")
    ap.add_argument("--workdir")
    ap.add_argument("--uls", help="intended ULS member-check set, e.g. 101-130,135-139,141-148,151-154")
    ap.add_argument("--upstream", nargs="*", default=[], help=".dat files whose load cases this file uses")
    ap.add_argument("--sources", help="sources.tsv: '<PC name><TAB><cloud path>' per #INCLUDE file")
    ap.add_argument("--no-include", dest="no_include", action="store_true",
                    help="do not expand #INCLUDE (lint the file as written)")
    a = ap.parse_args()
    inputs = {"dat": input_record(a.dat, "dat")}
    if a.sources:
        inputs["sources"] = input_record(a.sources, "sources")
    rep = Report(TOOL, a.workdir, inputs)
    ex = None
    if a.no_include:
        dat = C.Dat.from_file(a.dat)
    else:
        mp = C.read_sources_tsv(a.sources) if a.sources else None
        ex = C.expand_includes(a.dat, sources=mp)
        dat = C.Dat("\n".join(ex["lines"]), a.dat)
        dat.read_info = ex["read_info"]
        for name, path in ex["includes"]:
            inputs[f"include:{name}"] = input_record(path, "include")
        if ex["includes"]:
            # the checksum of the expanded text, byte-identical to expand_master.py's X (scorecard links M and X)
            import hashlib
            xt = ("\n".join(ex["lines"]).rstrip("\n") + "\n").encode("utf-8")
            inputs["dat_expanded"] = {"path": None, "sha256": hashlib.sha256(xt).hexdigest(),
                                      "note": "expanded text of dat (as expand_master.py writes X)"}
    model = C.Model(dat)
    up = set()
    for u in a.upstream:
        up |= C.Model(C.Dat.from_file(u)).defined()
    F, notes = lint(dat, model, parse_ids(a.uls) if a.uls else None, up)
    if ex is None:
        for no, raw in enumerate(dat.lines, 1):
            if C.INCLUDE_LINE_RE.match(raw):
                F["S15"].append({"line": no, "msg": f"{raw.strip()[:80]}: not expanded (--no-include), so the "
                                 "included text was NOT linted; drop --no-include"})
    if ex is not None:
        for f, ln, nm in ex["missing"]:
            F["S15"].append({"line": None, "src": f"{os.path.basename(f)}:{ln}",
                             "msg": f"#INCLUDE {nm}: not found (pass --sources W/sources.tsv, or put the file next "
                                    "to the master)"})
        for f, ln, nm in ex["too_deep"]:
            F["S15"].append({"line": None, "src": f"{os.path.basename(f)}:{ln}",
                             "msg": f"#INCLUDE {nm}: nested deeper than {C.INCLUDE_DEPTH} levels"})
        if ex["includes"]:
            orig = ex["origin"]
            for v in F.values():
                for item in v:
                    ln = item.get("line")
                    if isinstance(ln, int) and 1 <= ln <= len(orig) and "src" not in item:
                        item["src"] = f"{os.path.basename(orig[ln - 1][0])}:{orig[ln - 1][1]}"
            notes.append(f"#INCLUDE expanded natively: {len(ex['includes'])} file(s) "
                         f"({', '.join(n for n, _ in ex['includes'][:10])}); 'line' = line of the expanded text, "
                         "'src' = file:line.")
        for f, ln, t in ex["apply"]:
            notes.append(f"{os.path.basename(f)}:{ln} '{t}': +APPLY is not expanded by this lint (the server "
                         "includes that file too).")
    for rid, name in RULES.items():
        f = F[rid]
        rep.check(rid, "FAIL" if f else "PASS", name=name, count=len(f), findings=f[:MAX_SHOWN],
                  **({"findings_truncated": True} if len(f) > MAX_SHOWN else {}))
    info = getattr(dat, "read_info", {}) or {}
    if info.get("nul_bytes_removed") or info.get("cr_removed"):
        rep.note(f"read: removed {info['nul_bytes_removed']} NUL bytes and {info['cr_removed']} CR characters "
                 "before linting (the file on disk is unchanged).")
    for n in notes:
        rep.note(n)
    rep.extra["summary"] = {"lines": len(dat.lines), "blocks": [f"{'+' if b.enabled else '-'}{b.prog}@{b.line}"
                                                             for b in dat.blocks if b.prog not in ("GAP", "PRE")],
                            "load_cases": len(model.lcs), "combinations": len(model.combos()),
                            "bdk_members": len(model.bdk_members()),
                            "includes": [n for n, _ in ex["includes"]] if ex else [],
                            "findings": sum(len(v) for v in F.values())}
    rep.note("S13 (load totals) is checked by equilibrium_check.py against expected.json, not here.")
    rep.emit()


if __name__ == "__main__":
    run_main(TOOL, main)
