import numpy as np, collections
exec(open('/mnt/project-files/26016/audit/generator/gen_unified.py').read())
P=pset('default')
B=sorted({s for c in COMBOS for s in combo_records(c,P)[1]})
vec={b:lc_records(b,P) for b in B}
keys=sorted({k for v in vec.values() for k in v})
ki={k:i for i,k in enumerate(keys)}
M=np.zeros((len(keys),len(B)))
for j,b in enumerate(B):
    for k,v in vec[b].items(): M[ki[k],j]=v
print('basic LCs',len(B),'DOFs',len(keys),'rank',np.linalg.matrix_rank(M))
def intended(c):
    out=collections.defaultdict(float)
    no,typ,facd,title,parts,ehf,eg,eq=c
    for g,expr in parts:
        for s in (GROUPS[g] if isinstance(g,str) else [g]): out[s]+=ev(expr,P)
    if ehf is not None and P['EHF']>0:
        out[501+ehf]+=ev(eg,P)
        if eq: out[505+ehf]+=ev(eq,P)
    return out
def recover(recs):
    y=np.zeros(len(keys))
    for k,v in recs.items(): y[ki[k]]=v
    x,res,rk,_=np.linalg.lstsq(M,y,rcond=None)
    return {b:x[j] for j,b in enumerate(B) if abs(x[j])>1e-6}, np.linalg.norm(M@x-y)/max(np.linalg.norm(y),1e-12)
worst=0
for c in COMBOS:
    rec,_,_=combo_records(c,P); x,r=recover(rec); I=intended(c)
    d=max(abs(x.get(b,0)-I.get(b,0)) for b in set(x)|set(I)); worst=max(worst,d)
print('clean: max factor error over',len(COMBOS),'combos = %.2e'%worst)
# mutations
C={c[0]:c for c in COMBOS}
rec,_,_=combo_records(C[102],P); rec=collections.defaultdict(float,rec)
for k,v in lc_records(2,P).items(): rec[k]+=1.35*v      # SDL counted twice
x,r=recover(rec); print('M1 SDL twice in 102 -> LC2 factor %.3f (intended 1.35)'%x[2])
rec,_,_=combo_records(C[103],P); rec=collections.defaultdict(float,rec)
for k,v in lc_records(81,P).items(): rec[k]+=0.75*v     # lateral wind twice
x,r=recover(rec); print('M2 103 + extra LC81 -> LC21 %.3f LC81 %.3f'%(x.get(21,0),x.get(81,0)))
rec,_,_=combo_records(C[103],P); rec={k:v*1.0 for k,v in rec.items()}
for k,v in lc_records(21,P).items(): rec[k]+= (0.9-0.75)*v
for k,v in lc_records(25,P).items(): rec[k]+= (0.9-0.75)*v
x,r=recover(rec); print('M3 103 with psi0 0.6 instead of 0.5 -> LC21 %.3f (intended 0.75)'%x[21])
print('--- forward check: ||combo - sum(intended f * basic)|| / ||combo||')
def fwd(rec,c):
    y=np.zeros(len(keys))
    for k,v in rec.items(): y[ki[k]]+=v
    I=intended(c); p=np.zeros(len(keys))
    for b,f in I.items():
        for k,v in vec[b].items(): p[ki[k]]+=f*v
    return np.linalg.norm(y-p)/np.linalg.norm(y)
print('clean max residual: %.2e'%max(fwd(combo_records(c,P)[0],c) for c in COMBOS))
for name,cn,add in (('M1 LC2 twice',102,[(2,1.35)]),('M2 extra LC81',103,[(81,0.75)]),('M3 psiW 0.6',103,[(21,0.15),(25,0.15)]),('M4 LC17 twice',102,[(17,1.5)]),('M5 drop LC14',102,[(14,-1.5)])):
    rec=collections.defaultdict(float,combo_records(C[cn],P)[0])
    for b,f in add:
        for k,v in lc_records(b,P).items(): rec[k]+=f*v
    print(name,'residual %.3f'%fwd(rec,C[cn]))
# aliases
u,s,vt=np.linalg.svd(M,full_matrices=True)
null=vt[np.sum(s>1e-8*s[0]):]
for z in null[:12]:
    idx=np.argsort(-abs(z))[:4]; print('alias:',[(B[i],round(z[i],2)) for i in idx if abs(z[i])>0.05])
