import json, math, collections
from geo import *
from cdbx import open_cdb, R
cdb, d = open_cdb()
E=json.load(open("erg_parsed.json")); BDK={int(k):v for k,v in E["bdk"].items()}; AQB={int(k):v for k,v in E["aqb"].items()}
out={}
# section per beam from AQB stations
bsno={b:recs[0]["sno"] for b,recs in AQB.items() if recs}
# ---------- A1 BDK per group
def grp_of_id(i):
    if i in SL and SL[i]["grp"]: return SL[i]["grp"]
    bs=[b for b,v in beams.items() if v["sln"]==i]
    return eg(bs[0]) if bs else None
def sno_of_id(i):
    if i in SL and SL[i]["sno"]: return SL[i]["sno"]
    bs=[b for b,v in beams.items() if v["sln"]==i]
    return bsno.get(bs[0]) if bs else None
A1={}
for i,r in BDK.items():
    g=grp_of_id(i); key=str(g)
    if g==25: key="25/sno%s"%sno_of_id(i)
    for k in {str(g),key}:
        if k not in A1 or r["util"]>A1[k]["util"]: A1[k]=dict(util=r["util"],sln=i,lc=r["lc"],check=r["check"])
out["A1"]=A1
# ---------- A2 AQB per section
A2={}
for b,recs in AQB.items():
    for r in recs:
        if r["util"] is None: continue
        s=r["sno"]
        if s not in A2 or r["util"]>A2[s]["util"]:
            A2[s]=dict(util=r["util"],beam=b,group=eg(b),sln=beams.get(b,{}).get("sln"),lc=r["lc"],x=r["x"],sig_v=r["sig_v"],tot_int=r["tot_int"])
out["A2"]=A2
# ---------- A3 modes
A3={}
for lc in (9201,9220,9221,9240):
    rows=R._node_rows(cdb,d,lc,None)
    if not rows: A3[lc]="none"; continue
    m=max(rows,key=lambda r:math.sqrt(r["ux"]**2+r["uy"]**2+r["uz"]**2))
    n=m["node"]; gs=collections.Counter(eg(b) for b in node_beams[n])
    tot=math.sqrt(m["ux"]**2+m["uy"]**2+m["uz"]**2)
    # share by group: max |u| of nodes per group
    gmax={}
    for r in rows:
        u=math.sqrt(r["ux"]**2+r["uy"]**2+r["uz"]**2)
        for g in {eg(b) for b in node_beams[r["node"]]}:
            gmax[g]=max(gmax.get(g,0),u)
    A3[lc]=dict(node=n,xyz=xyz[n],r_theta_z=pol(n),u=[m["ux"],m["uy"],m["uz"]],utot=tot,groups=dict(gs),gmax_rel={g:round(v/tot,3) for g,v in sorted(gmax.items())})
out["A3"]=A3
LCS={l["lc"]:l["title"] for l in R.load_cases(cdb,d)}
out["A3titles"]={lc:LCS.get(lc) for lc in (9201,9220,9221,9240)}
json.dump(out,open("partA1.json","w"),indent=1,default=str)
print(json.dumps(out,indent=1,default=str)[:6000])
