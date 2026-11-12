import json, math, pickle, bisect
from PIL import Image, ImageDraw, ImageFont
M=pickle.load(open("model.pkl","rb")); xyz,beams,G=M["xyz"],M["beams"],M["G"]
starts=[s for s,_ in G]; eg=lambda nr: G[bisect.bisect_right(starts,nr)-1][1]
A2=json.load(open("partA2.json")); A3=json.load(open("partA3.json"))
F=lambda s:ImageFont.truetype("arial.ttf",s); FB=lambda s:ImageFont.truetype("arialbd.ttf",s)
W,H=3900,1800; img=Image.new("RGB",(W,H),"white"); d=ImageDraw.Draw(img)
sc=60
def P(p,cx): return (cx+p[0]*sc, 900-p[1]*sc)
def polar(r,th,cx): return P((r*math.cos(math.radians(th)),r*math.sin(math.radians(th))),cx)
GREY=(185,185,185)
def frame(groups,cx,zlo,zhi,col=GREY,w=2):
    for b,v in beams.items():
        if eg(b) in groups:
            a,c=v["nodes"]
            if zlo<=xyz[a][2]<=zhi and zlo<=xyz[c][2]<=zhi: d.line([P(xyz[a],cx),P(xyz[c],cx)],fill=col,width=w)
def hl(nodes,cx,col,w=7):
    d.line([P(xyz[n],cx) for n in nodes],fill=col,width=w)
def lab(xy,t,col=(0,0,0),f=None,anchor="la"):
    d.text(xy,t,fill=col,font=f or F(24),anchor=anchor)
# ---------- left panel: Level 1 + supports
cx=830
lab((40,30),"LEVEL 1 (z 4.05) + supports (plan, x right, y up)",f=FB(34))
frame({15},cx,4.0,4.1); frame({62},cx,0,4.5,(205,225,240),1)
# angles
for th in range(0,360,20): 
    x,y=polar(13.3,th,cx); lab((x,y),"%d°"%th,(120,120,120),F(20),"mm")
# column bases
for r in A3["rows"]:
    n=r["node"]
    if n>1000: continue
    x,y=P(xyz[n],cx); c=(0,90,200) if n<900 else (0,150,150)
    d.ellipse([x-8,y-8,x+8,y+8],fill=c)
    if n<100: lab((x+10,y-26),"%d: %.0f"%(n,r["pz"]),c,F(19))
# ring spans (a)
import geo
ring=sorted([n for n in xyz if abs(xyz[n][2]-4.054)<0.01 and 11.95<geo.pol(n)[0]<12.05],key=lambda n:geo.pol(n)[1])
def arc(t0,t1):
    return [n for n in ring if (t0<=geo.pol(n)[1]<=t1)]
hl(arc(0,40.1),cx,(220,30,30)); hl([n for n in ring if geo.pol(n)[1]>=319.9]+[ring[0]],cx,(240,140,0))
for th in range(0,360,40):
    x,y=polar(12,th,cx); d.rectangle([x-9,y-9,x+9,y+9],outline=(0,0,0),width=3)
x,y=polar(12,20,cx); d.line([(x,y),(1450,330)],fill=(220,30,30),width=2); lab((1455,300),"(a) 0-40°, L 8.3 m\n201: 11.2 rel / 12.5 abs\n221: 11.5 rel / 12.7 abs",(220,30,30),F(22))
x,y=polar(12,340,cx); d.line([(x,y),(1450,1200)],fill=(240,140,0),width=2); lab((1455,1190),"(a) 320-0°: LC 11 8.1 rel",(240,140,0),F(22))
# radials 40 and 280 r 8.5-12 with posts
for th,col in ((40,(150,0,170)),(280,(150,0,170))):
    d.line([polar(8.5,th,cx),polar(12,th,cx)],fill=col,width=8)
    for rp in (9.675,11.773):
        x,y=polar(rp,th,cx); d.ellipse([x-10,y-10,x+10,y+10],outline=col,width=4)
