#!/usr/bin/env python3
"""Number receipts (04 A1, 03 M4): every number quoted in a hand-back carries where it came from.

usage:
  python3 -I receipts.py add --workdir W --value V --unit U --tool TOOL --args '<JSON object>'
                             --cdb CDB --cdb-mtime MTIME --raw W/raw/<file>.json --path <json path> [--label TEXT]
  python3 -I receipts.py audit --workdir W [--n 5] [--seed S]
  python3 -I receipts.py verify --workdir W --id rN --raw <re-called result>.json
  python3 -I receipts.py --help

add    refuses (FAIL) a value that is not the number at --path in the saved raw tool result (A-18: the path ties
       the number to its meaning; it cannot be typed from memory or rounded); records the path, the raw file's
       SHA-256 and the exact MCP call to re-make (L10).
       Appends {"id": "rN", ...} to W/receipts.jsonl and prints the id.
audit  picks N receipts at random (system randomness unless --seed) for the LEAD to re-call: each "recall" entry
       carries "mcp_call", the exact call (tool and arguments) to re-make, and the JSON path to compare (L10); FAIL if a raw file has changed since the receipt or the value is no longer at its path;
       ESCALATE if a receipt has no cdb mtime; CANNOT_RUN if there are no receipts.
verify compares the value at the receipt's JSON path in a re-called result with the receipt (exact to 1e-9).
"""
from __future__ import annotations

import json
import os
import random
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import CannotRun, MissingField, Parser, Report, load_json, run_main, sha256_file, unwrap  # noqa: E402

TOOL = "receipts"
REL = 1e-9


