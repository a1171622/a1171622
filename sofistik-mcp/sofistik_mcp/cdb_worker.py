"""Reads a .cdb in a separate process, so that SOFiSTiK's DLL can never print into the MCP channel or
crash the server.  Called by server.py as:

    python -m sofistik_mcp.cdb_worker request.json answer.json

request.json: {"op": "...", "cdb": "C:\\...\\model.cdb", "info": {install dict}, "args": {...}}
answer.json:  {"ok": true, "result": {...}}  or  {"ok": false, "error": "..."}
"""
from __future__ import annotations

import json
import os
import sys
import traceback

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "sofistik_mcp"

from sofistik_mcp import cdbio, results  # noqa: E402

OPS = {
    "overview": lambda c, d, a: results.overview(c, d),
    "load_cases": lambda c, d, a: results.load_cases(c, d, only=results.parse_ids(a.get("lcs"))),
    "nodes": lambda c, d, a: results.nodes(c, d, ids=a.get("ids"), max_rows=a.get("max_rows", 500)),
    "node_results": lambda c, d, a: results.node_results(c, d, a["lc"], ids=a.get("ids"),
                                                         max_rows=a.get("max_rows", 200),
                                                         include_coords=a.get("include_coords", False)),
    "support_reactions": lambda c, d, a: results.support_reactions(c, d, a["lc"], ids=a.get("ids"),
                                                                   max_rows=a.get("max_rows", 500)),
    "beam_forces": lambda c, d, a: results.beam_forces(c, d, a["lc"], beams=a.get("beams"),
                                                       groups_=a.get("groups"), slns=a.get("slns"),
                                                       max_rows=a.get("max_rows", 300),
                                                       ends_only=a.get("ends_only", False)),
    "axial_forces": lambda c, d, a: results.axial_forces(c, d, a["lc"], element_type=a.get("element_type", "truss"),
                                                         ids=a.get("ids"), max_rows=a.get("max_rows", 300)),
    "envelope": lambda c, d, a: results.envelope(c, d, a["lcs"], what=a.get("what", "beam"), ids=a.get("ids"),
                                                 groups_=a.get("groups"), slns=a.get("slns")),
    "read_key": lambda c, d, a: results.read_key(c, d, a["kwh"], a["kwl"], class_name=a.get("class_name"),
                                                 max_records=a.get("max_records", 20), skip=a.get("skip", 0)),
}


def handle(req: dict) -> dict:
    op = req.get("op")
    if op not in OPS:
        return {"ok": False, "error": f"unknown operation {op}"}
    info = req["info"]
    daten = cdbio.load_daten(info.get("daten"))
    cdb = cdbio.Cdb(req["cdb"], info)
    try:
        res = OPS[op](cdb, daten, req.get("args") or {})
        if getattr(cdb, "truncated", 0):
            res["warning_truncated_records"] = cdb.truncated
        return {"ok": True, "result": res}
    finally:
        cdb.close()


def main(argv):
    req_path, ans_path = argv[1], argv[2]
    try:
        with open(req_path, encoding="utf-8") as f:
            req = json.load(f)
        ans = handle(req)
    except (cdbio.CdbError, ValueError, KeyError) as e:
        ans = {"ok": False, "error": str(e)}
    except Exception as e:  # pragma: no cover - unexpected; give the engineer the traceback
        ans = {"ok": False, "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-3000:]}
    with open(ans_path, "w", encoding="utf-8") as f:
        json.dump(ans, f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
