"""Steel section property calculator and catalogue.

Public API (see CONTRACT.md "sections.py API"):

    from_name(name, fabrication=None) -> dict | None
    props_I(h, b, tw, tf, r, eta=1.0) -> dict
    props_RHS(h, b, t, ro=None, fabrication="hot_finished", ri=None) -> dict
    props_CHS(d, t) -> dict

Units: mm, mm², mm³, mm⁴, mm⁶, kg/m.  Axes: y = major (strong) axis, z = minor axis.

Formulas used (so that a checking engineer can trace every number):

Rolled I/H with root radius r (parallel flanges, 4 fillets):
    A      = 2 b tf + (h - 2 tf) tw + (4 - π) r²
    Iy, Iz = flanges + web + 4 fillets (exact second moment of the fillet "spandrel":
             square r×r minus a quarter circle of radius r, centroid 0.2234 r from the
             flange face / web face)
    Wel    = I / (extreme fibre distance);  Wpl = 2 × first moment of half section
    It     = 2/3 b tf³ + 1/3 (h - 2 tf) tw³ + 2 α1 D1⁴ - 0.420 tf⁴      (SCI P363 / El Darwish
             & Johnston approximation incl. fillets; this is the formula used for the BS 4-1
             tabulated values in the SCI "Blue Book")
             α1 = -0.042 + 0.2204 tw/tf + 0.1355 r/tf - 0.0865 r tw/tf² - 0.0725 tw²/tf²
             D1 = ((tf + r)² + tw (r + tw/4)) / (2 r + tf)
    Iw     = Iz (h - tf)² / 4
    Avz    = max(A - 2 b tf + (tw + 2 r) tf ,  η hw tw)    EN 1993-1-1 6.2.6(3)a, hw = h - 2 tf
             (props use η = 1.0, which is the conservative choice for the max(); the EC3 code
             module may recompute with η = 1.2 per EN 1993-1-5 recommended value)
    Avy    = 2 b tf      (flanges only, loads parallel to flanges; common practice, EC3 gives
             no explicit rolled-I expression for this direction)

RHS / SHS (EN 10210-2 hot finished: ro = 1.5 t, ri = 1.0 t;
           EN 10219-2 cold formed: ro = 2 t (t ≤ 6), 2.5 t (6 < t ≤ 10), 3 t (t > 10), ri = ro - t):
    A, I, Wpl from outer rounded rectangle minus inner rounded rectangle (exact for circular corners)
    It = t³ hp / 3 + 2 K Ah,   Wt = It / (t + K / t)              EN 10210-2 Annex B / EN 10219-2 Annex B
         hp = 2 ((b - t) + (h - t)) - 2 Rc (4 - π),  Ah = (b - t)(h - t) - Rc² (4 - π),
         K = 2 Ah t / hp,  Rc = (ro + ri) / 2
    Avz = A h / (b + h),  Avy = A b / (b + h)                     EN 1993-1-1 6.2.6(3)f
CHS:
    A = π (d² - di²)/4, I = π (d⁴ - di⁴)/64, Wpl = (d³ - di³)/6, It = 2 I, Wt = 2 Wel,
    Av = 2 A / π                                                  EN 1993-1-1 6.2.6(3)g

Steel density 7850 kg/m³ for mass.
"""
from __future__ import annotations

import math
import re
from typing import Optional

RHO = 7850e-9  # kg/mm³
_KGM = RHO * 1000.0  # kg/m per mm² of area (= 7.85e-3)

# ---------------------------------------------------------------------------------------------
# Sources of the tabulated dimensions
# ---------------------------------------------------------------------------------------------
SOURCES = {
    "UK_UB": "BS 4-1:2005 / EN 10365 dimensions as tabulated in SCI P363 'Steel building design: "
             "Design data' (Blue Book), UKB section range",
    "UK_UC": "BS 4-1:2005 / EN 10365 dimensions as tabulated in SCI P363 (Blue Book), UKC section range",
    "AU_UB": "AS/NZS 3679.1 rolled sections, dimensions as tabulated in the OneSteel/InfraBuild "
             "'Hot Rolled and Structural Steel Products' catalogue (UB range 150UB14.0 - 610UB125)",
    "AU_UC": "AS/NZS 3679.1 rolled sections, dimensions as tabulated in the OneSteel/InfraBuild "
             "'Hot Rolled and Structural Steel Products' catalogue (UC range 100UC14.8 - 310UC158)",
    "US_W": "ASTM A6 W shapes, dimensions (d, bf, tw, tf, k_des) from the AISC Shapes Database v15/v16; "
            "root radius r = k_des - tf",
    "HOLLOW_HF": "Dimensions from the section name; corner radii per EN 10210-2 (hot finished: "
                 "ro = 1.5 t, ri = 1.0 t)",
    "HOLLOW_CF": "Dimensions from the section name; corner radii per EN 10219-2 (cold formed)",
    "HSS": "AISC HSS (ASTM A500): design wall thickness t_des = 0.93 t_nom (AISC 360-22 B4.2), "
           "outside corner radius 2 t_des as used in the AISC Manual tables",
    "CHS": "Dimensions from the section name (EN 10210 / EN 10219 / AS 1163 circular hollow section)",
}

