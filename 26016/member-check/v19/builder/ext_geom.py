"""External stair (ground -> L1) geometry in model axes, from Wing's DXF (rotated +20 deg; see make_v17.py header).
Returns nodes and member lines. Everything in m."""
import numpy as np, json, os
HERE=os.path.dirname(os.path.abspath(__file__))
ZG=0.0; ZF=0.64; Z1=2.43; Z1F2=2.64; Z2=4.43; ZRING=4.054
# L1 r12 ring chords (exact model coordinates)
RING={'0-20':((11.9999962,0.0),(11.2763083,4.10423978)),'20-40':((11.2763083,4.10423978),(9.19253118,7.71344854)),
      '300-320':((5.9999969,-10.392302),(9.19252957,-7.71344962)),'280-300':((2.08377602,-11.8176894),(5.9999969,-10.392302))}
def proj(p,seg):
    a,b=map(np.array,seg); p=np.array(p[:2]); t=np.dot(p-a,b-a)/np.dot(b-a,b-a); return a+t*(b-a)
P=lambda x,y,z: np.array([x,y,z],float)
ARMS={
 'R':dict(title='external stair, right arm (to L1 at 20 deg)',
   foot_i=P(11.68,-2.48,ZF), foot_o=P(13.73,-2.84,ZF),
   C1=P(12.09,-0.06,Z1), C2=P(14.14,-0.39,Z1), C3=P(14.04,1.02,Z1), C4=P(11.99,0.66,Z1),
   S_lo=np.r_[proj((11.47,3.10),RING['0-20']),Z2], D2=P(13.59,3.53,Z2), D3=P(13.25,5.42,Z2),
   S_hi=np.r_[proj((10.71,5.01),RING['20-40']),Z2], K=P(11.31,4.01,Z2), M=P(13.39,4.41,Z2),
   ring_lo='0-20 (SLN 161)', ring_hi='20-40 (SLN 170)'),
 'L':dict(title='external stair, left arm (to L1 at 300 deg)',
   foot_i=P(10.55,-5.61,ZF), foot_o=P(12.36,-6.65,ZF),
   C1=P(9.32,-7.74,Z1), C2=P(11.11,-8.78,Z1), C3=P(10.14,-9.82,Z1), C4=P(8.79,-8.23,Z1),
   S_lo=np.r_[proj((6.83,-9.78),RING['300-320']),Z2], D2=P(8.19,-11.46,Z2), D3=P(6.74,-12.73,Z2),
   S_hi=np.r_[proj((5.02,-10.76),RING['280-300']),Z2], K=P(6.13,-10.37,Z2), M=P(7.47,-12.01,Z2),
   ring_lo='300-320 (SLN 164)', ring_hi='280-300 (SLN 165)'),
}
def treads():
    cl=json.load(open(os.path.join(HERE,'cl.json')))
    T={'R1':[],'R2':[],'L1':[],'L2':[]}
    for o in cl:
        p=o['path']
        if 'Thread' not in p or 'GF' not in p or o['L']<1.5: continue
        k=('L' if '$1$ATF' in p else 'R')+('1' if 'btm' in p else '2')
        T[k].append((np.array(o['a']),np.array(o['b'])))
    for k in T: T[k].sort(key=lambda ab: ab[0][2])
    return T
def on_line(p,a,b):
    """point of line a-b nearest to p (3D)"""
    t=np.dot(p-a,b-a)/np.dot(b-a,b-a); return a+t*(b-a)
