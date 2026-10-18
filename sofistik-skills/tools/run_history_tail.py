#!/usr/bin/env python3
"""Run time and peak RAM of earlier runs of a .dat from the tail of the server's run_history.json
(replaces the inline "script H" of sofistik-run-and-fix).

usage: python3 -I run_history_tail.py <tail.txt> "<file name of dat>" [--workdir W]

<tail.txt>  the 'text' of read_text_file(<status folder>\\run_history.json, start_line=s, max_lines=200), saved
            exactly (lines 'N: ...'; the prefix is removed).  The tail may start in the middle of a run entry.
<file name of dat>  the PC file name (a full PC path is reduced to its base name); case is ignored.
Run entries are the server's (sofistik_mcp/dashboard.py:293-295 RunHistory.add): "dat", "finished", "status",
"seconds", "peak_ram_mb", newest last.  A clean run is status 'ok' or 'ok with warnings' (dashboard.py:311
GOOD_RUNS) with seconds not null.
Prints one line, the same as script H, then the one JSON verdict line:
  HIST same file minutes=<m|none> peak_gb=<g|none>        runs of exactly this file name
  HIST earlier version minutes=<m|none> peak_gb=<g|none>  else runs of the same name without its _vN suffix
  HIST none                                               no run of either kind
minutes = the newest clean run's seconds/60 (1 decimal); peak_gb = max peak_ram_mb of the last 3 runs of that
kind / 1024, rounded up to 0.1 (+0.05 then 1 decimal, as script H).  Verdict PASS (also for HIST none: it is a
lookup; the skill NOTEs 'no run history'); CANNOT_RUN ('HIST error ...') when the tail cannot be read.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import Parser, Report, input_record, run_main  # noqa: E402

TOOL = "run_history_tail"
PAT = re.compile(r'"dat":\s*"((?:[^"\\]|\\.)*)"[^{}\[\]]*?"status":\s*"([^"]*)"[^{}\[\]]*?"seconds":\s*([0-9.]+|null)'
                 r'[^{}\[\]]*?"peak_ram_mb":\s*([0-9.]+|null)')
GOOD = ("ok", "ok with warnings")


def base(s):
    return re.sub(r"_v\d+(\.dat)$", r"\1", s)


def history(text, want):
    t = "\n".join(re.sub(r"^\d+: ?", "", l) for l in text.replace("\r", "").split("\n"))
    want = want.replace("/", "\\").rsplit("\\", 1)[-1].lower()
    runs = [(g.group(1).replace("\\\\", "\\").replace("/", "\\").lower().rsplit("\\", 1)[-1], g)
            for g in PAT.finditer(t)]
    for label, same in (("same file", lambda n: n == want), ("earlier version", lambda n: base(n) == base(want))):
        rs = [g for n, g in runs if same(n)]
        good = [g for g in rs if g.group(2) in GOOD and g.group(3) != "null"]
        peaks = [float(g.group(4)) for g in rs[-3:] if g.group(4) != "null"]
        if good or peaks:
            minutes = round(float(good[-1].group(3)) / 60, 1) if good else None
            peak_gb = round(max(peaks) / 1024 + 0.05, 1) if peaks else None
            return {"label": label, "minutes": minutes, "peak_gb": peak_gb, "runs_matched": len(rs),
                    "runs_in_tail": len(runs)}
    return {"label": None, "minutes": None, "peak_gb": None, "runs_matched": 0, "runs_in_tail": len(runs)}


def main():
    ap = Parser(TOOL, description="earlier run time / peak RAM of a .dat from run_history.json",
                formatter_class=__import__("argparse").RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("tail")
    ap.add_argument("dat_name")
    ap.add_argument("--workdir")
    a = ap.parse_args()
    rep = Report(TOOL, a.workdir, {"tail": input_record(a.tail, "tail")})
    try:
        text = open(a.tail, encoding="utf-8", errors="replace").read()
    except OSError as e:
        print("HIST error", e)
        rep.check("H1_history", "CANNOT_RUN", error=str(e))
        rep.emit()
        return
    h = history(text, a.dat_name)
    if h["label"]:
        print("HIST", h["label"], "minutes=%s" % ("none" if h["minutes"] is None else h["minutes"]),
              "peak_gb=%s" % ("none" if h["peak_gb"] is None else h["peak_gb"]))
    else:
        print("HIST none")
    rep.check("H1_history", "PASS", **h)
    if h["runs_in_tail"] == 0:
        rep.note("No run entry was found in the tail (empty history, or the tail holds no complete entry).")
    rep.extra.update(h)
    rep.emit()


if __name__ == "__main__":
    run_main(TOOL, main)
