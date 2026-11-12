import numpy as np, math
def f6(x): return ('%.6g'%x)
def sexpr(base,c):
    if abs(c-1)<1e-12: return base
    if abs(c+1)<1e-12: return '-'+base
    return ('-' if c<0 else '')+base+'*'+f6(abs(c))
DIRS=[('+X',(1,0)),('-X',(-1,0)),('-Y',(0,-1)),('+Y',(0,1))]
ALPH=[0,5,10,15,20,25,30]; CFMAX=[0.2,0.4,0.5,0.7,0.8,1.0,1.2]; CFMIN=[-0.5,-0.7,-0.9,-1.1,-1.3,-1.6,-1.8]
def stair_wind(S, drag, bal, flights, landq, dep):
    """S: n->(A,B,sno); drag: members for drag; bal: balustrade lines; flights: stringer lines on inclined flights;
    landq: landing LAR numbers; dep: sno->(cf,depth) expression parts. Returns {lc: [lines]}"""
    out={}
    for i,(lab,u2) in enumerate(DIRS):
        wd=np.array([u2[0],u2[1],0.0]); L=[f"LC {25+i} TYPE '-' TITL 'WL{lab} stairs (block)'","  $ member drag"]
        comp,val=('PXX',wd[0]) if wd[0] else ('PYY',wd[1])
        for n in sorted(drag):
            A,B,sec=S[n]; e=(B-A)/np.linalg.norm(B-A); s2=1-np.dot(e,wd)**2
            if s2<1e-3: continue
            L.append(f"  LINE SLN '{n}' WIDE 0 TYPE {comp} "+sexpr(f'#Q*{dep[sec][0]}*{dep[sec][1]}',val*s2))
        L.append('  $ open balustrade, normal to its plane')
        for n in sorted(bal):
            A,B,_=S[n]; d=(B-A)[:2]; d=d/np.linalg.norm(d); nb=np.array([-d[1],d[0]]); k=float(np.dot(nb,wd[:2]))
            if abs(k)<0.03: continue
            fx,fy=k*nb[0],k*nb[1]
            if abs(fx)>=1e-4: L.append(f"  LINE SLN '{n}' WIDE 0 TYPE PXX "+sexpr('#Q*#CFL*#PHIB*#HBR',fx))
            if abs(fy)>=1e-4: L.append(f"  LINE SLN '{n}' WIDE 0 TYPE PYY "+sexpr('#Q*#CFL*#PHIB*#HBR',fy))
        L.append('  $ inclined flights as monopitch canopies (EN Table 7.6, phi 0): wind up the flight pushes down, down the flight lifts')
        L.append('  IF #VF>0')
        for n in flights:
            A,B,_=S[n]
            if B[2]<A[2]: A,B=B,A
            dv=B-A; uu=dv[:2]/np.linalg.norm(dv[:2]); al=math.atan2(dv[2],np.linalg.norm(dv[:2]))
            c=float(np.dot(uu,wd[:2]))
            if abs(c)<1e-6: continue
            ae=math.degrees(math.asin(min(1,math.sin(al)*abs(c)))); down=c>0
            cf=float(np.interp(min(ae,30.0),ALPH,CFMAX if down else CFMIN)); sgn=1 if down else -1
            comps=sgn*np.array([math.sin(al)*uu[0],math.sin(al)*uu[1],-math.cos(al)])*abs(cf)
            for cname,v in zip(('PXX','PYY','PZZ'),comps):
                if abs(v)>=1e-4: L.append(f"    LINE SLN '{n}' WIDE 0 TYPE {cname} "+sexpr('#Q*#BST/2',v))
        L.append('  ENDIF'); L.append('  IF #UPL>0')
        for n in landq: L.append(f"    AREA LAR '{n}' WIDE 0 TYPE PG -#Q")
        L.append('  ENDIF')
        out[25+i]=L
    return out
