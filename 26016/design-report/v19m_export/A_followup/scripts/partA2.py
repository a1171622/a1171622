import json, math, collections
from geo import *
from cdbx import open_cdb, R
cdb, d = open_cdb()
E=json.load(open("erg_parsed.json")); AQB={int(k):v for k,v in E["aqb"].items()}
bsno={b:recs[0]["sno"] for b,recs in AQB.items() if recs}
LT={l["lc"]:l["title"] for l in R.load_cases(cdb,d)}
NC={}
def U(lc):
    if lc not in NC: NC[lc]={r["node"]:r for r in R._node_rows(cdb,d,lc,None)}
    return NC[lc]
def Usum(lcs):
    k=tuple(lcs)
    if k not in NC:
        acc={}
        for lc in lcs:
            for n,r in U(lc).items():
                a=acc.setdefault(n,dict(node=n,ux=0,uy=0,uz=0))
                for c in ("ux","uy","uz"): a[c]+=r[c]
        NC[k]=acc
    return NC[k]
def uz(lc,n): return (Usum(lc) if isinstance(lc,tuple) else U(lc))[n]["uz"]
out={}
SLS=list(range(201,222)); GQW=list(range(210,214))+list(range(218,222)); GW=list(range(202,210))
def span_defl(nodes, lc):
    """nodes ordered along the span, ends = supports. returns abs min uz, rel min (vs chord), node"""
    P=[xyz[n] for n in nodes]; s=[0]
    for i in range(1,len(P)): s.append(s[-1]+math.dist(P[i-1],P[i]))
    L=s[-1]; ua=uz(lc,nodes[0]); ub=uz(lc,nodes[-1])
    best=None; amin=None
    for n,si in zip(nodes,s):
        u=uz(lc,n); rel=u-(ua+(ub-ua)*si/L)
        if best is None or abs(rel)>abs(best[0]): best=(rel,n,si,u)
        if amin is None or u<amin[0]: amin=(u,n)
    return dict(L=round(L,3),rel=round(best[0],2),rel_node=best[1],rel_at_m=round(best[2],2),uz_abs_at_rel=round(best[3],2),uz_abs_min=round(amin[0],2),abs_node=amin[1],end_uz=[round(ua,2),round(ub,2)])
def worst(spans, lcs, sign=-1):
    """spans list of (label,nodes); over lcs, max downward (sign -1) or upward (+1) relative deflection"""
    best=None
    for lab,ns in spans:
        for lc in lcs:
            r=span_defl(ns,lc)
            v=r["rel"]*sign
            if best is None or v>best[0]: best=(v,dict(r,span=lab,lc=str(lc)))
    return best[1]
def worst_abs(spans,lcs,sign=-1):
    best=None
    for lab,ns in spans:
        for lc in lcs:
            r=span_defl(ns,lc); v=(r["uz_abs_min"] if sign<0 else max(uz(lc,n) for n in ns))*sign
            if best is None or v>best[0]: best=(v,dict(r,span=lab,lc=str(lc),abs_ext=round(v*sign,2)))
    return best[1]
# ---- (a) L1 ring spans between column (group 11) nodes at 40 deg
ring=sorted([n for n in xyz if abs(xyz[n][2]-4.054)<0.01 and 11.95<pol(n)[0]<12.05],key=lambda n:pol(n)[1])
col=[n for n in ring if any(eg(b)==11 for b in node_beams[n])]
def ring_spans(ring,col):
    sp=[]; idx=[ring.index(c) for c in col]
    for k in range(len(idx)):
        i,j=idx[k],idx[(k+1)%len(idx)]
        ns=ring[i:j+1] if j>i else ring[i:]+ring[:j+1]
        sp.append(("%.0f-%.0f"%(pol(ns[0])[1],pol(ns[-1])[1]),ns))
    return sp
