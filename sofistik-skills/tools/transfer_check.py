#!/usr/bin/env python3
"""Compare the saved PC read-backs W/raw/xfer__<k>__<PC name>.txt with the cloud copies named in sources.tsv
(replaces the inline "script V" of sofistik-cadinp-author / sofistik-run-and-fix).

usage: python3 -I transfer_check.py <raw_dir> <sources.tsv> [--workdir W]

Each xfer file holds read_text_file 'text' exactly as returned: lines 'N: content' (or 'N:content').  Line N is
compared with line N of the cloud copy (trailing blanks ignored, CR removed).  Files whose PC name is not in
sources.tsv are skipped (listed in the JSON).
Prints (same lines as script V):
  DIFF <name> line <i>              one per differing line (at most 50 printed)
  <name> <n> lines compared         one per file (n = distinct line numbers compared)
  TRANSFER_OK                       nothing differs and at least one line was compared
  TRANSFER_BAD first=<name>:<line>  the first differing file:line (or first=none when nothing was compared,
                                    first=<name>:missing when the cloud copy cannot be read)
then the one JSON verdict line (T1_transfer PASS / FAIL).
Change from script V: 'lines compared' counts distinct line numbers (overlapping windows no longer inflate it),
so the skill's 'master lines compared below wc -l of M' test is exact.
"""
from __future__ import annotations

import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cadinp as C  # noqa: E402
from _common import Parser, Report, input_record, run_main  # noqa: E402

TOOL = "transfer_check"
LINE_RE = re.compile(r"^(\d+): ?(.*)$")
MAX_PRINT = 50


def main():
    ap = Parser(TOOL, description="compare PC read-backs with the cloud copies",
                formatter_class=__import__("argparse").RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("raw_dir")
    ap.add_argument("sources")
    ap.add_argument("--workdir")
    a = ap.parse_args()
    rep = Report(TOOL, a.workdir, {"sources": input_record(a.sources, "sources")})
    mp = C.read_sources_tsv(a.sources)
    seen = {}            # name -> {line: ok}
    diffs, skipped, missing = [], [], []
    cloud = {}
    for f in sorted(glob.glob(os.path.join(a.raw_dir, "xfer__*__*.txt"))):
        name = os.path.basename(f).split("__", 2)[2][:-4]
        if name not in mp:
            skipped.append(os.path.basename(f))
            continue
        if name not in cloud:
            try:
                cloud[name] = open(mp[name], encoding="utf-8", errors="replace").read().replace("\r", "").split("\n")
            except OSError as e:
                cloud[name] = None
                missing.append(f"{name}: {e}")
        cl = cloud[name]
        if cl is None:
            continue
        for l in open(f, encoding="utf-8", errors="replace").read().replace("\r", "").split("\n"):
            g = LINE_RE.match(l)
            if not g:
                continue
            i = int(g.group(1))
            ok = i <= len(cl) and cl[i - 1].rstrip() == g.group(2).rstrip()
            d = seen.setdefault(name, {})
            if not ok and d.get(i, True):
                diffs.append((name, i))
            d[i] = d.get(i, True) and ok
    for k, (name, i) in enumerate(diffs):
        if k < MAX_PRINT:
            print("DIFF", name, "line", i)
    counts = {k: len(v) for k, v in seen.items()}
    for k, v in counts.items():
        print(k, v, "lines compared")
    if missing:
        first = f"{missing[0].split(':', 1)[0]}:missing"
    elif diffs:
        first = f"{diffs[0][0]}:{diffs[0][1]}"
    elif not counts:
        first = "none"
    else:
        first = None
    if first is None:
        print("TRANSFER_OK")
        rep.check("T1_transfer", "PASS", files=counts)
    else:
        print("TRANSFER_BAD", f"first={first}")
        rep.check("T1_transfer", "FAIL", first=first, n_diff=len(diffs), diffs=[f"{n}:{i}" for n, i in diffs[:MAX_PRINT]],
                  missing_cloud=missing, files=counts,
                  **({"meaning": "no line was compared (no xfer files, or none named in sources.tsv)"}
                     if first == "none" else {}))
    rep.extra.update(lines_compared=counts, skipped=skipped, first_diff=first)
    rep.emit()


if __name__ == "__main__":
    run_main(TOOL, main)
