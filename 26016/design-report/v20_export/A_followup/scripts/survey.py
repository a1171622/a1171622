import json, math, bisect, collections, pickle

from cdbx import open_cdb, R
cdb, d = open_cdb()
xyz = dict(R._node_coords(cdb, d)); beams = R._beam_index(cdb, d)
G = sorted({(g["min_element"], g["group"]) for g in R.groups(cdb, d) if g["min_element"] > 0})
k0 = next(iter(beams)); print("beam keys", beams[k0])
starts=[s for s,_ in G]
eg=lambda nr: G[bisect.bisect_right(starts,nr)-1][1]
pickle.dump(dict(xyz=xyz,beams=beams,G=G), open("model.pkl","wb"))
agg=collections.defaultdict(lambda: dict(n=0,sno=collections.Counter(),z=[],r=[]))
for b,v in beams.items():
    a=agg[eg(b)]; a["n"]+=1; a["sno"][v.get("sno")]+=1
    for n in v["nodes"]:
        x=xyz[n]; a["z"].append(x[2]); a["r"].append(math.hypot(x[0],x[1]))
for g in sorted(agg):
    a=agg[g]; print(g,a["n"],dict(a["sno"]),"z %.2f-%.2f r %.2f-%.2f"%(min(a["z"]),max(a["z"]),min(a["r"]),max(a["r"])))