# ---------------------------------------------------------------------------------------------
# Catalogues: name -> (h, b, tw, tf, r) in mm
# ---------------------------------------------------------------------------------------------
# UK Universal Beams, BS 4-1 (SCI P363).  Key format "UB {serial}x{width}x{mass}".
UK_UB = {
    "UB 1016x305x487": (1036.3, 308.5, 30.0, 54.1, 30.0),
    "UB 1016x305x437": (1026.1, 305.4, 26.9, 49.0, 30.0),
    "UB 1016x305x393": (1015.9, 303.0, 24.4, 43.9, 30.0),
    "UB 1016x305x349": (1008.1, 302.0, 21.1, 40.0, 30.0),
    "UB 1016x305x314": (1000.0, 300.0, 19.1, 35.9, 30.0),
    "UB 1016x305x272": (990.1, 300.0, 16.5, 31.0, 30.0),
    "UB 1016x305x249": (980.1, 300.0, 16.5, 26.0, 30.0),
    "UB 1016x305x222": (970.3, 300.0, 16.0, 21.1, 30.0),
    "UB 914x419x388": (921.0, 420.5, 21.4, 36.6, 24.1),
    "UB 914x419x343": (911.8, 418.5, 19.4, 32.0, 24.1),
    "UB 914x305x289": (926.6, 307.7, 19.5, 32.0, 19.1),
    "UB 914x305x253": (918.4, 305.5, 17.3, 27.9, 19.1),
    "UB 914x305x224": (910.4, 304.1, 15.9, 23.9, 19.1),
    "UB 914x305x201": (903.0, 303.3, 15.1, 20.2, 19.1),
    "UB 838x292x226": (850.9, 293.8, 16.1, 26.8, 17.8),
    "UB 838x292x194": (840.7, 292.4, 14.7, 21.7, 17.8),
    "UB 838x292x176": (834.9, 291.7, 14.0, 18.8, 17.8),
    "UB 762x267x197": (769.8, 268.0, 15.6, 25.4, 16.5),
    "UB 762x267x173": (762.2, 266.7, 14.3, 21.6, 16.5),
    "UB 762x267x147": (754.0, 265.2, 12.8, 17.5, 16.5),
    "UB 762x267x134": (750.0, 264.4, 12.0, 15.5, 16.5),
    "UB 686x254x170": (692.9, 255.8, 14.5, 23.7, 15.2),
    "UB 686x254x152": (687.5, 254.5, 13.2, 21.0, 15.2),
    "UB 686x254x140": (683.5, 253.7, 12.4, 19.0, 15.2),
    "UB 686x254x125": (677.9, 253.0, 11.7, 16.2, 15.2),
    "UB 610x305x238": (635.8, 311.4, 18.4, 31.4, 16.5),
    "UB 610x305x179": (620.2, 307.1, 14.1, 23.6, 16.5),
    "UB 610x305x149": (612.4, 304.8, 11.8, 19.7, 16.5),
    "UB 610x229x140": (617.2, 230.2, 13.1, 22.1, 12.7),
    "UB 610x229x125": (612.2, 229.0, 11.9, 19.6, 12.7),
    "UB 610x229x113": (607.6, 228.2, 11.1, 17.3, 12.7),
    "UB 610x229x101": (602.6, 227.6, 10.5, 14.8, 12.7),
    "UB 610x178x100": (607.4, 179.2, 11.3, 17.2, 12.7),
    "UB 610x178x92": (603.0, 178.8, 10.9, 15.0, 12.7),
    "UB 610x178x82": (598.6, 177.9, 10.0, 12.8, 12.7),
    "UB 533x312x272": (577.1, 320.2, 21.1, 37.6, 12.7),
    "UB 533x312x219": (560.3, 317.4, 18.3, 29.2, 12.7),
    "UB 533x312x182": (550.7, 314.5, 15.2, 24.4, 12.7),
    "UB 533x312x150": (542.5, 312.0, 12.7, 20.3, 12.7),
    "UB 533x210x138": (549.1, 213.9, 14.7, 23.6, 12.7),
    "UB 533x210x122": (544.5, 211.9, 12.7, 21.3, 12.7),
    "UB 533x210x109": (539.5, 210.8, 11.6, 18.8, 12.7),
    "UB 533x210x101": (536.7, 210.0, 10.8, 17.4, 12.7),
    "UB 533x210x92": (533.1, 209.3, 10.1, 15.6, 12.7),
    "UB 533x210x82": (528.3, 208.8, 9.6, 13.2, 12.7),
    "UB 533x165x85": (534.9, 166.5, 10.3, 16.5, 12.7),
    "UB 533x165x75": (529.1, 165.9, 9.7, 13.6, 12.7),
    "UB 533x165x66": (524.7, 165.1, 8.9, 11.4, 12.7),
    "UB 457x191x161": (492.0, 199.4, 18.0, 32.0, 10.2),
    "UB 457x191x133": (480.6, 196.7, 15.3, 26.3, 10.2),
    "UB 457x191x106": (469.2, 194.0, 12.6, 20.6, 10.2),
    "UB 457x191x98": (467.2, 192.8, 11.4, 19.6, 10.2),
    "UB 457x191x89": (463.4, 191.9, 10.5, 17.7, 10.2),
    "UB 457x191x82": (460.0, 191.3, 9.9, 16.0, 10.2),
    "UB 457x191x74": (457.0, 190.4, 9.0, 14.5, 10.2),
    "UB 457x191x67": (453.4, 189.9, 8.5, 12.7, 10.2),
    "UB 457x152x82": (465.8, 155.3, 10.5, 18.9, 10.2),
    "UB 457x152x74": (462.0, 154.4, 9.6, 17.0, 10.2),
    "UB 457x152x67": (458.0, 153.8, 9.0, 15.0, 10.2),
    "UB 457x152x60": (454.6, 152.9, 8.1, 13.3, 10.2),
    "UB 457x152x52": (449.8, 152.4, 7.6, 10.9, 10.2),
    "UB 406x178x85": (417.2, 181.9, 10.9, 18.2, 10.2),
    "UB 406x178x74": (412.8, 179.5, 9.5, 16.0, 10.2),
    "UB 406x178x67": (409.4, 178.8, 8.8, 14.3, 10.2),
    "UB 406x178x60": (406.4, 177.9, 7.9, 12.8, 10.2),
    "UB 406x178x54": (402.6, 177.7, 7.7, 10.9, 10.2),
    "UB 406x140x53": (406.6, 143.3, 7.9, 12.9, 10.2),
    "UB 406x140x46": (403.2, 142.2, 6.8, 11.2, 10.2),
    "UB 406x140x39": (398.0, 141.8, 6.4, 8.6, 10.2),
    "UB 356x171x67": (363.4, 173.2, 9.1, 15.7, 10.2),
    "UB 356x171x57": (358.0, 172.2, 8.1, 13.0, 10.2),
    "UB 356x171x51": (355.0, 171.5, 7.4, 11.5, 10.2),
    "UB 356x171x45": (351.4, 171.1, 7.0, 9.7, 10.2),
    "UB 356x127x39": (353.4, 126.0, 6.6, 10.7, 10.2),
    "UB 356x127x33": (349.0, 125.4, 6.0, 8.5, 10.2),
    "UB 305x165x54": (310.4, 166.9, 7.9, 13.7, 8.9),
    "UB 305x165x46": (306.6, 165.7, 6.7, 11.8, 8.9),
    "UB 305x165x40": (303.4, 165.0, 6.0, 10.2, 8.9),
    "UB 305x127x48": (311.0, 125.3, 9.0, 14.0, 8.9),
    "UB 305x127x42": (307.2, 124.3, 8.0, 12.1, 8.9),
    "UB 305x127x37": (304.4, 123.4, 7.1, 10.7, 8.9),
    "UB 305x102x33": (312.7, 102.4, 6.6, 10.8, 7.6),
    "UB 305x102x28": (308.7, 101.8, 6.0, 8.8, 7.6),
    "UB 305x102x25": (305.1, 101.6, 5.8, 7.0, 7.6),
    "UB 254x146x43": (259.6, 147.3, 7.2, 12.7, 7.6),
    "UB 254x146x37": (256.0, 146.4, 6.3, 10.9, 7.6),
    "UB 254x146x31": (251.4, 146.1, 6.0, 8.6, 7.6),
    "UB 254x102x28": (260.4, 102.2, 6.3, 10.0, 7.6),
    "UB 254x102x25": (257.2, 101.9, 6.0, 8.4, 7.6),
    "UB 254x102x22": (254.0, 101.6, 5.7, 6.8, 7.6),
    "UB 203x133x30": (206.8, 133.9, 6.4, 9.6, 7.6),
    "UB 203x133x25": (203.2, 133.2, 5.7, 7.8, 7.6),
    "UB 203x102x23": (203.2, 101.8, 5.4, 9.3, 7.6),
    "UB 178x102x19": (177.8, 101.2, 4.8, 7.9, 7.6),
    "UB 152x89x16": (152.4, 88.7, 4.5, 7.7, 7.6),
    "UB 127x76x13": (127.0, 76.0, 4.0, 7.6, 7.6),
}

