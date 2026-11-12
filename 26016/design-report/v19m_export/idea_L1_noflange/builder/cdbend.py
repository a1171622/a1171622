"""End forces at a joint node from a SOFiSTiK cdb (read only). get(cdb_path, node_xyz, slns, lcs) -> {(sln, lc): dict(N..Mz, at='start'/'end', beam, dir)}"""
import sys, math
sys.path.insert(0, r"C:\Sofistik workflow\sofistik-mcp")
from sofistik_mcp import cdbio, results as R, install, config
class Model:
    def __init__(s, path):
        st = config.load_settings(r"C:\Sofistik workflow\sofistik-mcp\settings.json"); info = install.find(st)
        s.d = cdbio.load_daten(info.get("daten")); s.cdb = cdbio.Cdb(path, info)
        s.xyz = R._node_coords(s.cdb, s.d); s.ctx = R._beam_ctx(s.cdb, s.d); s.idx = s.ctx["idx"]
        s.cache = {}
    def node_at(s, p, tol=0.03):
        n = min(s.xyz, key=lambda k: math.dist(s.xyz[k], p)); return n if math.dist(s.xyz[n], p) < tol else None
    def beams_at(s, n): return [b for b, v in s.idx.items() if n in v["nodes"]]
    def forces(s, lc, beams):
        rows = R.beam_forces(s.cdb, s.d, lc, beams=",".join(map(str, beams)), max_rows=10 ** 6, ctx=s.ctx)["rows"]
        return rows
    def end_forces(s, node, lcs):
        bl = s.beams_at(node); out = {}
        for lc in lcs:
            rows = s.forces(lc, bl)
            for b in bl:
                rs = sorted([r for r in rows if r["beam"] == b], key=lambda r: r["x"])
                if not rs: continue
                a, e = s.idx[b]["nodes"]
                r = rs[0] if a == node else rs[-1]
                other = e if a == node else a
                out[(b, lc)] = dict(r, at="start" if a == node else "end", sln=s.idx[b]["sln"], other=other,
                                    dirv=[s.xyz[other][i] - s.xyz[node][i] for i in range(3)])
        return out
