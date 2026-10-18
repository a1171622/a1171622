import collections,sys
exec(open('/mnt/project-files/26016/audit/generator/geo.py').read())
# areas cm2 from SCI Blue Book (hot-finished) / geometry; INFERRED tables
A={'1':54.9,'2':54.8,'3':371.0,'4':114.0,'5':117.0,'6':8.49,'7':20.0}
Ls=collections.defaultdict(float); n=collections.Counter()
for k,v in sln.items():
    s=v['sno']; 
    if s is None: continue
    Ls[s]+=v['len']; n[s]+=1
tot=0
for s in sorted(Ls):
    w=A.get(s,0)*1e-4*Ls[s]*78.5; tot+=w
    print(s,n[s],'L=%.1f m'%Ls[s],'W=%.1f kN'%w)
print('beam total %.1f kN'%tot)