# UK Universal Columns, BS 4-1 (SCI P363).
UK_UC = {
    "UC 356x406x634": (474.6, 424.0, 47.6, 77.0, 15.2),
    "UC 356x406x551": (455.6, 418.5, 42.1, 67.5, 15.2),
    "UC 356x406x467": (436.6, 412.2, 35.8, 58.0, 15.2),
    "UC 356x406x393": (419.0, 407.0, 30.6, 49.2, 15.2),
    "UC 356x406x340": (406.4, 403.0, 26.6, 42.9, 15.2),
    "UC 356x406x287": (393.6, 399.0, 22.6, 36.5, 15.2),
    "UC 356x406x235": (381.0, 394.8, 18.4, 30.2, 15.2),
    "UC 356x368x202": (374.6, 374.7, 16.5, 27.0, 15.2),
    "UC 356x368x177": (368.2, 372.6, 14.4, 23.8, 15.2),
    "UC 356x368x153": (362.0, 370.5, 12.3, 20.7, 15.2),
    "UC 356x368x129": (355.6, 368.6, 10.4, 17.5, 15.2),
    "UC 305x305x283": (365.3, 322.2, 26.8, 44.1, 15.2),
    "UC 305x305x240": (352.5, 318.4, 23.0, 37.7, 15.2),
    "UC 305x305x198": (339.9, 314.5, 19.1, 31.4, 15.2),
    "UC 305x305x158": (327.1, 311.2, 15.8, 25.0, 15.2),
    "UC 305x305x137": (320.5, 309.2, 13.8, 21.7, 15.2),
    "UC 305x305x118": (314.5, 307.4, 12.0, 18.7, 15.2),
    "UC 305x305x97": (307.9, 305.3, 9.9, 15.4, 15.2),
    "UC 254x254x167": (289.1, 265.2, 19.2, 31.7, 12.7),
    "UC 254x254x132": (276.3, 261.3, 15.3, 25.3, 12.7),
    "UC 254x254x107": (266.7, 258.8, 12.8, 20.5, 12.7),
    "UC 254x254x89": (260.3, 256.3, 10.3, 17.3, 12.7),
    "UC 254x254x73": (254.1, 254.6, 8.6, 14.2, 12.7),
    "UC 203x203x127": (241.4, 213.9, 18.1, 30.1, 10.2),
    "UC 203x203x113": (235.0, 212.1, 16.3, 26.9, 10.2),
    "UC 203x203x100": (228.6, 210.3, 14.5, 23.7, 10.2),
    "UC 203x203x86": (222.2, 209.1, 12.7, 20.5, 10.2),
    "UC 203x203x71": (215.8, 206.4, 10.0, 17.3, 10.2),
    "UC 203x203x60": (209.6, 205.8, 9.4, 14.2, 10.2),
    "UC 203x203x52": (206.2, 204.3, 7.9, 12.5, 10.2),
    "UC 203x203x46": (203.2, 203.6, 7.2, 11.0, 10.2),
    "UC 152x152x51": (170.2, 157.4, 11.0, 15.7, 7.6),
    "UC 152x152x44": (166.0, 155.9, 9.5, 13.6, 7.6),
    "UC 152x152x37": (161.8, 154.4, 8.0, 11.5, 7.6),
    "UC 152x152x30": (157.6, 152.9, 6.5, 9.4, 7.6),
    "UC 152x152x23": (152.4, 152.2, 5.8, 6.8, 7.6),
}

# Australian UB / UC, AS/NZS 3679.1 (OneSteel/InfraBuild catalogue).  (d, bf, tw, tf, r1)
AU_UB = {
    "150UB14.0": (150.0, 75.0, 5.0, 7.0, 8.0),
    "150UB18.0": (155.0, 75.0, 6.0, 9.5, 8.0),
    "180UB16.1": (173.0, 90.0, 4.5, 7.0, 8.9),
    "180UB18.1": (175.0, 90.0, 5.0, 8.0, 8.9),
    "180UB22.2": (179.0, 90.0, 6.0, 10.0, 8.9),
    "200UB18.2": (198.0, 99.0, 4.5, 7.0, 11.0),
    "200UB22.3": (202.0, 133.0, 5.0, 7.0, 8.9),
    "200UB25.4": (203.0, 133.0, 5.8, 7.8, 8.9),
    "200UB29.8": (207.0, 134.0, 6.3, 9.6, 8.9),
    "250UB25.7": (248.0, 124.0, 5.0, 8.0, 12.0),
    "250UB31.4": (252.0, 146.0, 6.1, 8.6, 8.9),
    "250UB37.3": (256.0, 146.0, 6.4, 10.9, 8.9),
    "310UB32.0": (298.0, 149.0, 5.5, 8.0, 13.0),
    "310UB40.4": (304.0, 165.0, 6.1, 10.2, 11.4),
    "310UB46.2": (307.0, 166.0, 6.7, 11.8, 11.4),
    "360UB44.7": (352.0, 171.0, 6.9, 9.7, 11.4),
    "360UB50.7": (356.0, 171.0, 7.3, 11.5, 11.4),
    "360UB56.7": (359.0, 172.0, 8.0, 13.0, 11.4),
    "410UB53.7": (403.0, 178.0, 7.6, 10.9, 11.4),
    "410UB59.7": (406.0, 178.0, 7.8, 12.8, 11.4),
    "460UB67.1": (454.0, 190.0, 8.5, 12.7, 11.4),
    "460UB74.6": (457.0, 190.0, 9.1, 14.5, 11.4),
    "460UB82.1": (460.0, 191.0, 9.9, 16.0, 11.4),
    "530UB82.0": (528.0, 209.0, 9.6, 13.2, 14.0),
    "530UB92.4": (533.0, 209.0, 10.2, 15.6, 14.0),
    "610UB101": (602.0, 228.0, 10.6, 14.8, 14.0),
    "610UB113": (607.0, 228.0, 11.2, 17.3, 14.0),
    "610UB125": (612.0, 229.0, 11.9, 19.6, 14.0),
}

