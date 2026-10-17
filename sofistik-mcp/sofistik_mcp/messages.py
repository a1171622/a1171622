"""Read SOFiSTiK text outputs (.prt protocol, .erg / .lst listings) and pull out errors and warnings.

Formats (SOFiSTiK 2027 manual "Troubleshooting", and real files from Wing's PC, 2026-10-14):
  .prt   *** Start: Program Calculation - Version 2027-0.0.139
         *** Start: Program aqb
         +++++ error no. 10001
         Data base aqb_steel_check.cdb not found or erroneous
          +++++    1 errors and    0 warnings +++++
         +++++ DATA ERRONEOUS, PROGRAM ABORTED +++++
         *** Stop : Program aqb
         *** Process canceled, error detected!
         *** End of Calculation!
  The manual also shows the long form "++++ ERROR NO. nnnnn IN PROGRAM xxxx" (and WARNING); both are
  matched, case-insensitive.  In the .erg the message follows the input line that caused it (ECHO).
"""
from __future__ import annotations

import os
import re

MSG_RE = re.compile(r"^\s*\+{3,}\s*(error|warning)\s+no\.?\s*(\d+)(?:\s+in\s+program\s+(\S+))?",
                    re.IGNORECASE)
TOTAL_RE = re.compile(r"\+{3,}\s*(\d+)\s+errors?\s+and\s+(\d+)\s+warnings?", re.IGNORECASE)
START_RE = re.compile(r"^\s*\*\*\*\s*Start\s*:\s*Program\s+(.+?)\s*$", re.IGNORECASE)
STOP_RE = re.compile(r"^\s*\*\*\*\s*Stop\s*:\s*Program\s+(.+?)\s*$", re.IGNORECASE)
ABORT_RE = re.compile(r"PROGRAM\s+ABORTED|Process\s+canceled|abnormal\s+termination|fatal\s+error",
                      re.IGNORECASE)
END_RE = re.compile(r"\*\*\*\s*End\s+of\s+Calculation", re.IGNORECASE)


def read_text(path: str, max_bytes: int = 50_000_000) -> str:
    """Read a SOFiSTiK text file: NUL bytes removed, CRLF -> LF, UTF-8 or else cp1252."""
    with open(path, "rb") as f:
        raw = f.read(max_bytes)
    raw = raw.replace(b"\x00", b"")
    for enc in ("utf-8", "cp1252"):
        try:
            txt = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        txt = raw.decode("latin-1", errors="replace")
    return txt.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")


def parse_protocol(text: str, context_before: int = 0, max_messages: int = 200) -> dict:
    """Errors, warnings, programs and the end state found in a .prt (or .erg / .lst) text.

    Each message: kind, number, program, line (1-based), text (the explanation lines after it),
    and with context_before > 0 the input lines before it (useful for the .erg ECHO)."""
    lines = text.split("\n")
    programs = []           # [{name, line, stop_line, errors, warnings, aborted}]
    current = None
    messages = []
    n_err = n_warn = 0
    aborted_lines = []
    for i, ln in enumerate(lines):
        m = START_RE.match(ln)
        if m:
            name = m.group(1)
            if not name.lower().startswith("calculation"):
                current = {"program": name, "line": i + 1, "stop_line": None, "errors": None,
                           "warnings": None, "aborted": False}
                programs.append(current)
            continue
        m = STOP_RE.match(ln)
        if m:
            if current is not None:
                current["stop_line"] = i + 1
            current = None
            continue
        m = TOTAL_RE.search(ln)
        if m:
            if current is not None:
                current["errors"], current["warnings"] = int(m.group(1)), int(m.group(2))
            continue
        if ABORT_RE.search(ln):
            aborted_lines.append({"line": i + 1, "text": ln.strip()})
            if current is not None:
                current["aborted"] = True
            continue
        m = MSG_RE.match(ln)
        if m:
            kind = m.group(1).lower()
            if kind == "error":
                n_err += 1
            else:
                n_warn += 1
            if len(messages) < max_messages:
                expl = []
                for nxt in lines[i + 1:i + 9]:
                    if not nxt.strip() or MSG_RE.match(nxt) or TOTAL_RE.search(nxt) or nxt.strip().startswith("***"):
                        break
                    expl.append(nxt.strip())
                msg = {"kind": kind, "number": int(m.group(2)),
                       "program": m.group(3) or (current["program"] if current else ""),
                       "line": i + 1, "text": " ".join(expl)}
                if context_before > 0:
                    msg["input_before"] = [x.rstrip() for x in lines[max(0, i - context_before):i]
                                           if x.strip()]
                messages.append(msg)
    return {
        "programs": programs,
        "errors": n_err,
        "warnings": n_warn,
        "messages": messages,
        "messages_truncated": (n_err + n_warn) > len(messages),
        "aborted": aborted_lines,
        "finished": bool(END_RE.search(text)),
    }


def summarize_run(prt_path: str | None, erg_path: str | None = None) -> dict:
    """Combine the .prt (authoritative for counts and end state) with the .erg (input context)."""
    out = {"prt": prt_path if prt_path and os.path.isfile(prt_path) else None,
           "erg": erg_path if erg_path and os.path.isfile(erg_path) else None}
    if out["prt"]:
        p = parse_protocol(read_text(out["prt"]))
    else:
        p = {"programs": [], "errors": 0, "warnings": 0, "messages": [], "messages_truncated": False,
             "aborted": [], "finished": False}
    out.update(p)
    # totals printed per program are the most complete count (messages may be suppressed in the .prt)
    tot_e = sum(x["errors"] or 0 for x in p["programs"])
    tot_w = sum(x["warnings"] or 0 for x in p["programs"])
    out["errors"] = max(out["errors"], tot_e)
    out["warnings"] = max(out["warnings"], tot_w)
    if out["erg"]:
        e = parse_protocol(read_text(out["erg"]), context_before=6, max_messages=60)
        out["erg_messages"] = [m for m in e["messages"] if m["kind"] == "error"][:30] + \
                              [m for m in e["messages"] if m["kind"] == "warning"][:30]
    if not out["prt"]:
        out["status"] = "no protocol"
    elif out["errors"] or out["aborted"]:
        out["status"] = "errors"
    elif not out["finished"]:
        out["status"] = "not finished"
    elif out["warnings"]:
        out["status"] = "ok with warnings"
    else:
        out["status"] = "ok"
    return out
