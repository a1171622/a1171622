"""Collect beam forces saved from the SOFiSTiK MCP tool cdb_beam_forces into one forces.csv.gz.

The MCP result for a whole load case is too big to show, so Claude Code saves it as a JSON .txt file.  This script
picks those files up, keeps one file per (load case, group set), and writes the table the checker reads:
    lc, beam, sln, group, x, N, Vy, Vz, Mt, My, Mz      (x = station from the beam start, m)

    python scripts/harvest_mcp.py --src <tool-results folder> --store forces/ --out forces.csv.gz
Each load case is fetched in two calls (row cap): groups "11-15,21-24,60,61" -> part A, "25,31,35" -> part B
(26016 grouping; any other split works as long as every call returns whole groups).  Truncated results are refused.
"""
import argparse
import csv
import glob
import gzip
import json
import os
import shutil


def harvest(src, store):
    os.makedirs(store, exist_ok=True)
    for f in glob.glob(os.path.join(src, "*beam_forces*.txt")):
        try:
            d = json.load(open(f))
        except Exception as e:  # not a JSON result
            print("skip (not JSON)", f, e)
            continue
        if d.get("truncated"):
            print("REFUSED (truncated, raise max_rows)", f, d.get("lc"))
            continue
        gs = sorted({r["group"] for r in d["rows"]})
        tag = "g" + "-".join(map(str, gs[:3])) + f"_{len(gs)}"
        shutil.move(f, os.path.join(store, f"lc{d['lc']}_{tag}.json"))
    return sorted(glob.glob(os.path.join(store, "lc*.json")))


def build(files, out):
    n = 0
    seen = set()
    with gzip.open(out, "wt", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["lc", "beam", "sln", "group", "x", "N", "Vy", "Vz", "Mt", "My", "Mz"])
        for fn in files:
            d = json.load(open(fn))
            for r in d["rows"]:
                key = (d["lc"], r["beam"], r["x"])
                if key in seen:
                    continue
                seen.add(key)
                w.writerow([d["lc"], r["beam"], r["sln"], r["group"], r["x"], r["N"], r["Vy"], r["Vz"], r["Mt"],
                            r["My"], r["Mz"]])
                n += 1
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="folder where Claude Code saved the large MCP results")
    ap.add_argument("--store", required=True, help="folder to keep one JSON per load case and group set")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    files = harvest(a.src, a.store)
    lcs = sorted({int(os.path.basename(f)[2:].split("_")[0]) for f in files})
    print(f"{len(files)} files, load cases {lcs}")
    print(build(files, a.out), "rows ->", a.out)