RS=ring_spans(ring,col)
out["a_ring_nodes_per_span"]={l:len(n) for l,n in RS}
out["a_201"]=worst(RS,[201]); out["a_GQpsiW"]=worst(RS,GQW); out["a_SLS_all"]=worst(RS,SLS); out["a_LC11"]=worst(RS,[11])
# ---- radial chains
def radial_chains(group, z0):
    ch=collections.defaultdict(set)
    for b,v in beams.items():
        if eg(b)!=group: continue
        a,c=v["nodes"]; ra,ta,_=pol(a); rc,tc,_=pol(c)
        dt=abs((ta-tc+180)%360-180)
        if abs(ra-rc)>0.05 and (dt<0.3 or min(ra,rc)<0.05):
            th=round(ta if ra>rc else tc)%360
            ch[th].update([a,c])
    return {th:sorted(ns,key=lambda n:pol(n)[0]) for th,ns in ch.items()}
def supports_on(ns, groups):
    return [n for n in ns if any(eg(b) in groups for b in node_beams[n])]
COLG={11,12,13,14,21,23,24,31,61}
L2R=radial_chains(25,8.055)
out["b_radial_angles"]=sorted(L2R)
out["b_radial_r"]={th:[round(pol(ns[0])[0],2),round(pol(ns[-1])[0],2),len(ns),[round(pol(n)[0],2) for n in supports_on(ns,COLG)]] for th,ns in sorted(L2R.items())}
L2S=[(str(th),ns) for th,ns in L2R.items() if pol(ns[-1])[0]>11.9]
out["b_201"]=worst(L2S,[201]); out["b_Q"]=worst(L2S,[(11,12,13)]); out["b_Q13"]=worst(L2S,[13]); out["b_abs201"]=worst_abs(L2S,[201]); out["b_absQ"]=worst_abs(L2S,[(11,12,13)])
RFR=radial_chains(35,12.056)
out["c_radial_r"]={th:[round(pol(ns[0])[0],2),round(pol(ns[-1])[0],2),len(ns),[round(pol(n)[0],2) for n in supports_on(ns,COLG)]] for th,ns in sorted(RFR.items())}
RFS=[(str(th),ns) for th,ns in RFR.items() if pol(ns[-1])[0]>11.9]
out["c_201"]=worst(RFS,[201]); out["c_Q12"]=worst(RFS,[12]); out["c_up_GW"]=worst(RFS,GW,+1); out["c_abs201"]=worst_abs(RFS,[201]); out["c_absQ12"]=worst_abs(RFS,[12]); out["c_absup"]=worst_abs(RFS,GW,+1); out["c_up_206_209"]=worst(RFS,list(range(206,210)),+1)
# ---- (d) horizontal max per level over SLS
for lvl,z0 in (("L1",4.054),("L2",8.055),("RF",12.056)):
    gg={"L1":15,"L2":25,"RF":35}[lvl]; ns=sorted({n for b in beams if eg(b)==gg for n in beams[b]["nodes"]})
    best=None
    for lc in SLS:
        for n in ns:
            r=U(lc).get(n)
            if r is None: continue
            h=math.hypot(r["ux"],r["uy"])
            if best is None or h>best[0]: best=(h,n,lc,r["ux"],r["uy"])
    out["d_"+lvl]=dict(uh=round(best[0],2),node=best[1],lc=best[2],ux=best[3],uy=best[4],r_theta=[round(v,2) for v in pol(best[1])[:2]],nnodes=len(ns))
