import json, collections; from cdbx import *
cdb, d = open_cdb()
xyz = R._node_coords(cdb, d)
q = {}
for rec in cdb.records(200, 0):
    if R.first_int(rec) > 0:
        e = R.as_rec(d, "CQUAD", rec); q[int(e.m_nr)] = [int(n) for n in e.m_node]
ctx = R._beam_ctx(cdb, d)
json.dump({"xyz": xyz, "quads": q, "beams": ctx["idx"], "sln_groups": ctx["sln_groups"]}, open("model.json", "w"))
def band(ns):
    zs=[xyz[n][2] for n in ns if n in xyz]; return (round(min(zs),2), round(max(zs),2), len(set(ns)))
for g,(a,b) in {1:(10000,30000),2:(30000,40000),6:(40000,50000),7:(50000,60000)}.items():
    ns=[n for k,v in q.items() if a<=k<b for n in v if n>0]; print("quad grp",g,band(ns))
bg=collections.defaultdict(list)
for k,v in ctx["idx"].items(): bg[ctx["sln_groups"].get(v["sln"])].extend(v["nodes"])
for g in sorted(bg, key=lambda x: (x is None, x)): print("beam grp",g,band(bg[g]))
cdb.close()
