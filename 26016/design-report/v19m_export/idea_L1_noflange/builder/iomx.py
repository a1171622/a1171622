import xml.etree.ElementTree as ET, re
XSI = '{http://www.w3.org/2001/XMLSchema-instance}type'
def load(path):
    b = open(path, 'rb').read(); t = b.decode('utf-16')
    return ET.ElementTree(ET.fromstring(t.encode('utf-8').replace(b'encoding="utf-16"', b'encoding="utf-8"', 1)))
def L(e): return e.tag.split('}')[-1]
def find(e, name): return [x for x in e.iter() if L(x) == name]
def info(tree):
    r = tree.getroot()
    pts = {}
    for p in find(r, 'Point3D'):
        if p.find('Id') is not None and p.find('X') is not None:
            pts[int(p.find('Id').text)] = tuple(float(p.find(k).text) for k in 'XYZ')
    segs = {}
    for s in find(r, 'Segment3D'):
        if s.find('Id') is None: continue
        bp = s.find('BeginNode/Id'); ep = s.find('EndNode/Id')
        segs[int(s.find('Id').text)] = (int(bp.text), int(ep.text)) if bp is not None else None
    els = {}
    for e in find(r, 'Element1D'):
        if e.find('Id') is None or e.find('Segment') is None: continue
        els[int(e.find('Id').text)] = dict(name=e.findtext('Name'), seg=int(e.find('Segment/Id').text),
                                          css=e.findtext('CrossSectionBegin/Id'))
    mems = {}
    for m in find(r, 'Member1D'):
        if m.find('Id') is None or m.find('Name') is None: continue
        mems[int(m.find('Id').text)] = dict(name=m.findtext('Name'), els=[int(x.findtext('Id')) for x in m.find('Elements1D')])
    lcs = {}
    for lc in find(r, 'LoadCase'):
        if lc.find('Name') is not None: lcs[int(lc.find('Id').text)] = (lc.findtext('Name'), lc.findtext('Description'))
    return pts, segs, els, mems, lcs