AU_UC = {
    "100UC14.8": (97.0, 99.0, 5.0, 7.0, 10.0),
    "150UC23.4": (152.0, 152.0, 6.1, 6.8, 8.9),
    "150UC30.0": (158.0, 153.0, 6.6, 9.4, 8.9),
    "150UC37.2": (162.0, 154.0, 8.1, 11.5, 8.9),
    "200UC46.2": (203.0, 203.0, 7.3, 11.0, 11.4),
    "200UC52.2": (206.0, 204.0, 7.9, 12.5, 11.4),
    "200UC59.5": (210.0, 205.0, 9.3, 14.2, 11.4),
    "250UC72.9": (254.0, 254.0, 8.6, 14.2, 12.7),
    "250UC89.5": (260.0, 256.0, 10.5, 17.3, 12.7),
    "310UC96.8": (308.0, 305.0, 9.9, 15.4, 16.5),
    "310UC118": (315.0, 307.0, 11.9, 18.7, 16.5),
    "310UC137": (321.0, 309.0, 13.8, 21.7, 16.5),
    "310UC158": (327.0, 311.0, 15.7, 25.0, 16.5),
}

# US W shapes in inches: (d, bf, tw, tf, k_des)  (AISC Shapes Database v15/v16)
_US_W_IN = {
    "W8x10": (7.89, 3.94, 0.170, 0.205, 0.505),
    "W8x13": (7.99, 4.00, 0.230, 0.255, 0.555),
    "W8x15": (8.11, 4.01, 0.245, 0.315, 0.615),
    "W8x18": (8.14, 5.25, 0.230, 0.330, 0.630),
    "W8x21": (8.28, 5.27, 0.250, 0.400, 0.700),
    "W8x24": (7.93, 6.50, 0.245, 0.400, 0.700),
    "W8x28": (8.06, 6.54, 0.285, 0.465, 0.859),
    "W8x31": (8.00, 8.00, 0.285, 0.435, 0.829),
    "W8x35": (8.12, 8.02, 0.310, 0.495, 0.889),
    "W8x40": (8.25, 8.07, 0.360, 0.560, 0.954),
    "W8x48": (8.50, 8.11, 0.400, 0.685, 1.08),
    "W8x58": (8.75, 8.22, 0.510, 0.810, 1.20),
    "W8x67": (9.00, 8.28, 0.570, 0.935, 1.33),
    "W10x12": (9.87, 3.96, 0.190, 0.210, 0.510),
    "W10x15": (9.99, 4.00, 0.230, 0.270, 0.570),
    "W10x17": (10.1, 4.01, 0.240, 0.330, 0.630),
    "W10x19": (10.2, 4.02, 0.250, 0.395, 0.695),
    "W10x22": (10.2, 5.75, 0.240, 0.360, 0.660),
    "W10x26": (10.3, 5.77, 0.260, 0.440, 0.740),
    "W10x30": (10.5, 5.81, 0.300, 0.510, 0.810),
    "W10x33": (9.73, 7.96, 0.290, 0.435, 0.935),
    "W10x39": (9.92, 7.99, 0.315, 0.530, 1.03),
    "W10x45": (10.1, 8.02, 0.350, 0.620, 1.12),
    "W10x49": (9.98, 10.0, 0.340, 0.560, 1.06),
    "W10x54": (10.1, 10.0, 0.370, 0.615, 1.12),
    "W10x60": (10.2, 10.1, 0.420, 0.680, 1.18),
    "W10x68": (10.4, 10.1, 0.470, 0.770, 1.27),
    "W10x77": (10.6, 10.2, 0.530, 0.870, 1.37),
    "W10x88": (10.8, 10.3, 0.605, 0.990, 1.49),
    "W10x100": (11.1, 10.3, 0.680, 1.12, 1.62),
    "W12x14": (11.9, 3.97, 0.200, 0.225, 0.525),
    "W12x16": (12.0, 3.99, 0.220, 0.265, 0.565),
    "W12x19": (12.2, 4.01, 0.235, 0.350, 0.650),
    "W12x22": (12.3, 4.03, 0.260, 0.425, 0.725),
    "W12x26": (12.2, 6.49, 0.230, 0.380, 0.680),
    "W12x30": (12.3, 6.52, 0.260, 0.440, 0.740),
    "W12x35": (12.5, 6.56, 0.300, 0.520, 0.820),
    "W12x40": (11.9, 8.01, 0.295, 0.515, 1.02),
    "W12x45": (12.1, 8.05, 0.335, 0.575, 1.08),
    "W12x50": (12.2, 8.08, 0.370, 0.640, 1.14),
    "W12x53": (12.1, 10.0, 0.345, 0.575, 1.08),
    "W12x58": (12.2, 10.0, 0.360, 0.640, 1.14),
    "W12x65": (12.1, 12.0, 0.390, 0.605, 1.20),
    "W12x72": (12.3, 12.0, 0.430, 0.670, 1.27),
    "W12x79": (12.4, 12.1, 0.470, 0.735, 1.33),
    "W12x87": (12.5, 12.1, 0.515, 0.810, 1.41),
    "W12x96": (12.7, 12.2, 0.550, 0.900, 1.50),
    "W12x106": (12.9, 12.2, 0.610, 0.990, 1.59),
    "W14x22": (13.7, 5.00, 0.230, 0.335, 0.735),
    "W14x26": (13.9, 5.03, 0.255, 0.420, 0.820),
    "W14x30": (13.8, 6.73, 0.270, 0.385, 0.785),
    "W14x34": (14.0, 6.75, 0.285, 0.455, 0.855),
    "W14x38": (14.1, 6.77, 0.310, 0.515, 0.915),
    "W14x43": (13.7, 8.00, 0.305, 0.530, 1.12),
    "W14x48": (13.8, 8.03, 0.340, 0.595, 1.19),
    "W14x53": (13.9, 8.06, 0.370, 0.660, 1.25),
    "W14x61": (13.9, 10.0, 0.375, 0.645, 1.24),
    "W14x68": (14.0, 10.0, 0.415, 0.720, 1.31),
    "W14x74": (14.2, 10.1, 0.450, 0.785, 1.38),
    "W14x82": (14.3, 10.1, 0.510, 0.855, 1.45),
    "W14x90": (14.0, 14.5, 0.440, 0.710, 1.31),
    "W14x99": (14.2, 14.6, 0.485, 0.780, 1.38),
    "W14x109": (14.3, 14.6, 0.525, 0.860, 1.46),
    "W14x120": (14.5, 14.7, 0.590, 0.940, 1.54),
    "W14x132": (14.7, 14.7, 0.645, 1.03, 1.63),
    "W16x26": (15.7, 5.50, 0.250, 0.345, 0.747),
    "W16x31": (15.9, 5.53, 0.275, 0.440, 0.842),
    "W16x36": (15.9, 6.99, 0.295, 0.430, 0.832),
    "W16x40": (16.0, 7.00, 0.305, 0.505, 0.907),
    "W16x45": (16.1, 7.04, 0.345, 0.565, 0.967),
    "W16x50": (16.3, 7.07, 0.380, 0.630, 1.03),
    "W16x57": (16.4, 7.12, 0.430, 0.715, 1.12),
    "W16x67": (16.3, 10.2, 0.395, 0.665, 1.07),
    "W16x77": (16.5, 10.3, 0.455, 0.760, 1.16),
    "W16x89": (16.8, 10.4, 0.525, 0.875, 1.28),
    "W16x100": (17.0, 10.4, 0.585, 0.985, 1.39),
    "W18x35": (17.7, 6.00, 0.300, 0.425, 0.827),
    "W18x40": (17.9, 6.02, 0.315, 0.525, 0.927),
    "W18x46": (18.1, 6.06, 0.360, 0.605, 1.01),
    "W18x50": (18.0, 7.50, 0.355, 0.570, 0.972),
    "W18x55": (18.1, 7.53, 0.390, 0.630, 1.03),
    "W18x60": (18.2, 7.56, 0.415, 0.695, 1.10),
    "W18x65": (18.4, 7.59, 0.450, 0.750, 1.15),
    "W18x71": (18.5, 7.64, 0.495, 0.810, 1.21),
    "W18x76": (18.2, 11.0, 0.425, 0.680, 1.08),
    "W18x86": (18.4, 11.1, 0.480, 0.770, 1.17),
    "W18x97": (18.6, 11.1, 0.535, 0.870, 1.27),
    "W18x106": (18.7, 11.2, 0.590, 0.940, 1.34),
    "W21x44": (20.7, 6.50, 0.350, 0.450, 0.950),
    "W21x50": (20.8, 6.53, 0.380, 0.535, 1.04),
    "W21x57": (21.1, 6.56, 0.405, 0.650, 1.15),
    "W21x62": (21.0, 8.24, 0.400, 0.615, 1.12),
    "W21x68": (21.1, 8.27, 0.430, 0.685, 1.19),
    "W21x73": (21.2, 8.30, 0.455, 0.740, 1.24),
    "W21x83": (21.4, 8.36, 0.515, 0.835, 1.34),
    "W21x93": (21.6, 8.42, 0.580, 0.930, 1.43),
    "W21x101": (21.4, 12.3, 0.500, 0.800, 1.30),
    "W21x111": (21.5, 12.3, 0.550, 0.875, 1.38),
    "W21x122": (21.7, 12.4, 0.600, 0.960, 1.46),
    "W24x55": (23.6, 7.01, 0.395, 0.505, 1.01),
    "W24x62": (23.7, 7.04, 0.430, 0.590, 1.09),
    "W24x68": (23.7, 8.97, 0.415, 0.585, 1.09),
    "W24x76": (23.9, 8.99, 0.440, 0.680, 1.18),
    "W24x84": (24.1, 9.02, 0.470, 0.770, 1.27),
    "W24x94": (24.3, 9.07, 0.515, 0.875, 1.37),
    "W24x104": (24.1, 12.8, 0.500, 0.750, 1.25),
    "W24x117": (24.3, 12.8, 0.550, 0.850, 1.35),
    "W24x131": (24.5, 12.9, 0.605, 0.960, 1.46),
    "W24x146": (24.7, 12.9, 0.650, 1.09, 1.59),
    "W24x162": (25.0, 13.0, 0.705, 1.22, 1.72),
}
_IN = 25.4
US_W = {k: (d * _IN, bf * _IN, tw * _IN, tf * _IN, (kd - tf) * _IN)
        for k, (d, bf, tw, tf, kd) in _US_W_IN.items()}
