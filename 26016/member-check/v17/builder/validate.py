import re,sys,numpy as np
sys.path.insert(0,'.')
from parse import parse_sln; from stairwind import stair_wind
L=open('/mnt/project-files/26016/member-check/run/v16/26016_check_v16.dat').read().split('\n')
sln=parse_sln(L,4223)
S={n:(v['segs'][0][0],v['segs'][-1][1],v['sno']) for n,v in sln.items() if v['grp']==60}
drag=[n for n,(a,b,s) in S.items() if s in (5,6)]
i3=L.index("LC 3 TYPE 'G' TITL 'SDL stairs handrail'")
bal=[]
for l in L[i3+1:]:
    m=re.match(r"\s+LINE SLN '(\d+)'",l)
    if m: bal.append(int(m[1]))
    elif l.strip().startswith('IF') or not l.strip(): break
flights=[136,137,79,90,489,490,461,472]
out=stair_wind(S,drag,bal,flights,[601,602,603,604],{5:('#CF5','#D5'),6:('#CF6','#D6')})
for lc,lines in out.items():
    i=L.index(lines[0]); j=i+1
    while L[j].strip(): j+=1
    old=L[i:j]
    print(lc, old==lines, len(old), len(lines))
    if old!=lines:
        import difflib; print('\n'.join(list(difflib.unified_diff(old,lines,lineterm=''))[:20]))
