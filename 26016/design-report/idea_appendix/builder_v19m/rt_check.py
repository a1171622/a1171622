import sys, glob, os, json
sys.path.insert(0, '.')
from iomx import load
from calib import geom
rt = sys.argv[1]; T = r"C:\Sofistik workflow\idea-statica\v15"
def cmp(newf, tf):
    _, _, l1, r1 = geom(load(newf)); _, _, l0, r0 = geom(load(tf))
    n1 = {v: k for k, v in l1.items()}; worst = (0, None)
    for (e, k), v in r0.items():
        k1 = n1[l0[k]]
        for c in v:
            d = abs(v[c] - r1[(e, k1)][c]) / 1000
            if d > worst[0]: worst = (round(d, 3), (e, l0[k], c))
    return worst
for sub, tsub in (('xml_L2haunch_flush_M20', 'xml_L2haunch_flush_asis\\part*'), ('xml_strut_10deg_v15tr', 'xml_strut_10deg_asis'), ('d\\xml_strut_10deg', 'xml_strut_10deg_asis')):
    for f in sorted(glob.glob(os.path.join(rt, sub, '*.xml'))):
        tf = glob.glob(os.path.join(T, tsub, os.path.basename(f)))
        if not tf: print(sub, os.path.basename(f), 'no same-name template (rotated layout)'); continue
        print(sub, os.path.basename(f), 'max |diff| kN/kNm', cmp(f, tf[0]))