# nominal depth (in) -> metric nominal depth (mm) used in AISC metric designations (W310x52 = W12x35)
_US_METRIC_DEPTH = {8: 200, 10: 250, 12: 310, 14: 360, 16: 410, 18: 460, 21: 530, 24: 610}
_LBFT_TO_KGM = 1.48816

# ---------------------------------------------------------------------------------------------
# Property calculators
# ---------------------------------------------------------------------------------------------
_E_FIL = (10.0 - 3.0 * math.pi) / (12.0 - 3.0 * math.pi)  # centroid of spandrel / r = 0.2234
_A_FIL = 1.0 - math.pi / 4.0                                # spandrel area / r²
# second moment of spandrel about its own centroidal axis (parallel to a straight edge) / r⁴
_I_FIL = (1.0 / 3.0 - math.pi / 16.0) - _A_FIL * (1.0 - _E_FIL) ** 2


def _spandrel(r: float):
    """(area, centroid distance from straight edge, own I about centroid) of a fillet of radius r."""
    return _A_FIL * r * r, _E_FIL * r, _I_FIL * r ** 4


def props_I(h: float, b: float, tw: float, tf: float, r: float, eta: float = 1.0) -> dict:
    """Doubly symmetric rolled I/H with parallel flanges and 4 root fillets of radius r (mm)."""
    hw = h - 2.0 * tf
    af, ef, i0 = _spandrel(r)
    A = 2.0 * b * tf + hw * tw + 4.0 * af
    # major axis
    dy = h / 2.0 - tf - ef                         # fillet centroid to y-axis
    Iy = (b * h ** 3 - (b - tw) * hw ** 3) / 12.0 + 4.0 * (i0 + af * dy * dy)
    # minor axis
    dz = tw / 2.0 + ef                             # fillet centroid to z-axis
    Iz = (2.0 * tf * b ** 3 + hw * tw ** 3) / 12.0 + 4.0 * (i0 + af * dz * dz)
    Wpl_y = b * tf * (h - tf) + tw * hw * hw / 4.0 + 4.0 * af * dy
    Wpl_z = tf * b * b / 2.0 + hw * tw * tw / 4.0 + 4.0 * af * dz
    # St Venant torsion incl. fillets (SCI P363 approximation)
    a1 = (-0.042 + 0.2204 * tw / tf + 0.1355 * r / tf - 0.0865 * r * tw / tf ** 2
          - 0.0725 * tw ** 2 / tf ** 2)
    D1 = ((tf + r) ** 2 + tw * (r + tw / 4.0)) / (2.0 * r + tf)
    It = 2.0 / 3.0 * b * tf ** 3 + hw * tw ** 3 / 3.0 + 2.0 * a1 * D1 ** 4 - 0.420 * tf ** 4
    Iw = Iz * (h - tf) ** 2 / 4.0
    Avz = max(A - 2.0 * b * tf + (tw + 2.0 * r) * tf, eta * hw * tw)
    Avy = 2.0 * b * tf
    return {
        "A": A, "Iy": Iy, "Iz": Iz, "It": It, "Iw": Iw,
        "Wel_y": Iy / (h / 2.0), "Wel_z": Iz / (b / 2.0),
        "Wpl_y": Wpl_y, "Wpl_z": Wpl_z,
        "iy": math.sqrt(Iy / A), "iz": math.sqrt(Iz / A),
        "Avy": Avy, "Avz": Avz, "mass": A * _KGM,
        "hw": hw, "eta_Avz": eta,
    }


