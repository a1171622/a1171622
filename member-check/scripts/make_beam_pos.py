"""Where each beam element sits on the structural lines of the .dat (needed when SOFiMSHC split lines).

Inputs come from the SOFiSTiK MCP tools (saved as JSON by Claude Code):
  cbeam.json  {beam: {"nodes": [n1, n2], "sln": ..}}  from cdb_read_key key 100/0 (CBEAM), paged with skip
  nodes.json  {"rows": [{"node", "x", "y", "z"}]}       from cdb_nodes
    python scripts/make_beam_pos.py --dat model.dat --cbeam cbeam.json --nodes nodes.json --out beam_pos.json
The checker then reads forces by position on the original line: python -m memcheck.run ... --beam-pos beam_pos.json
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from memcheck import sofistik as S  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--dat", required=True)
ap.add_argument("--cbeam", required=True)
ap.add_argument("--nodes", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()
_, slns, _ = S.read_dat(a.dat)
cb = json.load(open(a.cbeam))
nd = {r["node"]: (r["x"], r["y"], r["z"]) for r in json.load(open(a.nodes))["rows"]}
bp = S.beam_positions(cb, nd, slns)
json.dump({str(k): v for k, v in bp.items()}, open(a.out, "w"))
print(f"{len(bp)} of {len(cb)} beams placed on structural lines -> {a.out}")
