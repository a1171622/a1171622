import json, math, collections
from geo import *
from cdbx import open_cdb, R
cdb, d = open_cdb()
LT={l["lc"]:l for l in R.load_cases(cdb,d)}
def sup(lc): return {r["node"]:r for r in R.support_reactions(cdb,d,lc,max_rows=100000)["rows"]}
S102,S201=sup(102),sup(201); EQ={lc:sup(lc) for lc in (131,132,133,134)}
o={}
rows=[]
for n in sorted(S102):
    r=pol(n) if n in xyz else (None,None,None)
    eqmin=min(((EQ[lc].get(n,{}).get("pz",0),lc) for lc in EQ))
    rows.append(dict(node=n,x=xyz[n][0],y=xyz[n][1],r=r[0],th=r[1],px=S102[n]["px"],py=S102[n]["py"],pz=S102[n]["pz"],pz201=S201.get(n,{}).get("pz"),eq=eqmin,
                     m=[S102[n][k] for k in ("mx","my","mz")]))
o["rows"]=rows
o["tot102"]=[round(sum(r["px"] for r in rows),2),round(sum(r["py"] for r in rows),2),round(sum(r["pz"] for r in rows),2)]
o["tot201"]=round(sum(S201[n]["pz"] for n in S201),2)
o["stored102"]=LT[102].get("sum_reactions_kN"); o["stored201"]=LT[201].get("sum_reactions_kN")
o["missing201"]=[n for n in S102 if n not in S201]+[n for n in S201 if n not in S102]
# A7 STR envelope
STR=[lc for lc in range(101,155) if lc in LT and "nodes" in (LT[lc].get("has_results") or []) and lc not in (131,132,133,134)]
o["STR"]=STR
mx=mn=hh=None
for lc in STR:
    for n,r in sup(lc).items():
        h=math.hypot(r["px"],r["py"])
        if mx is None or r["pz"]>mx[0]: mx=(r["pz"],n,lc)
        if mn is None or r["pz"]<mn[0]: mn=(r["pz"],n,lc)
        if hh is None or h>hh[0]: hh=(h,n,lc,r["px"],r["py"],r["pz"])
o["A7"]=dict(max=mx,min=mn,hmax=hh)
# A8 ring SLN 56 LC 120 forces along beams
bl=[b for b,v in beams.items() if v["sln"]==56]
bf=R.beam_forces(cdb,d,120,beams=",".join(map(str,bl)),max_rows=10000)
st=[]
for r in bf["rows"]:
    a,c=beams[r["beam"]]["nodes"]; st.append((r["beam"],r["x"],r["N"],r["Vz"],r["My"],r["Mz"],round(pol(a)[1],2),round(pol(c)[1],2)))
o["A8_stations"]=sorted(st,key=lambda t:(t[0],t[1]))
# neighbour SLNs moments at nodes 1460 / 1485
for s in (55,57,1460):
    pass
nb={}
for n in (1460,1485):
    for b in node_beams[n]:
        if eg(b)==25:
            f=R.beam_forces(cdb,d,120,beams=str(b),max_rows=100)["rows"]
            a,c=beams[b]["nodes"]; end=f[0] if a==n else f[-1]
            nb.setdefault(n,[]).append(dict(beam=b,sln=beams[b]["sln"],start_node=a,end_node=c,x=end["x"],N=end["N"],Vz=end["Vz"],My=end["My"],Mz=end["Mz"],th=[round(pol(a)[1],1),round(pol(c)[1],1)],r=[round(pol(a)[0],2),round(pol(c)[0],2)]))
o["A8_nodes"]=nb
json.dump(o,open("partA3.json","w"),indent=1,default=str)