def corner_radii(t: float, fabrication: str = "hot_finished"):
    """(ro, ri) for RHS/SHS: EN 10210-2 (hot finished) or EN 10219-2 (cold formed)."""
    if fabrication == "cold_formed":
        ro = 2.0 * t if t <= 6.0 else (2.5 * t if t <= 10.0 else 3.0 * t)
        return ro, ro - t
    return 1.5 * t, 1.0 * t


def _rounded_rect(B: float, H: float, R: float):
    """Area, I about axis parallel to B, and plastic modulus about that axis of a solid
    B (width) × H (depth) rectangle with 4 corner radii R."""
    if R <= 0:
        return B * H, B * H ** 3 / 12.0, B * H * H / 4.0
    af, ef, i0 = _spandrel(R)
    d = H / 2.0 - ef
    A = B * H - 4.0 * af
    I = B * H ** 3 / 12.0 - 4.0 * (i0 + af * d * d)
    Wpl = B * H * H / 4.0 - 4.0 * af * d
    return A, I, Wpl


def props_RHS(h: float, b: float, t: float, ro: Optional[float] = None,
              fabrication: str = "hot_finished", ri: Optional[float] = None) -> dict:
    """RHS/SHS: h = depth (bends about y), b = width, t = wall, ro/ri = outer/inner corner radius.
    Default radii: EN 10210-2 hot finished ro = 1.5 t, ri = t; cold formed per EN 10219-2."""
    ro_d, ri_d = corner_radii(t, fabrication)
    if ro is None:
        ro = ro_d
    if ri is None:
        ri = ri_d if fabrication == "cold_formed" else min(ri_d, ro)
        if fabrication == "cold_formed":
            ri = max(ro - t, 0.0)
    Ao, Iyo, Wyo = _rounded_rect(b, h, ro)
    Ai, Iyi, Wyi = _rounded_rect(b - 2 * t, h - 2 * t, ri)
    _, Izo, Wzo = _rounded_rect(h, b, ro)
    _, Izi, Wzi = _rounded_rect(h - 2 * t, b - 2 * t, ri)
    A = Ao - Ai
    Iy, Iz = Iyo - Iyi, Izo - Izi
    Rc = (ro + ri) / 2.0
    hp = 2.0 * ((b - t) + (h - t)) - 2.0 * Rc * (4.0 - math.pi)
    Ah = (b - t) * (h - t) - Rc * Rc * (4.0 - math.pi)
    K = 2.0 * Ah * t / hp
    It = t ** 3 * hp / 3.0 + 2.0 * K * Ah
    Wt = It / (t + K / t)
    return {
        "A": A, "Iy": Iy, "Iz": Iz, "It": It, "Iw": 0.0,
        "Wel_y": Iy / (h / 2.0), "Wel_z": Iz / (b / 2.0),
        "Wpl_y": Wyo - Wyi, "Wpl_z": Wzo - Wzi,
        "iy": math.sqrt(Iy / A), "iz": math.sqrt(Iz / A),
        "Avy": A * b / (b + h), "Avz": A * h / (b + h), "mass": A * _KGM,
        "Wt": Wt, "ro": ro, "ri": ri,
    }


def props_CHS(d: float, t: float) -> dict:
    di = d - 2.0 * t
    A = math.pi * (d * d - di * di) / 4.0
    I = math.pi * (d ** 4 - di ** 4) / 64.0
    Wel = I / (d / 2.0)
    Wpl = (d ** 3 - di ** 3) / 6.0
    i = math.sqrt(I / A)
    Av = 2.0 * A / math.pi
    return {
        "A": A, "Iy": I, "Iz": I, "It": 2.0 * I, "Iw": 0.0,
        "Wel_y": Wel, "Wel_z": Wel, "Wpl_y": Wpl, "Wpl_z": Wpl,
        "iy": i, "iz": i, "Avy": Av, "Avz": Av, "mass": A * _KGM, "Wt": 2.0 * Wel,
    }


