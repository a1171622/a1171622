import re,sys
OPS=('DIV','SIN','COS','SQR','TAN','EXP','LOG','ABS','MOD','ATN','POW')   # CADINP function words (DIV/SIN/COS/SQR per memory; rest inferred)
def lint(text):
    F=[]; L=text.split('\n'); defined=set(); copies=[]; prog=None; lcdef=set()
    for i,raw in enumerate(L,1):
        l=raw.rstrip('\r')
        if len(l)>255: F.append((i,'S3 line > 255 chars'))
        code=re.split(r'\s\$|^\$|!',l)[0] if not l.lstrip().startswith(('$','!')) else ''
        m=re.match(r'\s*[+-]?PROG\s+(\w+)',code,re.I)
        if m: prog=m.group(1).upper(); continue
        for v in re.findall(r'(?:STO|LET|DEL)#(\w+)',code,re.I):
            if any(o in v.upper() for o in OPS): F.append((i,f'S4 variable name {v} contains an operator word'))
        # comma lists
        for grp in re.findall(r'(?:\b\w+\s+)((?:[-\d.#\w]+\s*,\s*){25,}[-\d.#\w]+)',code):
            F.append((i,'S5 comma list > 25 items')); break
        if re.match(r'\s*(SV|SVAL)\b',code,re.I):
            for k in ('IY','IZ','IT','IYZ'):
                mm=re.search(r'\b'+k+r'\s+([-\d.Ee+]+)(\[[^\]]+\])?',code)
                if mm and not mm.group(2): F.append((i,f'S6 {k} without explicit unit (default m4)'))
        if prog=='SOFILOAD':
            m=re.match(r'\s*LC\s+(\d+)',code)
            if m: lcdef.add(int(m.group(1)))
            m=re.match(r'\s*COPY\s+(?:NO\s+)?(\d+)',code)
            if m: copies.append((i,int(m.group(1))))
            m=re.match(r'\s*(AREA|LINE|BEAM|NODE|QUAD|POIN)\b.*?\bTYPE\s+\w+\s+(?:(?:P1|PA|P|PE)\s+)?(\S+)',code)
            if m and '#' not in m.group(2) and m.group(2) not in ('0','1','-1'):
                F.append((i,f'S1 hard-coded load value {m.group(2)}'))
    for i,n in copies:
        if n not in lcdef: F.append((i,f'S2 COPY of LC {n} not defined in SOFiLOAD'))
    return F
if __name__=='__main__':
    t=open(sys.argv[1],encoding='utf-8',errors='replace').read(); f=lint(t)
    print(sys.argv[1].split('/')[-1],len(f),'findings'); [print(' ',x) for x in f[:8]]
