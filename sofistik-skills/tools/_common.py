"""Shared helpers for the proof tools (stdlib only).

Output contract (06_TOOLS_CONTRACT.md): every tool prints ONE JSON object
  {"tool": ..., "verdict": "PASS"|"FAIL"|"ESCALATE"|"CANNOT_RUN", "checks": [...], "notes": [...]}
to stdout, appends the same object as one line to <workdir>/proofs.jsonl when --workdir is given,
and exits 0 PASS, 1 FAIL, 2 ESCALATE, 3 CANNOT_RUN.

Loading saved tool results: Haiku saves MCP results by hand, so a file may be
  * the result object itself                      {"lc": 1, "rows": [...], ...}
  * an MCP envelope                               {"result": {...}} / {"structuredContent": {...}}
  * an MCP content list                           [{"type": "text", "text": "{...json...}"}]
  * a list result the server wrapped              {"rows": [...]}   (server.py _cdb_call wraps lists)
  * pretty-printed / re-indented / with a UTF-8 BOM / with trailing commas removed by hand
unwrap() accepts all of these.  Nothing else is guessed: a missing field is an error (need()).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import sys

EXIT = {"PASS": 0, "FAIL": 1, "ESCALATE": 2, "CANNOT_RUN": 3}
# A definite FAIL outranks "could not run" (review A-22): a tool with one FAIL check and one CANNOT_RUN check
# reports FAIL (exit 1), so a found fault is never hidden behind "not checked".
RANK = {"PASS": 0, "ESCALATE": 1, "CANNOT_RUN": 2, "FAIL": 3}


class MissingField(Exception):
    """A required field is absent or None in an input file: the tool must not guess it."""


class CannotRun(Exception):
    pass


def worst(*verdicts):
    vs = [v for v in verdicts if v]
    if not vs:
        return "PASS"
    return max(vs, key=lambda v: RANK[v])


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _strip_json_text(t: str) -> str:
    t = t.lstrip("﻿").strip()
    # a hand-saved file sometimes carries a ```json fence
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
    return t


def load_json(path):
    """Read a JSON file (BOM, code fences tolerated).  Raises CannotRun with a clear message."""
    if not os.path.isfile(path):
        raise CannotRun(f"file not found: {path}")
    with open(path, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    text = _strip_json_text(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise CannotRun(f"{path} is not valid JSON ({e}); save the tool result again, whole and unedited")


def unwrap(obj, _depth=0):
    """Remove MCP / hand-saving envelopes around a cdb_* result (see module doc)."""
    if _depth > 6:
        return obj
    if isinstance(obj, list) and obj and all(isinstance(x, dict) and x.get("type") == "text" and "text" in x
                                            for x in obj):
        texts = [x["text"] for x in obj]
        for t in texts:
            try:
                return unwrap(json.loads(_strip_json_text(t)), _depth + 1)
            except json.JSONDecodeError:
                continue
        return obj
    if isinstance(obj, dict):
        if set(obj) <= {"content", "isError", "structuredContent", "_meta"} and "content" in obj:
            if obj.get("structuredContent") is not None:
                return unwrap(obj["structuredContent"], _depth + 1)
            return unwrap(obj["content"], _depth + 1)
        if set(obj) <= {"structuredContent", "isError", "_meta"} and "structuredContent" in obj:
            return unwrap(obj["structuredContent"], _depth + 1)
        if set(obj) <= {"result", "id", "jsonrpc", "tool", "args", "name"} and "result" in obj:
            return unwrap(obj["result"], _depth + 1)
        # FastMCP wraps non-dict returns as {"result": ...}
        if list(obj) == ["result"]:
            return unwrap(obj["result"], _depth + 1)
    return obj


def need(d, key, where=""):
    """d[key], or MissingField.  None counts as missing (never default a value)."""
    if not isinstance(d, dict) or key not in d or d[key] is None:
        raise MissingField(f"missing field '{key}'" + (f" in {where}" if where else ""))
    return d[key]


def num(v, what):
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise MissingField(f"{what} is not a number: {v!r}")
    if f != f:
        raise MissingField(f"{what} is NaN")
    return f


def parse_ids(spec):
    """'1-10,15,20-30' / [1,2] / 7 / '(101 130 1)' -> sorted list of ints."""
    if spec is None or spec == "":
        return []
    if isinstance(spec, int):
        return [spec]
    if isinstance(spec, (list, tuple, set)):
        out = set()
        for s in spec:
            out |= set(parse_ids(s))
        return sorted(out)
    out = set()
    s = str(spec).strip()
    for m in re.finditer(r"\(\s*(-?\d+)\s+(-?\d+)(?:\s+(-?\d+))?\s*\)", s):
        a, b, st = int(m.group(1)), int(m.group(2)), int(m.group(3) or 1)
        out.update(range(a, b + 1, st or 1))
    s = re.sub(r"\(\s*-?\d+\s+-?\d+(?:\s+-?\d+)?\s*\)", " ", s)
    s = re.sub(r"\s*(-|\bto\b|\.\.)\s*", r"\1", s, flags=re.I)
    for part in re.split(r"[,\s;]+", s):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)(?:-|to|\.\.)(\d+)", part, re.I)
        if m:
            a, b = sorted((int(m.group(1)), int(m.group(2))))
            out.update(range(a, b + 1))
        elif re.fullmatch(r"-?\d+", part):
            out.add(int(part))
        else:
            raise ValueError(f"cannot read number list {spec!r}")
    return sorted(out)


def rows_of(obj, where):
    """The 'rows' list of a cdb_* result (cdb_load_cases: list wrapped as {'rows': [...]})."""
    obj = unwrap(obj)
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        if obj.get("error"):
            raise MissingField(f"{where} holds a tool error, not results: {obj['error']}")
        if "rows" in obj and isinstance(obj["rows"], list):
            return obj["rows"]
    raise MissingField(f"no 'rows' list in {where}")


def stale_of(obj):
    obj = unwrap(obj)
    if isinstance(obj, dict) and obj.get("stale_results_warning"):
        w = obj["stale_results_warning"]
        return w if isinstance(w, list) else [str(w)]
    return []


class Report:
    """Collects checks / notes and emits the one JSON object."""

    def __init__(self, tool, workdir=None, inputs=None):
        self.tool = tool
        self.workdir = workdir
        self.checks = []
        self.notes = []
        self.extra = {}
        self.inputs = inputs or {}
        self.verdict = "PASS"

    def check(self, cid, verdict, **kw):
        c = {"id": cid, "verdict": verdict}
        c.update(kw)
        self.checks.append(c)
        self.verdict = worst(self.verdict, verdict)
        return c

    def note(self, text):
        self.notes.append(text)

    def force(self, verdict):
        self.verdict = worst(self.verdict, verdict)

    def obj(self):
        o = {"tool": self.tool, "verdict": self.verdict, "checks": self.checks, "notes": self.notes,
             "time_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        if self.inputs:
            o["inputs"] = self.inputs
        o.update(self.extra)
        return o

    def emit(self, exit_now=True):
        o = self.obj()
        text = json.dumps(o, ensure_ascii=False, default=str)
        print(text)
        if self.workdir:
            os.makedirs(self.workdir, exist_ok=True)
            with open(os.path.join(self.workdir, "proofs.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(o, ensure_ascii=False, default=str) + "\n")
        if exit_now:
            sys.exit(EXIT[self.verdict])
        return o


def input_record(path, role):
    """{'role':..., 'path':..., 'sha256':...} for the proof header (scorecard compares hashes)."""
    try:
        return {"path": os.path.abspath(path), "sha256": sha256_file(path)}
    except OSError:
        return {"path": path, "sha256": None}


def run_main(tool, fn, argv=None):
    """Run fn(report, args) with the uniform error handling: CannotRun / MissingField -> CANNOT_RUN or FAIL."""
    import argparse  # noqa: F401
    rep = None
    try:
        return fn()
    except SystemExit:
        raise
    except (CannotRun, MissingField, ValueError) as e:
        rep = Report(tool, _workdir_from_argv(argv))
        rep.check("input", "CANNOT_RUN", error=str(e))
        rep.note("Fail closed: the check could not run, so it is not a PASS. Fix the input file (missing fields "
                 "are never defaulted) and run again.")
        rep.emit()


def _workdir_from_argv(argv=None):
    a = list(sys.argv if argv is None else argv)
    for i, x in enumerate(a):
        if x == "--workdir" and i + 1 < len(a):
            return a[i + 1]
        if x.startswith("--workdir="):
            return x.split("=", 1)[1]
    return None


class Parser:
    """argparse that turns usage errors into a CANNOT_RUN JSON (exit 3) instead of exit 2 (= ESCALATE)."""

    def __new__(cls, tool, **kw):
        import argparse

        class _P(argparse.ArgumentParser):
            def error(self, message):
                rep = Report(tool, _workdir_from_argv())
                rep.check("usage", "CANNOT_RUN", error=message, usage=self.format_usage().strip())
                rep.note("Usage error. Run the script with --help once, then retry with that usage.")
                rep.emit()

        return _P(**kw)