# ---------------------------------------------------------------------------------------------
# Name parsing
# ---------------------------------------------------------------------------------------------
_NUM = r"(\d+(?:\.\d+)?)"
_SEP = r"\s*[X×*/]\s*"
_DEC = r"(\d*\.?\d+)"


def _g(v: float) -> str:
    return f"{v:g}"


def _I_result(name, dims, region, source_key):
    h, b, tw, tf, r = dims
    return {
        "name": name, "shape": "I", "fabrication": "rolled",
        "dims": {"h": h, "b": b, "tw": tw, "tf": tf, "r": r},
        "props": props_I(h, b, tw, tf, r),
        "region": region, "source": SOURCES[source_key],
    }


def _index_uk():
    idx = {}
    for series, cat in (("UB", UK_UB), ("UC", UK_UC)):
        for k, v in cat.items():
            a, bb, m = (float(x) for x in k.split()[1].split("x"))
            idx.setdefault((round(a), round(bb)), []).append((m, k, v, series))
    return idx


def _index_au():
    idx = {}
    for series, cat in (("UB", AU_UB), ("UC", AU_UC)):
        for k, v in cat.items():
            mo = re.match(r"(\d+)(UB|UC)([\d.]+)$", k)
            idx.setdefault((series, int(mo.group(1))), []).append((float(mo.group(3)), k, v))
    return idx


def _index_us():
    idx = {}
    for k, v in US_W.items():
        mo = re.match(r"W(\d+)x([\d.]+)$", k)
        idx.setdefault(int(mo.group(1)), []).append((float(mo.group(2)), k, v))
    return idx


_UK_IDX = _index_uk()
_AU_IDX = _index_au()
_US_IDX = _index_us()


def _nearest(cands, mass, rel_tol):
    best = min(cands, key=lambda c: abs(c[0] - mass))
    if abs(best[0] - mass) <= rel_tol * max(mass, 1e-9) + 1e-9:
        return best
    return None


def _lookup_uk(series, a, b, m):
    cands = _UK_IDX.get((round(a), round(b)))
    if not cands:
        return None
    pref = [c for c in cands if c[3] == series] or cands
    hit = _nearest(pref, m, 0.02) or _nearest(cands, m, 0.02)
    if not hit:
        return None
    _, key, dims, ser = hit
    res = _I_result(key, dims, "UK", "UK_" + ser)
    if ser != series:
        res["warning"] = (f"requested {series} {_g(a)}x{_g(b)}x{_g(m)}: not in the {series} table; the catalogue "
                          f"section {key} ({ser} series) was used - check the section name")
    return res


def _lookup_au(series, depth, m):
    for ser in (series, "UC" if series == "UB" else "UB"):
        cands = _AU_IDX.get((ser, round(depth)))
        if cands:
            hit = _nearest(cands, m, 0.015)
            if hit:
                res = _I_result(hit[1], hit[2], "AU", "AU_" + ser)
                if ser != series:
                    res["warning"] = (f"requested {_g(depth)}{series}{_g(m)}: not in the {series} table; the "
                                      f"catalogue section {hit[1]} ({ser} series) was used - check the section name")
                return res
    return None


def _lookup_us(nom, wt):
    if nom <= 44:  # imperial W{in}x{lb/ft}
        cands = _US_IDX.get(round(nom))
        if not cands:
            return None
        hit = _nearest(cands, wt, 0.01)
        alias = None
    else:  # metric W{mm}x{kg/m}
        inv = {v: k for k, v in _US_METRIC_DEPTH.items()}
        nom_in = inv.get(round(nom))
        cands = _US_IDX.get(nom_in) if nom_in else None
        if not cands:
            return None
        cands = [(m * _LBFT_TO_KGM, k, v) for (m, k, v) in cands]
        hit = _nearest(cands, wt, 0.02)
        alias = f"W{round(nom)}x{_g(wt)}"
    if not hit:
        return None
    res = _I_result(hit[1], hit[2], "US", "US_W")
    if alias:
        res["alias"] = alias
    return res


def _frac(s: str) -> float:
    s = s.strip()
    m = re.match(r"^(\d+)\s*(?:-|\s)\s*(\d+)/(\d+)$", s)
    if m:
        return int(m.group(1)) + int(m.group(2)) / int(m.group(3))
    if "/" in s:
        n, d = s.split("/")
        return float(n) / float(d)
    return float(s)


def _hollow(kind, nums, fabrication, display=None):
    if kind == "CHS":
        if len(nums) != 2:
            return None
        d, t = nums
        if not (0 < 2 * t < d):
            return None
        return {"name": display or f"CHS {_g(d)}x{_g(t)}", "shape": "CHS",
                "fabrication": fabrication, "dims": {"d": d, "t": t},
                "props": props_CHS(d, t), "source": SOURCES["CHS"]}
    if len(nums) == 2:
        h = b = nums[0]
        t = nums[1]
    elif len(nums) == 3:
        h, b, t = nums
    else:
        return None
    if not (0 < 2 * t < min(h, b)):
        return None
    p = props_RHS(h, b, t, fabrication=fabrication)
    pre = "SHS" if h == b else "RHS"
    src = SOURCES["HOLLOW_CF" if fabrication == "cold_formed" else "HOLLOW_HF"]
    return {"name": display or f"{pre} {_g(h)}x{_g(b)}x{_g(t)}", "shape": "RHS",
            "fabrication": fabrication, "dims": {"h": h, "b": b, "t": t, "ro": p["ro"]},
            "props": p, "source": src}


_HOLLOW_TOKENS = {"SHS": "RHS", "RHS": "RHS", "CHS": "CHS", "QRO": "RHS", "RRO": "RHS",
                  "RO": "CHS", "SQHS": "RHS", "RECHS": "RHS", "CIRC": "CHS", "PIPE": "CHS"}
_TOK = r"(SHS|RHS|CHS|QRO|RRO|RO|SQHS)"


_HSS_RE = re.compile(r"^HSS\s*" + _DEC + r"\s*X\s*([\d./\- ]+?)(?:\s*X\s*([\d./\- ]+))?$")


