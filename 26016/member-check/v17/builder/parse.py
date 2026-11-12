import re, numpy as np
def parse_sln(lines, end):
    sln={}; cur=None
    for i,l in enumerate(lines[:end]):
        m=re.match(r'SLN\s+(\d+)\s',l)
        if m:
            cur=int(m[1]); g=re.search(r'GRP\s+(\d+)',l); s=re.search(r'SNO\s+(\d+)',l)
            sln[cur]=dict(grp=int(g[1]) if g else None, sno=int(s[1]) if s else None, line=i, segs=[]); continue
        if l.startswith('SLNB') and cur is not None:
            m=re.search(r'X1\s+(\S+)\s+(\S+)\s+(\S+)\s+X2\s+(\S+)\s+(\S+)\s+(\S+)',l)
            a=list(map(float,m.groups())); sln[cur]['segs'].append((np.array(a[:3]),np.array(a[3:])))
            sln[cur].setdefault('blines',[]).append(i)
        elif l.startswith(('SPT','SAR','END','GRP')): cur=None
    return sln