x,y=polar(9,52,cx); lab((x,y),"(e) radial 40°, posts 603/604\nspan r 8.5-12 (3.5 m): 1.8 mm",(150,0,170),F(22))
x,y=polar(8.8,262,cx); lab((x-120,y),"(e) SLN 222, 280°, posts 601/602\nspan r 8.5-12 (3.5 m): 1.8 mm",(150,0,170),F(22))
lab((40,1600),"Blue dot + number = column/diagonal base node: pz under 102 (kN, + = compression). Teal = stair supports 901-916.\nSquares = raking columns (group 11) at the ring, 40° apart: the ends of each (a) span. Purple circles = stair landing posts (group 61).\nDeflection 'rel' = relative to the straight line between the span ends; 'abs' = global uz.",(60,60,60),F(23))
# ---------- right panel: Level 2
cx=2850
lab((2000,30),"LEVEL 2 (z 8.05)  and roof radials",f=FB(34))
frame({25},cx,8.0,8.1)
for th in range(0,360,20):
    x,y=polar(13.3,th,cx); lab((x,y),"%d°"%th,(120,120,120),F(20),"mm")
for th in range(20,360,40):
    x,y=polar(12,th,cx); d.rectangle([x-9,y-9,x+9,y+9],outline=(0,0,0),width=3)
x,y=polar(3,0,cx)
for th in (20,80,140,200,260,320):
    x,y=polar(3,th,cx); d.rectangle([x-7,y-7,x+7,y+7],fill=(0,0,0))
# SLN 56
ring2=sorted([n for n in xyz if abs(xyz[n][2]-8.055)<0.01 and 11.95<geo.pol(n)[0]<12.05],key=lambda n:geo.pol(n)[1])
hl([n for n in ring2 if geo.pol(n)[1]>=339.9]+[n for n in ring2 if geo.pol(n)[1]<0.1],cx,(220,30,30),10)
x,y=polar(12,340,cx); lab((x-80,y+25),"node 1460 (340°): My -163.2 hog\nN +13.5 (tension), Vz -91.0, Mz 1.4",(220,30,30),F(22))
x,y=polar(12,0,cx); lab((x+20,y-30),"node 1485 (0°): My +136.7 sag\n(no column, radial only)",(220,30,30),F(22))
lab((3100,1130),"(A8) SLN 56, 4.168 m, LC 120\npsi = +136.7 / -163.2 = -0.84\nMy = 0 at about 349°",(220,30,30),F(22))
for th,col,t in ((220,(0,120,0),"(b) radial 220°, kingpost r 0.66 -> r 12 (11.34 m)\n201: 17.9 rel / 20.0 abs;  LC 11+12+13: 13.5 rel"),
                 (240,(0,170,170),"(b) radial 240° (ring end not on a column)\n201: 33.1 abs (11.3 rel); Q: 24.9 abs")):
    d.line([polar(0.66,th,cx),polar(12,th,cx)],fill=col,width=8)
lab((1990,1050),"(b) radial 220°, r 0.66 -> 12 (11.34 m)\n201: 17.9 rel / 20.0 abs\nLC 11+12+13: 13.5 rel / 15.0 abs",(0,120,0),F(22))
lab((1990,1400),"(b) radial 240° (ring end free of column)\n201: 33.1 abs (11.3 rel)\nLC 11+12+13: 24.9 abs (8.6 rel)",(0,150,150),F(22))
d.ellipse([cx-12,900-12,cx+12,900+12],fill=(0,0,0)); lab((cx+15,905),"kingpost hub r 0.66",(0,0,0),F(20))
lab((2000,1600),"Black squares on the ring = L1-L2 / L2-roof columns (groups 21/31), 40° apart. Black squares at r 3 = inner columns (group 24).\nRoof radials (not drawn): 201 12.4 rel at 340°, 15.9 abs at 180°; LC 12 8.1 rel; uplift G+W (206) 31.7 abs / 27.2 rel at 180°.",(60,60,60),F(23))
img.save("A_followup_reading.png"); print("ok")