def _parse_hss(s: str):
    """AISC HSS designation -> section dict, or None.  Imperial names (inches, fractions) are converted
    to mm; a name is taken as metric (mm) when its first dimension is > 40 (no imperial HSS is wider
    than 24 in round / 20 in rectangular) or its wall thickness is a decimal > 1.0 (no imperial HSS
    wall exceeds 1 in, no metric wall is <= 1 mm; a fraction such as 1 1/4 is always inches).  Design wall thickness t_des = 0.93 t_nom (AISC 360-22 B4.2)."""
    m = _HSS_RE.match(s)
    if not m:
        return None
    rect = m.group(3) is not None
    a = float(m.group(1))
    t_txt = (m.group(3) if rect else m.group(2)).strip()
    tn = _frac(t_txt)
    bb = _frac(m.group(2)) if rect else None
    metric = a > 40.0 or (bb is not None and bb > 40.0) or ("/" not in t_txt and tn > 1.0)
    u = 1.0 if metric else _IN
    a *= u
    tn *= u
    if tn <= 0:
        return None
    td = 0.93 * tn
    if rect:
        bb *= u
        if not (0 < 2 * td < min(a, bb)):
            return None
        p = props_RHS(a, bb, td, ro=2.0 * td, ri=td, fabrication="cold_formed")
        return {"name": f"HSS{m.group(1)}x{m.group(2).strip()}x{t_txt}", "shape": "RHS",
                "fabrication": "cold_formed", "dims": {"h": a, "b": bb, "t": td, "ro": 2.0 * td},
                "props": p, "region": "US", "source": SOURCES["HSS"],
                "units_in_name": "mm" if metric else "in"}
    if not (0 < 2 * td < a):
        return None
    return {"name": f"HSS{m.group(1)}x{t_txt}", "shape": "CHS",
            "fabrication": "cold_formed", "dims": {"d": a, "t": td},
            "props": props_CHS(a, td), "region": "US", "source": SOURCES["HSS"],
            "units_in_name": "mm" if metric else "in"}


def _parse(s: str, fabrication: Optional[str]):
    # ---- HSS (AISC): "HSS6X6X3/8", "HSS6.625X.280", "HSS 8X4X1/2", "HSS 6x6x1 1/4";
    #      metric designations (AISC metric / SOFiSTiK library) "HSS152.4x152.4x9.5", "HSS168.3x6.4" in mm
    if re.match(r"^HSS\b|^HSS\d", s):
        try:
            return _parse_hss(s)
        except (ValueError, ZeroDivisionError, TypeError):
            return None

    fab = fabrication or "hot_finished"
    # ---- UK I, prefix or suffix: "UB 254x146x43", "UKB254/146/43", "254x146x43UB"
    tri = _NUM + _SEP + _NUM + _SEP + _NUM
    m = re.match(r"^(UKB|UB|UKC|UC)\s*[-_]?\s*" + tri + "$", s) or \
        re.match(r"^" + tri + r"\s*[-_]?\s*(UKB|UB|UKC|UC)$", s)
    if m:
        g = m.groups()
        tok, nums = (g[0], g[1:]) if not g[0][0].isdigit() else (g[3], g[:3])
        series = "UC" if tok.endswith("C") else "UB"
        return _lookup_uk(series, *(float(x) for x in nums))
    # ---- AU I: "310UB40.4", "310 UB 40.4", "UB 310x40.4"
    m = re.match(r"^" + _NUM + r"\s*(UB|UC)\s*" + _NUM + "$", s)
    if m:
        return _lookup_au(m.group(2), float(m.group(1)), float(m.group(3)))
    m = re.match(r"^(UB|UC)\s*" + _NUM + _SEP + _NUM + "$", s)
    if m:
        return _lookup_au(m.group(1), float(m.group(2)), float(m.group(3)))
    # ---- US W: "W12x35", "W 310 x 52"
    m = re.match(r"^W\s*" + _NUM + _SEP + _NUM + "$", s)
    if m:
        return _lookup_us(float(m.group(1)), float(m.group(2)))
    # ---- Hollow sections, prefix or suffix
    nums_re = _NUM + r"(?:" + _SEP + _NUM + r")?" + r"(?:" + _SEP + _NUM + r")?"
    m = re.match(r"^" + _TOK + r"\s*[-_]?\s*" + nums_re + "$", s)
    if m:
        kind = _HOLLOW_TOKENS[m.group(1)]
        nums = [float(x) for x in m.groups()[1:] if x is not None]
        return _hollow(kind, nums, fab)
    m = re.match(r"^" + nums_re + r"\s*[-_]?\s*" + _TOK + "$", s)
    if m:
        kind = _HOLLOW_TOKENS[m.groups()[-1]]
        nums = [float(x) for x in m.groups()[:-1] if x is not None]
        return _hollow(kind, nums, fab)
    return None


def from_name(name: str, fabrication: Optional[str] = None) -> Optional[dict]:
    """Parse a section name and return {"name","shape","fabrication","dims","props",
    "source", ...} or None when the name is not recognised / not in the catalogue.

    fabrication: optional override for hollow sections ("hot_finished" default, or "cold_formed").
    A name containing "CF" / "COLD" / "EN 10219" is treated as cold formed; "HF" / "HOT" /
    "EN 10210" as hot finished.  I sections are always "rolled".
    """
    if not name or not isinstance(name, str):
        return None
    s = name.strip().upper()
    s = re.sub(r"(?<=\d),(?=\d)", ".", s)        # decimal comma
    s = s.replace("×", "X").replace("Ø", "")
    # fabrication tags
    if fabrication is None:
        if re.search(r"\bCF\b|COLD|10219|\bC\d{3}(?:L0|L15)?\b", s):
            fabrication = "cold_formed"
        elif re.search(r"\bHF\b|HOT|10210", s):
            fabrication = "hot_finished"
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"\b(EN\s*10210(-\d)?|EN\s*10219(-\d)?|HF|CF|HOT[\s-]*FINISHED|COLD[\s-]*FORMED)\b",
               " ", s)
    s = re.sub(r"\s+", " ", s).strip(" -_")
    res = _parse(s, fabrication)
    if res is None:
        # strip a trailing material grade, e.g. "UB 254x146x43 S275", "150X150X10SHS C350L0"
        s2 = re.sub(r"[\s\-_]+(S\d{3}\w*|C\d{3}\w*|GR\w*|A\d{3}\w*|G\d{3}\w*)$", "", s).strip()
        if s2 != s:
            res = _parse(s2, fabrication)
    if res is not None:
        res.setdefault("region", None)
        res["input_name"] = name
    return res


def catalogue_names() -> list:
    """All rolled I section names held in the catalogue."""
    return list(UK_UB) + list(UK_UC) + list(AU_UB) + list(AU_UC) + list(US_W)
