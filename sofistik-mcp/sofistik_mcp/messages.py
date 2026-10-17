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
    return decode_text(raw)


def _lines(txt: str) -> str:
    return txt.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")


def decode_text(raw: bytes) -> str:
    """Bytes of a SOFiSTiK text file -> text, as read_text (a UTF-8 BOM is dropped)."""
    raw = raw.replace(b"\x00", b"")
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    for enc in ("utf-8", "cp1252"):
        try:
            txt = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        txt = raw.decode("latin-1", errors="replace")
    return _lines(txt)


# byte order marks: UTF-32 before UTF-16 (FF FE 00 00 starts with FF FE)
UNICODE_BOMS = ((b"\x00\x00\xfe\xff", "utf-32-be"), (b"\xff\xfe\x00\x00", "utf-32-le"),
                (b"\xfe\xff", "utf-16-be"), (b"\xff\xfe", "utf-16-le"))
# marks of encodings an input file is never checked in (UTF-7, UTF-1, UTF-EBCDIC, SCSU, BOCU-1, GB 18030)
OTHER_BOMS = (b"\x2b\x2f\x76", b"\xf7\x64\x4c", b"\xdd\x73\x66\x73", b"\x0e\xfe\xff", b"\xfb\xee\x28",
              b"\x84\x31\x95\x33")


def decode_input(raw: bytes) -> tuple[str, str]:
    """Bytes of a .dat (or #INCLUDE / +APPLY file) -> (text for the +SYS check, encoding whose byte counts
    apply to its lines).  UTF-16 / UTF-32 with a byte order mark are decoded by it; otherwise as
    decode_text (UTF-8, else cp1252; counted as UTF-8, which never has fewer bytes).  Raises ValueError
    (the reason) for a file that cannot be read for certain the way SOFiSTiK reads it: NUL bytes without
    a UTF-16 / UTF-32 mark, a mark of another encoding, or bytes that are not valid in the marked encoding."""
    for bom, enc in UNICODE_BOMS:
        if raw.startswith(bom):
            try:
                txt = raw[len(bom):].decode(enc)
            except UnicodeDecodeError as e:
                raise ValueError(f"it starts with a {enc.upper()} byte order mark but is not valid {enc.upper()} "
                                 f"(byte {e.start + len(bom)})") from None
            if "\x00" in txt:
                raise ValueError(f"it contains NUL characters ({enc.upper()} text)")
            return _lines(txt), enc
    if raw.startswith(OTHER_BOMS):
        raise ValueError("it starts with the byte order mark of an encoding that is not checked (UTF-7 or "
                         "similar); save it as UTF-8 or ANSI")
    nul = raw.find(b"\x00")
    if nul >= 0:
        raise ValueError(f"it contains NUL bytes (first at byte {nul}; UTF-16 without a byte order mark?); "
                         "save it as UTF-8 or ANSI")
    return decode_text(raw), "utf-8"


def parse_protocol(text: str, context_before: int = 0, max_messages: int = 200) -> dict:
    """Errors, warnings, programs and the end state found in a .prt (or .erg / .lst) text.

    Each message: kind, number, program, line (1-based), text (the explanation lines after it),
    and with context_before > 0 the input lines before it (useful for the .erg ECHO)."""
    lines = text.split("\n")
    programs = []           # [{name, line, stop_line, errors, warnings, aborted}]
    current = None
    messages: list = []
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
    out: dict = {"prt": prt_path if prt_path and os.path.isfile(prt_path) else None,
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
    # A program without its "*** Stop" line did not finish.  The "n errors and m warnings" totals line is
    # only a note: no clean SOFiSTiK 2027 protocol has been seen yet to prove it is printed on every run
    # (the self-test report shows whether it was there), so its absence must not fail a good run.
    out["unfinished_programs"] = [x["program"] for x in p["programs"] if x["stop_line"] is None]
    out["programs_without_totals"] = [x["program"] for x in p["programs"]
                                      if x["stop_line"] is not None and x["errors"] is None]
    if out["programs_without_totals"]:
        out["notes"] = [("No 'n errors and m warnings' line for " + ", ".join(out["programs_without_totals"]) +
                         "; the counts come from the messages found in the protocol.")]
    if not out["prt"]:
        out["status"] = "no protocol"
    elif out["errors"] or out["aborted"]:
        out["status"] = "errors"
    elif not out["finished"] or out["unfinished_programs"]:
        out["status"] = "not finished"
    elif out["warnings"]:
        out["status"] = "ok with warnings"
    else:
        out["status"] = "ok"
    return out
