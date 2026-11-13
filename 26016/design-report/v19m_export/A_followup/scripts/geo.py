import pickle, bisect, math, re, collections
M=pickle.load(open("model.pkl","rb")); xyz,beams,G=M["xyz"],M["beams"],M["G"]
starts=[s for s,_ in G]; eg=lambda nr: G[bisect.bisect_right(starts,nr)-1][1]
DAT=r"C:\Sofistik workflow\26016-member-check\v19m\26016_check_v19m.dat"
lines=open(DAT,encoding="latin-1").read().splitlines()
SL={}
for l in lines:
    m=re.match(r"SLN\s+(\d+)\s",l)
    if m:
        g=re.search(r"GRP\s+(\d+)",l); s=re.search(r"SNO\s+(\d+)",l); t=re.search(r'TITL\s+"([^"]*)"',l)
        SL[int(m[1])]=dict(grp=int(g[1]) if g else None,sno=int(s[1]) if s else None,title=t[1] if t else "")
def pol(n):
    x,y,z=xyz[n]; return math.hypot(x,y), math.degrees(math.atan2(y,x))%360, z
node_beams=collections.defaultdict(list)
for b,v in beams.items():
    for n in v["nodes"]: node_beams[n].append(b)
def sln_of(b): return beams[b]["sln"]
def sno_of(b):
    s=SL.get(sln_of(b)); return s["sno"] if s else None