def build():
    """lines: list of dict(kind, a, b, sno, title, rail(bool), rel)"""
    T=treads(); lines=[]; supports=[]; lars=[]; flights=[]
    def add(kind,a,b,sno,title,**kw): lines.append(dict(kind=kind,a=np.array(a,float),b=np.array(b,float),sno=sno,title=title,**kw)); return len(lines)-1
    for arm,g in ARMS.items():
        side={'R':'right','L':'left'}[arm]
        C1,C2,C3,C4=g['C1'],g['C2'],g['C3'],g['C4']
        C3u=C3+[0,0,Z1F2-Z1]; C4u=C4+[0,0,Z1F2-Z1]
        # flight 1 (ground -> landing 1): feet pinned on the start platform
        fi=add('stringer',g['foot_i'],C1,5,f'{side} flight 1 inner stringer',rail=True,flight=arm+'1')
        fo=add('stringer',g['foot_o'],C2,5,f'{side} flight 1 outer stringer',rail=True,flight=arm+'1')
        supports+= [(g['foot_i'],f'{side} flight 1 inner foot'),(g['foot_o'],f'{side} flight 1 outer foot')]
        # landing 1 frame + 4 legs to the ground
        add('landing',C1,C2,5,f'{side} landing 1 edge at flight 1')
        add('landing',C2,C3,5,f'{side} landing 1 outer edge',rail=True)
        add('landing',C3,C4,5,f'{side} landing 1 edge at flight 2')
        add('landing',C4,C1,5,f'{side} landing 1 inner edge',rail=True)
        for c,nm in ((C1,'inner-low'),(C2,'outer-low'),(C3,'outer-high'),(C4,'inner-high')):
            add('leg',c,np.r_[c[:2],ZG],8,f'{side} landing 1 leg {nm}'); supports.append((np.r_[c[:2],ZG],f'{side} landing 1 leg {nm} base'))
        add('stub',C4,C4u,5,f'{side} flight 2 inner stringer seat'); add('stub',C3,C3u,5,f'{side} flight 2 outer stringer seat')
        # flight 2 (landing 1 -> landing 2 at L1)
        si=add('stringer',C4u,g['S_lo'],5,f'{side} flight 2 inner stringer',rail=True,flight=arm+'2')
        so=add('stringer',C3u,g['D2'],5,f'{side} flight 2 outer stringer',rail=True,flight=arm+'2')
        flights+= [(fi,fo),(si,so)]
        # landing 2 at L1 level
        S_lo,S_hi,K,M,D2,D3=g['S_lo'],g['S_hi'],g['K'],g['M'],g['D2'],g['D3']
        add('landing',S_lo,D2,5,f'{side} landing 2 edge at flight 2')
        add('landing',D2,M,5,f'{side} landing 2 outer edge (a)',rail=True)
        add('landing',M,D3,5,f'{side} landing 2 outer edge (b)',rail=True)
        add('landing',D3,S_hi,5,f'{side} landing 2 far edge',rail=True)
        add('landing',S_hi,K,5,f'{side} landing 2 inner edge (b), along the ring')
        add('landing',K,S_lo,5,f'{side} landing 2 inner edge (a), along the ring')
        add('landing',M,K,5,f'{side} landing 2 middle beam')
        for c,nm in ((D2,'outer-low'),(D3,'outer-high')):
            add('leg',c,np.r_[c[:2],ZG],8,f'{side} landing 2 leg {nm}'); supports.append((np.r_[c[:2],ZG],f'{side} landing 2 leg {nm} base'))
        add('bracket',S_lo,np.r_[S_lo[:2],ZRING],8,f'{side} landing 2 support on L1 ring {g["ring_lo"]}',rel='MYMZ')
        add('bracket',S_hi,np.r_[S_hi[:2],ZRING],8,f'{side} landing 2 support on L1 ring {g["ring_hi"]}',rel='MYMZ')
        # treads on the stringer axes
        for fl,(i,o) in ((arm+'1',(fi,fo)),(arm+'2',(si,so))):
            ai,bi=lines[i]['a'],lines[i]['b']; ao,bo=lines[o]['a'],lines[o]['b']
            for a,b in T[fl]:
                pa,pb=(a,b) if np.linalg.norm(a[:2]-ai[:2])<np.linalg.norm(b[:2]-ai[:2]) else (b,a)
                add('tread',on_line(pa,ai,bi),on_line(pb,ao,bo),7,f'{side} flight {fl[1]} tread')
        lars+= [(f'{side} landing 1',[C1,C2,C3,C4]),(f'{side} landing 2 (a)',[S_lo,D2,M,K]),(f'{side} landing 2 (b)',[K,M,D3,S_hi])]
    return lines,supports,lars,flights
if __name__=='__main__':
    L,S,A,F=build()
    import collections; print(collections.Counter(l['kind'] for l in L), len(S), len(A))
    for l in L:
        if l['kind']!='tread': print(l['kind'],l['title'],l['a'].round(3),l['b'].round(3),round(float(np.linalg.norm(l['b']-l['a'])),3))