def numbers(obj, path=""):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        yield path, float(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from numbers(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from numbers(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        try:
            yield path, float(obj)
        except ValueError:
            return


def at_path(obj, path):
    cur = obj
    for part in path.replace("[", ".[").split("."):
        if part == "":
            continue
        if part.startswith("["):
            cur = cur[int(part[1:-1])]
        else:
            cur = cur[part]
    return float(cur)


def mcp_call(tool, args):
    """The exact call the lead re-makes (L10): tool(name=value, ...) with JSON values."""
    if not isinstance(args, dict):
        return f"{tool}({json.dumps(args)})"
    return f"{tool}(" + ", ".join(f"{k}={json.dumps(v)}" for k, v in args.items()) + ")"


def same(a, b):
    return abs(a - b) <= REL * max(1.0, abs(b))


def rfile(w):
    return os.path.join(w, "receipts.jsonl")


def read_all(w):
    p = rfile(w)
    if not os.path.isfile(p):
        return []
    out = []
    with open(p, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def cmd_add(a, rep):
    for k in ("value", "unit", "tool", "args", "cdb", "cdb_mtime", "raw"):
        if getattr(a, k) in (None, ""):
            raise MissingField(f"--{k.replace('_', '-')} is required")
    try:
        v = float(a.value)
    except ValueError:
        raise MissingField(f"--value {a.value!r} is not a number")
    try:
        args = json.loads(a.args)
    except json.JSONDecodeError as e:
        raise MissingField(f"--args is not JSON ({e}); give the call arguments as a JSON object")
    if not a.path:
        raise MissingField("--path is required: the JSON path of the value in the raw result, e.g. "
                           "overall.N.min.value or rows[3].sum_reactions_kN[2] (review A-18)")
    raw = unwrap(load_json(a.raw))
    try:
        at = at_path(raw, a.path)
    except (KeyError, IndexError, ValueError, TypeError) as e:
        rep.check("receipt_add", "FAIL", value=v, path=a.path, error=f"path not in the raw result: {e}")
        return
    if not same(at, v):
        rep.check("receipt_add", "FAIL", value=v, path=a.path, got=at,
                  error="the value at this path differs: copy it exactly from the saved tool result")
        return
    hits = [a.path]
    rs = read_all(a.workdir)
    rid = f"r{len(rs) + 1}"
    rec = {"id": rid, "value": v, "unit": a.unit, "tool": a.tool, "args": args, "cdb": a.cdb,
           "cdb_mtime": a.cdb_mtime, "raw": os.path.abspath(a.raw), "raw_sha256": sha256_file(a.raw),
           "json_path": hits[0], "label": a.label or "", "mcp_call": mcp_call(a.tool, args)}
    os.makedirs(a.workdir, exist_ok=True)
    with open(rfile(a.workdir), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    rep.extra["action"] = "add"
    rep.extra["receipt_id"] = rid
    rep.check("receipt_add", "PASS", id=rid, value=v, unit=a.unit, json_path=hits[0])


def cmd_audit(a, rep):
    rs = read_all(a.workdir)
    rep.extra["action"] = "audit"
    if not rs:
        rep.check("receipts_present", "CANNOT_RUN", error=f"no receipts in {rfile(a.workdir)}")
        return
    rng = random.Random(a.seed) if a.seed is not None else secrets.SystemRandom()
    pick = rng.sample(rs, min(a.n, len(rs)))
    rep.extra["recall"] = [dict({k: r.get(k) for k in ("id", "value", "unit", "tool", "args", "cdb", "json_path")},
                                mcp_call=r.get("mcp_call") or mcp_call(r.get("tool"), r.get("args")),
                                then=f"save the re-call, run: receipts.py verify --workdir <W> --id {r.get('id')} "
                                     f"--raw <saved re-call>.json")
                           for r in pick]
    for r in rep.extra["recall"]:
        rep.note(f"LEAD RE-CALL {r['id']}: {r['mcp_call']} -> value at {r['json_path']} must be {r['value']} "
                 f"{r['unit'] or ''}")
    for r in rs:
        problems = [k for k in ("id", "value", "tool", "args", "cdb", "raw", "raw_sha256", "json_path") if not r.get(k)
                    and r.get(k) != 0]
        if problems:
            rep.check(f"receipt_{r.get('id')}", "FAIL", error=f"fields missing: {problems}")
            continue
        try:
            if sha256_file(r["raw"]) != r["raw_sha256"]:
                rep.check(f"receipt_{r['id']}", "FAIL", error="raw file changed after the receipt was written")
                continue
            if not same(at_path(unwrap(load_json(r["raw"])), r["json_path"]), float(r["value"])):
                rep.check(f"receipt_{r['id']}", "FAIL", error="value no longer at its JSON path")
                continue
        except (OSError, KeyError, IndexError, ValueError, TypeError, CannotRun) as e:
            rep.check(f"receipt_{r['id']}", "FAIL", error=f"cannot re-read raw file: {e}")
            continue
        if not r.get("cdb_mtime") or str(r["cdb_mtime"]).lower() in ("unknown", "none", "?"):
            rep.check(f"receipt_{r['id']}", "ESCALATE", error="no cdb mtime: freshness not provable")
    rep.check("receipts_audit", "PASS", receipts=len(rs), picked=[r["id"] for r in pick])
    rep.note("The lead re-calls each picked receipt's tool with the same args and runs "
             "'receipts.py verify --id <id> --raw <saved re-call>'. Any mismatch rejects the session (03 M4).")


def cmd_verify(a, rep):
    rep.extra["action"] = "verify"
    rs = {r["id"]: r for r in read_all(a.workdir)}
    if a.id not in rs:
        raise MissingField(f"receipt {a.id} not found")
    r = rs[a.id]
    try:
        got = at_path(unwrap(load_json(a.raw)), r["json_path"])
    except (KeyError, IndexError, ValueError, TypeError) as e:
        rep.check(f"verify_{a.id}", "FAIL", error=f"path {r['json_path']} not in the re-called result: {e}")
        return
    rep.check(f"verify_{a.id}", "PASS" if same(got, float(r["value"])) else "FAIL", expected=r["value"], got=got,
              json_path=r["json_path"])


def main():
    import argparse
    ap = Parser(TOOL, description="number receipts", formatter_class=argparse.RawDescriptionHelpFormatter,
                epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("add")
    p.add_argument("--workdir", required=True)
    p.add_argument("--value")
    p.add_argument("--unit")
    p.add_argument("--tool")
    p.add_argument("--args")
    p.add_argument("--cdb")
    p.add_argument("--cdb-mtime", dest="cdb_mtime")
    p.add_argument("--raw")
    p.add_argument("--label")
    p.add_argument("--path", help="JSON path of the value in the raw result (required), e.g. overall.N.min.value")
    q = sub.add_parser("audit")
    q.add_argument("--workdir", required=True)
    q.add_argument("--n", type=int, default=5)
    q.add_argument("--seed")
    v = sub.add_parser("verify")
    v.add_argument("--workdir", required=True)
    v.add_argument("--id", required=True)
    v.add_argument("--raw", required=True)
    for sp in (p, q, v):
        sp.error = ap.error
    a = ap.parse_args()
    if not a.cmd:
        ap.error("give a subcommand: add, audit or verify")
    rep = Report(TOOL, a.workdir)
    {"add": cmd_add, "audit": cmd_audit, "verify": cmd_verify}[a.cmd](a, rep)
    rep.emit()


if __name__ == "__main__":
    run_main(TOOL, main)
