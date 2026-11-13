import re, math, os
V = r'C:\Sofistik workflow\idea-statica'
def pts(path):
    t = open(path, 'rb').read().decode('utf-16')
    out = [(m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4))) for m in
           re.finditer(r'<(Point3D|Origin|Start|End)>(?:\s*<Id>[^<]*</Id>)?(?:\s*<Name>[^<]*</Name>)?\s*<X>([^<]*)</X>\s*<Y>([^<]*)</Y>\s*<Z>([^<]*)</Z>', t)]
    return t, out
for nsub, nf, tsub, tf in (('xml_B_noflange', 'L1-R8-B_040.xml', 'xml_B_noflange_asis', 'L1-R8-B_080.xml'),
                           ('xml_A_noflange', 'L1-R8-A_080.xml', 'xml_A_noflange_asis', 'L1-R8-A_120.xml')):
    t1, p1 = pts(os.path.join(V, 'v15', tsub, tf)); t2, p2 = pts(os.path.join(V, 'v19m', nsub, nf))
    a1, a2 = int(tf[-7:-4]), int(nf[-7:-4])
    c1 = (8.5 * math.cos(math.radians(a1)), 8.5 * math.sin(math.radians(a1))); c2 = (8.5 * math.cos(math.radians(a2)), 8.5 * math.sin(math.radians(a2)))
    d = max(abs(math.hypot(x1 - c1[0], y1 - c1[1]) - math.hypot(x2 - c2[0], y2 - c2[1])) + abs(z1 - z2) for (_, x1, y1, z1), (_, x2, y2, z2) in zip(p1, p2))
    print(nf, len(p1), len(p2), 'max change of distance to joint (m):', round(d, 6))
    print('  names:', sorted(set(re.findall(r'<Name>([^<]*(?:SLN|L1-R8)[^<]*)</Name>', t2))))
    print('  project:', re.search(r'<ProjectName>([^<]*)', t2).group(1))
print('--- detail B_040')
t1, p1 = pts(os.path.join(V, 'v15', 'xml_B_noflange_asis', 'L1-R8-B_080.xml')); t2, p2 = pts(os.path.join(V, 'v19m', 'xml_B_noflange', 'L1-R8-B_040.xml'))
c1 = (8.5 * math.cos(math.radians(80)), 8.5 * math.sin(math.radians(80))); c2 = (8.5 * math.cos(math.radians(40)), 8.5 * math.sin(math.radians(40)))
for (k, x1, y1, z1), (_, x2, y2, z2) in zip(p1, p2):
    d1 = math.hypot(x1 - c1[0], y1 - c1[1]); d2 = math.hypot(x2 - c2[0], y2 - c2[1])
    if abs(d1 - d2) > 1e-4: print(k, (round(x1, 3), round(y1, 3), round(z1, 3)), '->', (round(x2, 3), round(y2, 3), round(z2, 3)), round(d1, 3), round(d2, 3))
