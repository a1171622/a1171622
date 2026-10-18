#!/usr/bin/env python3
"""Expand a cloud master .dat (M) into one file (X) by replacing each #INCLUDE line with the cloud copy of
that file (replaces the inline "script E" of sofistik-cadinp-author / sofistik-run-and-fix).

usage: python3 -I expand_master.py <master.dat> <out_expanded.dat> <sources.tsv> [--workdir W]

<sources.tsv>  one line per included file: '<PC file name><TAB><cloud path>' (the skills write it).
Prints 'EXPANDED <n>' (n = lines written to X) and then the one JSON verdict line.  On an error it prints
'EXPAND_ERROR <reason>' instead of EXPANDED, writes nothing and exits 3 (CANNOT_RUN).

Behaviour (same as script E): one level only; the master is read as strict UTF-8, sources with bad bytes
replaced; CR removed; X ends with exactly one newline.  An #INCLUDE line is matched with the server's
spelling (#INCLUDE, also abbreviated #INCL..., sofistik_mcp/solver.py:74); the name is looked up in
sources.tsv as written, then by base name, then with '.dat', then ignoring case.  Not found -> EXPAND_ERROR.
An #INCLUDE of a #DEFINE block name is kept as written.
Checks:  E1_expanded PASS; E2_no_nested_include ESCALATE when a source itself has an #INCLUDE line (it is NOT
expanded, X still written: the skill's 'incl' gotcha check routes it to STOP S-BRIEF); E3_no_apply ESCALATE
when M or a source has a +APPLY line (the server includes that file too, X does not).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cadinp as C  # noqa: E402
from _common import Parser, Report, input_record  # noqa: E402

TOOL = "expand_master"


def main():
    ap = Parser(TOOL, description="expand #INCLUDE lines of a master .dat from sources.tsv",
                formatter_class=__import__("argparse").RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("master")
    ap.add_argument("out")
    ap.add_argument("sources")
    ap.add_argument("--workdir")
    a = ap.parse_args()
    rep = Report(TOOL, a.workdir, {"master": input_record(a.master, "master"),
                                   "sources": input_record(a.sources, "sources")})
    try:
        mp = C.read_sources_tsv(a.sources)
        # one level, sources.tsv only (no folder search: X must be built from the approved cloud copies)
        ex = C.expand_includes(a.master, sources=mp, recurse=False, strict_master=True)
        folder_hits = [(n, p) for n, p in ex["includes"] if C._lookup(mp, n) is None]
        if ex["missing"] or folder_hits:
            miss = [f"{os.path.basename(f)}:{ln} {n}" for f, ln, n in ex["missing"]] + \
                   [f"{n} (found only next to the master, not in sources.tsv)" for n, _ in folder_hits]
            raise ValueError("include not in sources.tsv: " + "; ".join(miss))
    except (OSError, ValueError, UnicodeDecodeError) as e:
        print("EXPAND_ERROR", str(e).replace("\n", " "))
        rep.check("E1_expanded", "CANNOT_RUN", error=str(e))
        rep.note("Nothing was written. Fix sources.tsv or the master and run again.")
        rep.emit()
        return
    out = ex["lines"]
    text = "\n".join(out).rstrip("\n") + "\n"
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(text)
    n = len(out)
    print("EXPANDED", n)
    rep.check("E1_expanded", "PASS", lines=n, includes=[n_ for n_, _ in ex["includes"]])
    if ex["nested"]:
        rep.check("E2_no_nested_include", "ESCALATE",
                  found=[f"{os.path.basename(f)}:{ln} {nm}" for f, ln, nm in ex["nested"]][:20],
                  meaning="a source has its own #INCLUDE: not expanded here (STOP S-BRIEF in the skill)")
    else:
        rep.check("E2_no_nested_include", "PASS")
    if ex["apply"]:
        rep.check("E3_no_apply", "ESCALATE", found=[f"{os.path.basename(f)}:{ln} {t}" for f, ln, t in ex["apply"]][:20],
                  meaning="+APPLY pulls in a file on the PC that X does not contain")
    else:
        rep.check("E3_no_apply", "PASS")
    rep.inputs["expanded"] = input_record(a.out, "expanded")      # links M and X for the scorecard
    rep.extra.update(expanded_lines=n, out=a.out, out_sha256=rep.inputs["expanded"].get("sha256"))
    rep.emit()


if __name__ == "__main__":
    from _common import run_main
    run_main(TOOL, main)