# ---- (e) L1 radials 280 and 40
L1R=radial_chains(15,4.054)
out["e_L1_radial_angles"]=sorted(L1R)
for th in (280,40):
    ns=L1R[th]; sup=supports_on(ns,{11,12,13,14,21})
    posts=[n for n in ns if any(eg(b)==61 for b in node_beams[n])]
    out["e_%d_info"%th]=dict(r_range=[round(pol(ns[0])[0],2),round(pol(ns[-1])[0],2)],supports_r=[round(pol(n)[0],3) for n in sup],posts_r=[round(pol(n)[0],3) for n in posts],slns=sorted({beams[b]["sln"] for n in ns for b in node_beams[n] if eg(b)==15 and beams[b]["sln"] is not None})[:20])
    spans=[]
    for i in range(len(sup)-1):
        a,b_=ns.index(sup[i]),ns.index(sup[i+1]); spans.append(("r%.2f-%.2f"%(pol(sup[i])[0],pol(sup[i+1])[0]),ns[a:b_+1]))
    out["e_%d_201_spans"%th]=[dict(span_defl(s,201),span=l) for l,s in spans]
# ---- (f) internal stair stringers: group 60 sno5 inclined SLN
str_sln=collections.defaultdict(list)
for b,v in beams.items():
    if eg(b)==60 and bsno.get(b)==5:
        a,c=v["nodes"]
        if abs(xyz[a][2]-xyz[c][2])>0.05: str_sln[v["sln"]].append(b)
def chain_nodes(bl):
    cnt=collections.Counter(n for b in bl for n in beams[b]["nodes"])
    ends=[n for n,c in cnt.items() if c==1]
    if len(ends)!=2: return None
    n=min(ends,key=lambda n:xyz[n][2]); seq=[n]; left=set(bl)
    while left:
        nx=[b for b in left if n in beams[b]["nodes"]]
        if not nx: break
        b=nx[0]; left.discard(b); a,c=beams[b]["nodes"]; n=c if a==n else a; seq.append(n)
    return seq
allb=[b for bl in str_sln.values() for b in bl]
def dvec(b):
    a,c=beams[b]["nodes"]; p,q=xyz[a],xyz[c]; v=[q[i]-p[i] for i in range(3)]; L=math.sqrt(sum(x*x for x in v)); v=[x/L for x in v]
    return v if v[2]>0 else [-x for x in v]
par={b:b for b in allb}
def f(b):
    while par[b]!=b: b=par[b]
    return b
nb=collections.defaultdict(list)
for b in allb:
    for n in beams[b]["nodes"]: nb[n].append(b)
for n,bl in nb.items():
    for i in range(len(bl)):
        for j in range(i+1,len(bl)):
            u,v=dvec(bl[i]),dvec(bl[j])
            if sum(x*y for x,y in zip(u,v))>0.999: par[f(bl[i])]=f(bl[j])
grp=collections.defaultdict(list)
for b in allb: grp[f(b)].append(b)
str_sln={min(beams[b]["sln"] or 0 for b in bl):bl for bl in grp.values()}
fres=[]
for s,bl in str_sln.items():
    seq=chain_nodes(bl)
    if not seq: fres.append(dict(sln=s,err="not a chain",n=len(bl))); continue
    for lc in (201,):
        r=span_defl(seq,lc)
        # perpendicular component approx: rel*cos(slope)
        p0,p1=xyz[seq[0]],xyz[seq[-1]]; hz=math.hypot(p1[0]-p0[0],p1[1]-p0[1]); slope=math.degrees(math.atan2(p1[2]-p0[2],hz))
        fres.append(dict(r,sln=s,slope_deg=round(slope,1),z=[round(p0[2],2),round(p1[2],2)],perp=round(r["rel"]*math.cos(math.radians(slope)),2)))
out["f_stringers_201"]=sorted(fres,key=lambda r:r.get("rel",0))
fq=[]
for s,bl in str_sln.items():
    seq=chain_nodes(bl)
    if seq:
        best=max((dict(span_defl(seq,lc),lc=lc) for lc in SLS),key=lambda r:-r["rel"])
        fq.append(dict(best,sln=s))
out["f_stringers_SLSenv_worst"]=min(fq,key=lambda r:r["rel"])
json.dump(out,open("partA2.json","w"),indent=1,default=str)
print(json.dumps(out,indent=1,default=str))
