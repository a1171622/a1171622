import sys,numpy as np,matplotlib,re
matplotlib.use('Agg'); import matplotlib.pyplot as plt
sys.path.insert(0,'.'); from parse import parse_sln
L=open('v17.dat').read().split('\n'); iM=L.index('PROG SOFIMSHC urs:2'); iE=next(i for i in range(iM,len(L)) if L[i]=='END')
s=parse_sln(L,iE)
fig=plt.figure(figsize=(24,13)); ax=fig.add_axes([0.01,0.04,0.50,0.9]); ax3=fig.add_axes([0.50,0.02,0.50,0.94],projection='3d')
def col(v):
    g=v['grp']
    if g in (60,61):
        a,b=v['segs'][0]; m=(a+b)/2; return '#2a9d2a' if np.degrees(np.arctan2(m[1],m[0]))%360>180 else '#1f4fd6'
    if g==62: return '#ff7f0e'
    return None
for n,v in s.items():
    for a,b in v['segs']:
        c=col(v)
        if c: lw=0.5 if v['sno']==7 else (2.2 if v['sno'] in (5,8) else 1)
        if c is None:
            if 3.9<a[2]<4.2 and 3.9<b[2]<4.2: ax.plot([a[0],b[0]],[a[1],b[1]],color='0.45',lw=1)
            if 7.9<a[2]<8.2 and 7.9<b[2]<8.2 and v['grp']==25 and v['sno']==4: ax.plot([a[0],b[0]],[a[1],b[1]],color='0.75',lw=1,ls='--')
        else: ax.plot([a[0],b[0]],[a[1],b[1]],color=c,lw=lw,zorder=3)
        # 3D (region near stairs only)
        m=(a+b)/2; ang=np.degrees(np.arctan2(m[1],m[0]))%360
        if (ang>275 or ang<75) and np.hypot(m[0],m[1])>7:
            cc=c or '0.6'; ax3.plot([a[0],b[0]],[a[1],b[1]],[a[2],b[2]],color=cc,lw=(0.5 if v['sno']==7 else 1.6) if c else 0.6)
# L2 radial changes
for d,cc,lab in ((40,'#d62728','L2 radial 40° now stops at r 8.5'),(60,'#2ca02c','L2 radial 60° now to r 12')):
    t=np.radians(d); ax.plot([8.5*np.cos(t),12*np.cos(t)],[8.5*np.sin(t),12*np.sin(t)],color=cc,lw=5,alpha=.5)
ax.text(9.3,8.6,'L2 radial 40°: stops at r 8.5\n(stair B opening 20-60°)',color='#d62728',fontsize=10)
ax.text(2.5,12.4,'L2 radial 60°: now to r 12 (stair B top)',color='#2ca02c',fontsize=10)
spt=[tuple(map(float,m.groups())) for l in L[iM:iE] for m in [re.match(r'SPT\s+9\d\d\s+X\s+(\S+)\s+(\S+)\s+(\S+)',l)] if m]
ax.plot([p[0] for p in spt],[p[1] for p in spt],'^',ms=9,mfc='#8c4a00',mec='k',zorder=6,label='pinned ground support (16)')
ax3.scatter([p[0] for p in spt],[p[1] for p in spt],[p[2] for p in spt],marker='^',s=40,c='#8c4a00')
import ext_geom as g
for arm,k,nm in (('R','S_lo','S1'),('R','S_hi','S2'),('L','S_lo','S3'),('L','S_hi','S4')):
    p=g.ARMS[arm][k]; ax.plot(p[0],p[1],'o',ms=12,mfc='yellow',mec='k',mew=2,zorder=7); ax.text(p[0]-1.4,p[1]+0.25,nm,fontsize=12,fontweight='bold')
    ax3.scatter([p[0]],[p[1]],[4.054],s=80,c='yellow',edgecolors='k'); ax3.text(p[0],p[1],4.6,nm,fontweight='bold')
for p,t in (((11.57,2.59),'clash in DXF: flight 2 inner stringer\npasses 20 mm from the L1 ring beam\nand 90 mm from the raking column'),((7.2,-9.42),'same on the left arm\n(30 mm / 110 mm)')):
    ax.plot(*p,'x',ms=16,mew=3,color='#d62728',zorder=8); ax.annotate(t,p,(p[0]+2.2,p[1]-1.6 if p[1]>0 else p[1]-2.4),fontsize=9.5,color='#d62728',arrowprops=dict(arrowstyle='->',color='#d62728'))
for d in range(0,360,20): t=np.radians(d); ax.text(12.9*np.cos(t),12.9*np.sin(t),f'{d}°',ha='center',va='center',fontsize=9,color='0.35')
from matplotlib.lines import Line2D
ax.legend(handles=[Line2D([],[],color='0.45',label='L1 framing'),Line2D([],[],color='#2a9d2a',lw=2,label='stair A (unchanged)'),Line2D([],[],color='#1f4fd6',lw=2,label='stair B v17 (rotated -20°)'),
   Line2D([],[],color='#ff7f0e',lw=2,label='external stair, group 62 (RHS 200x100x6, SHS 100x100x5 legs)'),Line2D([],[],marker='^',ls='',mfc='#8c4a00',mec='k',label='pinned ground support (16)'),
   Line2D([],[],marker='o',ls='',mfc='yellow',mec='k',ms=10,label='S1-S4 SHS bracket to L1 ring, pinned at ring')],loc='lower left',fontsize=10)
ax.set_aspect('equal'); ax.set_xlim(-4,16.5); ax.set_ylim(-15,14); ax.grid(alpha=.25); ax.set_title('26016 v17 model as built (plan, model axes in m)',fontsize=13)
ax3.set_box_aspect((1,1.6,0.45)); ax3.view_init(elev=22,azim=-25); ax3.set_title('v17, 3D of the east side (stairs + external stair)',fontsize=12)
ax3.set_xlabel('x'); ax3.set_ylabel('y'); ax3.set_zlabel('z')
plt.savefig('v17_model_check.png',dpi=100)
