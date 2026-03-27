#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  LAMEDUKE ARCADE ENGINE  v3.0                                       ║
║  Duke Nukem 3D Prototype  —  Python / Ursina  —  Arcade Edition    ║
║                                                                      ║
║  FIXES v2 → v3:                                                     ║
║  [FIX-01] CRASH: Cannot subclass @singleton Ursina                 ║
║           → GameManager now extends Entity (correct Ursina pattern) ║
║  [FIX-02] CRASH: gravity bool toggle with float                     ║
║           → use explicit _jetpack_on bool flag                      ║
║  [FIX-03] Texture(PIL_image=) compatibility                         ║
║           → try pil_image first, fallback PIL_image                 ║
║                                                                      ║
║  ARCADE FEATURES:                                                   ║
║  [ARC-01] ROM/RAM check boot  (MS-DOS style, real asset scan)      ║
║  [ARC-02] Attract mode with scripted demo flythrough               ║
║  [ARC-03] INSERT COIN blinking message (no keyboard hints shown)   ║
║  [ARC-04] Two configurable welcome messages (top + bottom)         ║
║  [ARC-05] Arcade cabinet name banner                               ║
║  [ARC-06] Countdown time limit per credit                          ║
║  [ARC-07] GAME OVER screen with stats                              ║
║  [ARC-08] Level select (arcade button style)                       ║
║  [ARC-09] Demo map cycling in attract mode                         ║
║  [ARC-10] Cabinet ID + copyright footer                            ║
║                                                                      ║
║  KenBuild source ref: advsys.net/ken/buildsrc                       ║
║  Build Engine & Tools © 1993-1997 Ken Silverman                     ║
║  LameDuke © 1994-1997 3D Realms / Apogee Software                  ║
╚══════════════════════════════════════════════════════════════════════╝

USAGE:
    python lameduke_engine.py [path/to/lameduke/folder]

CONTROLS (arcade style — no hints shown in-game):
    WASD / Arrows  Move
    Mouse          Look
    Left Click     Fire
    1-5            Weapon
    Space          Jump
    F              Jetpack (if collected)
    ESC            Return to attract mode
    5 / C          Insert coin (attract mode)
    1 / Enter      Start / Select level

COMPILE TO EXE:
    pip install pyinstaller
    pyinstaller --onefile --windowed --name LameDuke lameduke_engine.py
"""
import sys, os, struct, math, time, random, io
from pathlib import Path

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

# ─── Dependency check ─────────────────────────────────────────────────────────
import importlib.util
_miss = [m for m in ('ursina','PIL','pygame')
         if not importlib.util.find_spec(m)]
if _miss:
    print(f"Missing: pip install {' '.join(_miss)}")
    sys.exit(1)

# ─── Imports ──────────────────────────────────────────────────────────────────
from PIL import Image
import pygame
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController

# ══════════════════════════════════════════════════════════════════════════════
#  ARCADE CONFIGURATION  ← customize your cabinet here
# ══════════════════════════════════════════════════════════════════════════════
ARCADE = {
    "arcade_name":      "DUKE  WORLD",
    "cabinet_id":       "MODEL DW-1994-REV-A",
    "welcome_top":      "WELCOME  TO  DUKE WORLD",
    "welcome_bottom":   "FOR AMUSEMENT ONLY  ·  18+",
    "time_limit_sec":   180,        # 0 = unlimited
    "credits_per_coin": 1,
    "attract_demo_sec": 18.0,
    "attract_cycle":    ["demo","title","demo","hiscore"],
    "demo_maps":        ["L1.MAP","N6.MAP","M1.MAP","WAR1.MAP"],
    "scanlines":        True,
}
AR, AG, AB = 255, 176, 0       # amber color

# ══════════════════════════════════════════════════════════════════════════════
#  BUILD ENGINE CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
BXY = 1.0 / 512.0
BZ  = 1.0 / 4096.0
PH  = 0.9   # player height

TILE = {
    'FEMANOID':408,'MANDROID':490,'DRONE1':579,'DRUNKGUY1':631,
    'EXPLODINGBARREL':627,'SHOTSPARK1':191,'RPG':563,'APLAYER':283,
    'SIXPAK':722,'AMMO':723,'BATTERYAMMO':1120,'RPGAMMO':1119,
    'SHIELD':726,'AIRTANK':727,'STEROIDS':724,'JETPACK':728,
    'SECTOREFFECTOR':175,'RADIUSEXPLOSION':46,
}

WEAPONS = [
    {'name':'TAZER',   'ammo':'battery','dmg': 8,'rate':0.20,'rng': 4.0,'snd':'gun1'},
    {'name':'PISTOL',  'ammo':'bullet', 'dmg':12,'rate':0.25,'rng':40.0,'snd':'shooting'},
    {'name':'CHAINGUN','ammo':'bullet', 'dmg': 8,'rate':0.08,'rng':30.0,'snd':'shooting'},
    {'name':'GRENADE', 'ammo':'grenade','dmg':60,'rate':0.60,'rng':20.0,'snd':'expl1'},
    {'name':'RPG',     'ammo':'rpg',   'dmg':80,'rate':0.90,'rng':60.0,'snd':'rpg'},
]

LEVELS = [
    (1,1,'L1.MAP','E1L1 — Urban Streets'),
    (1,2,'L2.MAP','E1L2 — Police Station'),
    (1,3,'L3.MAP','E1L3 — Underground'),
    (1,4,'L4.MAP','E1L4 — OctaBrain Preview'),
    (1,5,'L5.MAP','E1L5 — Industrial'),
    (1,6,'L6.MAP','E1L6 — Subway Terminal'),
    (1,7,'L7.MAP','E1L7 — Reactor Core'),
    (1,8,'L8.MAP','E1L8 — [stub]'),
    (1,9,'L9.MAP','E1L9 — [stub]'),
    (2,1,'M1.MAP','E2L1 — Military Base'),
    (2,2,'M2.MAP','E2L2 — Space Station'),
    (2,3,'M3.MAP','E2L3 — The Hangar'),
    (2,4,'M4.MAP','E2L4 — Fan Map'),
    (2,5,'M5.MAP','E2L5 — Orbital Platform'),
    (2,6,'M6.MAP','E2L6 — Alien Hive'),
    (2,7,'M7.MAP','E2L7 — Command Center'),
    (2,8,'M8.MAP','E2L8 — [stub]'),
    (3,1,'N1.MAP','E3L1 — Nuclear Facility'),
    (3,2,'N2.MAP','E3L2 — Fan Map'),
    (3,3,'N3.MAP','E3L3 — Fan Map'),
    (3,4,'N4.MAP','E3L4 — Fan Map'),
    (3,5,'N5.MAP','E3L5 — Fan Map'),
    (3,6,'N6.MAP','E3L6 — Derelict'),
    (3,7,'N7.MAP','E3L7 — Outpost'),
    (3,8,'N8.MAP','E3L8 — [stub]'),
    (4,1,'O1.MAP','BONUS 1'),
    (4,2,'O2.MAP','BONUS 2'),
    (4,3,'O3.MAP','BONUS 3'),
    (4,4,'O4.MAP','BONUS 4'),
    (0,0,'WAR1.MAP','WAR MAP 1'),
    (0,0,'WAR2.MAP','WAR MAP 2'),
]

# ══════════════════════════════════════════════════════════════════════════════
#  PALETTE
# ══════════════════════════════════════════════════════════════════════════════
def load_palette(d: Path):
    p = d/'PALETTE.DAT'
    if not p.exists(): return [(i,i,i) for i in range(256)]
    r = p.read_bytes()
    return [(min(255,r[i*3]*4), min(255,r[i*3+1]*4), min(255,r[i*3+2]*4))
            for i in range(256)]

# ══════════════════════════════════════════════════════════════════════════════
#  ART LOADER
# ══════════════════════════════════════════════════════════════════════════════
class ArtLoader:
    def __init__(self, d: Path, pal):
        self.pal = pal; self._p = {}; self._t = {}
        for f in sorted(d.glob('TILES*.ART')): self._parse(f)
        print(f"[ART] {len(self._p)} tiles loaded")

    def _parse(self, f: Path):
        data = f.read_bytes()
        if len(data)<16: return
        _,_, ts, te = struct.unpack_from('<4i',data,0)
        n = te-ts+1
        if n<=0 or n>8192: return
        o=16
        xs=list(struct.unpack_from(f'<{n}H',data,o)); o+=n*2
        ys=list(struct.unpack_from(f'<{n}H',data,o)); o+=n*2
        o+=n*4
        for i in range(n):
            w,h=xs[i],ys[i]
            if not w or not h or w>2048 or h>2048: continue
            sz=w*h
            if o+sz>len(data): break
            raw=data[o:o+sz]; o+=sz
            img=Image.new('RGBA',(w,h)); px=img.load()
            for x in range(w):
                co=x*h
                for y in range(h):
                    c=raw[co+y]
                    px[x,y]=(0,0,0,0) if c==255 else (*self.pal[c],255)
            self._p[ts+i]=img

    def tex(self, tid):
        if tid in self._t: return self._t[tid]
        img=self._p.get(tid)
        if img is None: return None
        # Ursina 8.3.0+ accepts PIL Image directly
        try:
            t=Texture(img)  # Modern Ursina
        except:
            t=Texture(image=img)  # Fallback
        self._t[tid]=t; return t

    def ph(self, rgb=(80,80,80)):
        if rgb in self._t: return self._t[rgb]
        img=Image.new('RGB',(64,64),rgb)
        try:
            t=Texture(img)  # Modern Ursina
        except:
            t=Texture(image=img)  # Fallback
        self._t[rgb]=t; return t

    def get(self, tid, rgb=(80,80,80)): return self.tex(tid) or self.ph(rgb)


# ══════════════════════════════════════════════════════════════════════════════
#  MAP PARSER  — Build Engine v5 beta (LameDuke, 37-byte sectors)
# ══════════════════════════════════════════════════════════════════════════════
class S:  # sector
    __slots__=['wp','wn','cz','fz','cs','fs','cp','csh','cpl','fp','fsh','fpl','vis','lt','ht']
    def __init__(self,*a):
        for s,v in zip(self.__slots__,a): setattr(self,s,v)

class W:  # wall
    __slots__=['x','y','p2','nw','ns','cs','pic','opic','sh','pl','xr','yr','xp','yp','lt','ht']
    def __init__(self,*a):
        for s,v in zip(self.__slots__,a): setattr(self,s,v)

class Sp: # sprite
    __slots__=['x','y','z','cs','pic','sh','pl','cl','xr','yr','xo','yo','sn','st','ang','own','xv','yv','zv','lt','ht','ex']
    def __init__(self,*a):
        for s,v in zip(self.__slots__,a): setattr(self,s,v)

class MD:
    def __init__(self): self.ver=0; self.px=self.py=self.pz=0; self.pa=0; self.cs=0; self.sects=[]; self.walls=[]; self.sprs=[]

def parse_map(path: Path):
    try: data=path.read_bytes()
    except: return None
    m=MD(); o=0
    m.ver,=struct.unpack_from('<i',data,o); o+=4
    m.px,m.py,m.pz=struct.unpack_from('<3i',data,o); o+=12
    m.pa,=struct.unpack_from('<h',data,o); o+=2
    m.cs,=struct.unpack_from('<h',data,o); o+=2
    ns,=struct.unpack_from('<H',data,o); o+=2
    for _ in range(ns):
        if o+37>len(data): break
        s=data[o:o+37]; o+=37
        wp,wn=struct.unpack_from('<2h',s,0); cz,fz=struct.unpack_from('<2i',s,4)
        cs,fs=struct.unpack_from('<2h',s,12); cp,=struct.unpack_from('<h',s,16)
        csh=struct.unpack_from('<b',s,18)[0]; cpl=s[19]
        fp,=struct.unpack_from('<h',s,20); fsh=struct.unpack_from('<b',s,22)[0]; fpl=s[23]
        vis=s[24]; lt,ht=struct.unpack_from('<2h',s,31)
        m.sects.append(S(wp,wn,cz,fz,cs,fs,cp,csh,cpl,fp,fsh,fpl,vis,lt,ht))
    nw,=struct.unpack_from('<H',data,o); o+=2
    for _ in range(nw):
        if o+32>len(data): break
        w=data[o:o+32]; o+=32
        x,y=struct.unpack_from('<2i',w,0); p2,nw_,ns_=struct.unpack_from('<3h',w,8)
        cs,=struct.unpack_from('<h',w,14); pic,opic=struct.unpack_from('<2h',w,16)
        sh=struct.unpack_from('<b',w,20)[0]; pl=w[21]; xr,yr,xp,yp=w[22],w[23],w[24],w[25]
        lt,ht=struct.unpack_from('<2h',w,26)
        m.walls.append(W(x,y,p2,nw_,ns_,cs,pic,opic,sh,pl,xr,yr,xp,yp,lt,ht))
    nsp,=struct.unpack_from('<H',data,o); o+=2
    for _ in range(nsp):
        if o+44>len(data): break
        s=data[o:o+44]; o+=44
        x,y,z=struct.unpack_from('<3i',s,0); cs,pic=struct.unpack_from('<2h',s,12)
        sh=struct.unpack_from('<b',s,16)[0]; pl,cl=s[17],s[18]; xr,yr=s[20],s[21]
        xo=struct.unpack_from('<b',s,22)[0]; yo=struct.unpack_from('<b',s,23)[0]
        sn,st=struct.unpack_from('<2h',s,24); ang,own=struct.unpack_from('<2h',s,28)
        xv,yv,zv=struct.unpack_from('<3h',s,32); lt,ht,ex=struct.unpack_from('<3h',s,38)
        m.sprs.append(Sp(x,y,z,cs,pic,sh,pl,cl,xr,yr,xo,yo,sn,st,ang,own,xv,yv,zv,lt,ht,ex))
    print(f"[MAP] {path.name} v{m.ver} {len(m.sects)}s {len(m.walls)}w {len(m.sprs)}sp")
    return m

# ══════════════════════════════════════════════════════════════════════════════
#  MAP MESH
# ══════════════════════════════════════════════════════════════════════════════
DH = 3.0   # default wall height if sector z is bogus

class MapMesh:
    def __init__(self, md: MD, art: ArtLoader):
        self.md=md; self.art=art; self.E=[]; self.C=[]
        self._build()

    def _bx(self,v): return  v*BXY
    def _by(self,v): return -v*BXY
    def _bz(self,v): return -v*BZ

    def _sh(self, s):
        fy=self._bz(s.fz); cy=self._bz(s.cz)
        if abs(fy-cy)<0.05 or abs(fy-cy)>60: cy=fy+DH
        return fy,cy

    def _quad(self, verts, tex):
        v0,v1,v2,v3=[Vec3(*v) for v in verts]
        m=Mesh(vertices=[v0,v1,v2,v0,v2,v3],triangles=list(range(6)),
               uvs=[(0,0),(1,0),(1,1),(0,0),(1,1),(0,1)],mode='triangle')
        self.E.append(Entity(model=m,texture=tex,double_sided=True))

    def _fc(self, sec, floor):
        ws=[self.md.walls[sec.wp+i] for i in range(sec.wn)
            if sec.wp+i<len(self.md.walls)]
        if len(ws)<3: return
        fy,cy=self._sh(sec); y=fy if floor else cy
        pic=sec.fp if floor else sec.cp
        pts=[(self._bx(w.x),self._by(w.y)) for w in ws]
        cx=sum(p[0] for p in pts)/len(pts); cz=sum(p[1] for p in pts)/len(pts)
        n=len(pts); verts=[]; uvs=[]; us=0.02
        for i in range(n):
            x0,z0=pts[i]; x1,z1=pts[(i+1)%n]
            verts+=[Vec3(cx,y,cz),Vec3(x0,y,z0),Vec3(x1,y,z1)]
            uvs+=[(0.5,0.5),(cx*us,cz*us),(x1*us,z1*us)]
        tex=self.art.get(pic,(50,40,30) if floor else (40,40,60))
        m=Mesh(vertices=verts,triangles=list(range(len(verts))),uvs=uvs,mode='triangle')
        self.E.append(Entity(model=m,texture=tex,double_sided=True))
        if floor:
            ex=max(abs(p[0]-cx) for p in pts)*2; ez=max(abs(p[1]-cz) for p in pts)*2
            self.C.append(Entity(model='cube',position=Vec3(cx,y-.15,cz),
                                 scale=Vec3(max(.1,ex),.3,max(.1,ez)),
                                 visible=False,collider='box'))

    def _wall(self, w: W, sec: S):
        wp=self.md.walls[w.p2]
        x0,z0=self._bx(w.x),self._by(w.y); x1,z1=self._bx(wp.x),self._by(wp.y)
        fy,cy=self._sh(sec)
        if w.ns<0 or w.ns>=len(self.md.sects):
            tex=self.art.get(w.pic,(70,60,50))
            self._quad([(x0,fy,z0),(x1,fy,z1),(x1,cy,z1),(x0,cy,z0)],tex)
            mx=(x0+x1)/2; mz=(z0+z1)/2; my=(fy+cy)/2
            ln=max(.05,math.sqrt((x1-x0)**2+(z1-z0)**2)); ht=max(.05,abs(cy-fy))
            ag=math.degrees(math.atan2(z1-z0,x1-x0))
            self.C.append(Entity(model='cube',position=Vec3(mx,my,mz),rotation_y=-ag,
                                 scale=Vec3(ln,ht,.1),visible=False,collider='box'))
        else:
            ns=self.md.sects[w.ns]; nf,nc=self._sh(ns)
            if nf>fy+.05: self._quad([(x0,fy,z0),(x1,fy,z1),(x1,nf,z1),(x0,nf,z0)],self.art.get(w.pic,(60,50,40)))
            if nc<cy-.05:  self._quad([(x0,nc,z0),(x1,nc,z1),(x1,cy,z1),(x0,cy,z0)],self.art.get(w.opic or w.pic,(55,45,35)))

    def _build(self):
        done=set()
        for si,sec in enumerate(self.md.sects):
            if sec.wn<2 or sec.wp<0: continue
            if sec.wp+sec.wn>len(self.md.walls): continue
            if abs(self._bz(sec.fz))>100 or abs(self._bz(sec.cz))>100: continue
            self._fc(sec,True); self._fc(sec,False)
            for wi in range(sec.wn):
                idx=sec.wp+wi
                if idx>=len(self.md.walls): break
                w=self.md.walls[idx]
                if w.p2<0 or w.p2>=len(self.md.walls): continue
                key=(min(idx,w.nw),max(idx,w.nw))
                if w.nw>=0 and key in done: continue
                done.add(key); self._wall(w,sec)
        print(f"[MESH] {len(self.E)} ents {len(self.C)} cols")

    def spawn_pos(self):
        x=self._bx(self.md.px); z=self._by(self.md.py); y=0.
        if 0<=self.md.cs<len(self.md.sects):
            fy,_=self._sh(self.md.sects[self.md.cs]); y=fy+PH
        return Vec3(x,y,z)

    def spawn_ang(self): return -((self.md.pa%2048)/2048.)*360.

    def destroy_all(self):
        for e in self.E+self.C: destroy(e)
        self.E.clear(); self.C.clear()

# ══════════════════════════════════════════════════════════════════════════════
#  SPRITES / ENEMIES / ITEMS
# ══════════════════════════════════════════════════════════════════════════════
ITEMS = {
    TILE['SIXPAK']:('hp',25,(200,255,200)), TILE['AMMO']:('ammo',10,(255,230,100)),
    TILE['BATTERYAMMO']:('ammo',30,(255,200,50)), TILE['RPGAMMO']:('ammo',2,(255,150,50)),
    TILE['SHIELD']:('armor',50,(150,200,255)), TILE['AIRTANK']:('oxy',100,(100,200,255)),
    TILE['STEROIDS']:('speed',1,(255,100,255)), TILE['JETPACK']:('jp',1,(200,200,100)),
}
EN_TID = {TILE['FEMANOID']:'fem',TILE['MANDROID']:'man',490:'man',579:'drone',631:'drunk'}
EN_STAT = {
    'fem':  {'hp':20,'sp':1.8,'dm': 8,'rng': 8.,'col':(200,150,200)},
    'man':  {'hp':30,'sp':1.5,'dm':12,'rng':10.,'col':(150,200,150)},
    'drone':{'hp':15,'sp':3.0,'dm': 6,'rng':12.,'col':(200,200,100)},
    'drunk':{'hp':10,'sp':1.0,'dm': 4,'rng': 5.,'col':(200,150,100)},
}

class Enemy:
    def __init__(self, pos, kind, art, gm):
        self.kind=kind; self.alive=True; self.gm=gm
        st=EN_STAT.get(kind,EN_STAT['fem'])
        self.hp=st['hp']; self.sp=st['sp']; self.dm=st['dm']; self.rng=st['rng']
        tid={'fem':TILE['FEMANOID'],'man':TILE['MANDROID'],
             'drone':TILE['DRONE1'],'drunk':TILE['DRUNKGUY1']}.get(kind,TILE['FEMANOID'])
        tex=art.tex(tid); r,g,b=st['col']
        self.e=Entity(model='quad',position=pos,scale=.9,texture=tex,
                      color=color.white if tex else color.rgb(r,g,b),
                      billboard=True,collider='sphere')
        self._ac=random.uniform(1.,3.); self._fl=0.

    def damage(self,d):
        if not self.alive: return
        self.hp-=d; self._fl=.1
        if self.hp<=0: self.alive=False; self.e.color=color.rgb(180,50,50); invoke(destroy,self.e,delay=2.)

    def update(self,ppos,dt,gm):
        if not self.alive: return
        diff=ppos-self.e.position; dist=diff.length()
        if self._fl>0: self._fl-=dt; self.e.color=color.white if int(time.time()*20)%2 else color.red
        elif self.alive: self.e.color=color.white
        if 1.<dist<20.: mv=diff.normalized()*self.sp*dt; self.e.position+=Vec3(mv.x,0,mv.z)
        self._ac-=dt
        if self._ac<=0 and dist<self.rng:
            self._ac=random.uniform(1.5,3.); gm.hurt(random.randint(self.dm//2,self.dm))

    def destroy(self):
        if self.e: destroy(self.e)

class Sprites:
    def __init__(self,md,art,mesh,gm):
        self.md=md; self.art=art; self.mesh=mesh; self.gm=gm
        self.items=[]; self.enemies=[]
        for sp in md.sprs:
            x=mesh._bx(sp.x); z=mesh._by(sp.y); y=0.
            if 0<=sp.sn<len(md.sects): fy,_=mesh._sh(md.sects[sp.sn]); y=fy+.5
            pos=Vec3(x,y,z); pic=sp.pic&0xFFFF
            if pic in ITEMS:
                kd,vl,cl=ITEMS[pic]; tex=art.tex(pic)
                e=Entity(model='quad',position=pos,scale=.6,
                         color=color.rgb(*cl),texture=tex,billboard=True,
                         collider='sphere',name=f'item_{kd}_{vl}')
                e._ik=kd; e._iv=vl; self.items.append(e)
            elif pic in EN_TID:
                ang=-(sp.ang/2048.)*360.
                en=Enemy(pos,EN_TID[pic],art,gm); en.e.rotation_y=ang; self.enemies.append(en)
            elif pic==TILE['EXPLODINGBARREL']:
                e=Entity(model='cylinder',position=pos,scale=Vec3(.4,.8,.4),
                         texture=art.tex(pic),collider='box',name='barrel',color=color.rgb(180,100,60))
                e._health=30; self.items.append(e)
            elif 0<pic<2048:
                tex=art.tex(pic)
                if tex: self.items.append(Entity(model='quad',position=pos,scale=.5,texture=tex,billboard=True))

    def destroy_all(self):
        for e in self.items: destroy(e)
        for e in self.enemies: e.destroy()
        self.items.clear(); self.enemies.clear()

# ══════════════════════════════════════════════════════════════════════════════
#  AUDIO
# ══════════════════════════════════════════════════════════════════════════════
class Audio:
    def __init__(self,d):
        self._sfx={}; self._mid=[]; self._ok=False
        try:
            pygame.mixer.init(44100,-16,2,512); self._ok=True
            for f in d.glob('*.VOC'):
                try:
                    w=self._voc(f.read_bytes())
                    if w:
                        s=pygame.mixer.Sound(io.BytesIO(w)); s.set_volume(.5)
                        self._sfx[f.stem.lower()]=s
                except: pass
            self._mid=sorted(d.glob('*.MID'))+sorted(d.glob('*.mid'))
            print(f"[SFX] {len(self._sfx)} sfx, {len(self._mid)} midi")
        except Exception as e: print(f"[SFX] off: {e}")

    def _voc(self,data):
        if not data.startswith(b'Creative Voice File\x1a'): return None
        pcm=bytearray(); rate=8000; o=26
        while o<len(data):
            bt=data[o]; o+=1
            if bt==0: break
            if o+3>len(data): break
            sz=data[o]|(data[o+1]<<8)|(data[o+2]<<16); o+=3
            if bt==1 and sz>=2:
                rb=data[o]; o+=1; cd=data[o]; o+=1; sz-=2
                if cd==0: rate=1000000//(256-rb) if rb<256 else 8000; pcm.extend(data[o:o+sz])
                o+=sz
            elif bt==9 and sz>=12:
                rate=struct.unpack_from('<I',data,o)[0]; o+=8; sz-=12; pcm.extend(data[o:o+sz]); o+=sz
            else: o+=sz
        if not pcm: return None
        n=len(pcm)
        return bytes(b'RIFF'+struct.pack('<I',36+n)+b'WAVE'+b'fmt '
                     +struct.pack('<IHHIIHH',16,1,1,rate,rate,1,8)
                     +b'data'+struct.pack('<I',n))+bytes(pcm)

    def play(self,nm):
        if not self._ok: return
        s=self._sfx.get(nm.lower())
        if s:
            try: s.play()
            except: pass

    def music(self,i=0):
        if not self._ok or not self._mid: return
        try: pygame.mixer.music.load(str(self._mid[i%len(self._mid)])); pygame.mixer.music.set_volume(.35); pygame.mixer.music.play(-1)
        except: pass

    def stop(self):
        if not self._ok: return
        try: pygame.mixer.music.stop()
        except: pass

# ══════════════════════════════════════════════════════════════════════════════
#  WEAPON SYSTEM
# ══════════════════════════════════════════════════════════════════════════════
class Weapons:
    def __init__(self,audio):
        self.au=audio; self.cur=1; self._cd=0.
        self.ammo={'bullet':200,'battery':50,'grenade':10,'rpg':5}

    def fire(self,pp,pf,ens):
        w=WEAPONS[self.cur]
        if self._cd>0: return None
        at=w['ammo']
        if self.ammo.get(at,0)<=0: self.au.play('switch'); return 'OUT OF AMMO'
        self.ammo[at]-=1; self._cd=w['rate']; self.au.play(w['snd'])
        for en in ens:
            if not en.alive: continue
            d=en.e.position-pp; dist=d.length()
            if dist>w['rng'] or pf.dot(d.normalized())<.5: continue
            en.damage(w['dmg']); self.au.play('bodyblop')
            return f"HIT -{w['dmg']}HP"
        return None

    def update(self,dt): self._cd=max(0.,self._cd-dt)
    def switch(self,i):
        if 0<=i<len(WEAPONS): self.cur=i
    def pickup(self,at,v): self.ammo[at]=min(999,self.ammo.get(at,0)+v)

# ══════════════════════════════════════════════════════════════════════════════
#  HUD  (arcade — NO key hints, NO button labels)
# ══════════════════════════════════════════════════════════════════════════════
class HUD:
    def __init__(self,tl):
        self.tl=tl; self._mt=0.
        self._bar=Entity(parent=camera.ui,model='quad',scale=(2,.10),position=(0,-.47),color=color.rgba(0,0,0,200),z=-1)
        kw=dict(font='VeraMono.ttf',parent=camera.ui,z=-2)
        self.hp  =Text('♥100',position=(-.88,-.44),scale=1.3,color=color.rgb(255,80,80),**kw)
        self.arm =Text('◈000',position=(-.60,-.44),scale=1.3,color=color.rgb(100,180,255),**kw)
        self.wpn =Text('[PISTOL]',position=(-.20,-.44),scale=1.3,color=color.rgb(AR,AG,AB),**kw)
        self.amm =Text('●200',position=(.40,-.44),scale=1.3,color=color.rgb(AR,AG,AB),**kw)
        self.tmr =Text('',position=(.65,-.44),scale=1.3,color=color.rgb(255,100,100),**kw)
        self.lvl =Text('',position=(-.88,.46),scale=.9,color=color.rgb(AR,AG,AB),**kw)
        self.msg =Text('',position=(-.88,-.38),scale=1.0,color=color.rgb(200,255,150),**kw)
        self.xh  =Text('+',origin=(0,0),position=(0,0),scale=2.,color=color.rgb(AR,AG,AB),**kw)
        self._all=[self._bar,self.hp,self.arm,self.wpn,self.amm,self.tmr,self.lvl,self.msg,self.xh]

    def upd(self,hp,arm,wpn,amm,lvl,tl):
        self.hp.text=f'♥{hp:3d}'; self.arm.text=f'◈{arm:3d}'
        self.wpn.text=f'[{wpn.upper():<8}]'; self.amm.text=f'●{amm:3d}'
        self.lvl.text=lvl
        if self.tl>0:
            m,s=int(tl)//60,int(tl)%60; self.tmr.text=f'{m}:{s:02d}'
            self.tmr.color=color.red if tl<30 else color.rgb(255,200,100)

    def msg_show(self,t,d=2.5): self.msg.text=t; self._mt=d

    def tick(self,dt):
        if self._mt>0:
            self._mt-=dt
            if self._mt<=0: self.msg.text=''

    def destroy(self):
        for e in self._all: destroy(e)

# ══════════════════════════════════════════════════════════════════════════════
#  ROM / RAM CHECK  (MS-DOS style, real asset detection)
# ══════════════════════════════════════════════════════════════════════════════
class RomCheck:
    """
    Scans actual game files and reports results MS-DOS style.
    Matches the LameDuke startup screenshot style.
    """
    def __init__(self, game_dir: Path, on_done):
        self._done=False; self._t=0.; self._on=on_done; self._dur=4.0
        self._ents=[]; self._pool=[]; self._shown=0
        gd=game_dir

        # Build real check results
        art_count  = len(list(gd.glob('TILES*.ART')))
        map_count  = len(list(gd.glob('*.MAP')))
        voc_count  = len(list(gd.glob('*.VOC')))
        mid_count  = len(list(gd.glob('*.MID')))+len(list(gd.glob('*.mid')))
        pal_ok     = (gd/'PALETTE.DAT').exists()
        con_ok     = (gd/'GAME.CON').exists()
        tiles5_ok  = (gd/'TILES005.ART').exists() and (gd/'TILES005.ART').stat().st_size>0
        d3d_ver    = 'v1.3.95' if (gd/'D3D.EXE').exists() else 'NOT FOUND'
        ram_mb     = 32   # simulated
        xms_kb     = 8192

        self._lines = [
            # (text, progress_threshold, color_rgb)
            (f"DUKE DUKEM 3D Beta version 1.3.95 -- DO NOT DISTRIBUTE!!! That would be bad.", 0.00, (255,255,100)),
            ("",0.05,(200,200,200)),
            (f"Loading user stats...",                   0.06,(200,200,200)),
            (f"Init BootLeg CacheMaster...",             0.10,(200,200,200)),
            (f"Checking program integrety...",           0.14,(200,200,200)),
            ("",0.18,(200,200,200)),
            ("━━━━  ROM/RAM DIAGNOSTIC  ━━━━",          0.19,(AR,AG,AB)),
            (f"  Base memory (640K) ............. OK",   0.22,(100,255,100)),
            (f"  Extended (XMS {xms_kb}K) ........... OK",0.27,(100,255,100)),
            (f"  EMS memory ...................... OK",   0.31,(100,255,100)),
            (f"  VESA / Build Engine BIOS ........ OK",  0.35,(100,255,100)),
            (f"  ART tile banks ({art_count} files) ..... {'OK' if art_count>0 else 'MISSING!'}",
                                                          0.38,(100,255,100) if art_count>0 else (255,80,80)),
            (f"  MAP sector data ({map_count} maps) ...... {'OK' if map_count>0 else 'MISSING!'}",
                                                          0.42,(100,255,100) if map_count>0 else (255,80,80)),
            (f"  PALETTE.DAT (256 colors) ........ {'OK' if pal_ok else 'MISSING!'}",
                                                          0.46,(100,255,100) if pal_ok else (255,80,80)),
            (f"  TILES005.ART (effect tiles) ..... {'OK' if tiles5_ok else 'EMPTY (BUG-01)'}",
                                                          0.49,(100,255,100) if tiles5_ok else (255,180,50)),
            (f"  VOC sound effects ({voc_count} files) ... {'OK' if voc_count>0 else 'NONE'}",
                                                          0.52,(100,255,100) if voc_count>0 else (180,180,50)),
            (f"  MIDI music ({mid_count} tracks) ......... {'OK' if mid_count>0 else 'NONE'}",
                                                          0.55,(100,255,100) if mid_count>0 else (180,180,50)),
            (f"  CON script parser ............... {'OK' if con_ok else 'USING DEFAULTS'}",
                                                          0.58,(100,255,100) if con_ok else (255,180,50)),
            (f"  D3D.EXE ({d3d_ver}) ............ BYPASSED (Python engine)",
                                                          0.61,(180,180,50)),
            ("",0.64,(200,200,200)),
            ("Loading script...",                         0.65,(200,200,200)),
            ("   Compiling...",                           0.70,(200,200,200)),
            ("   Loading include file defs.con",          0.74,(200,200,200)),
            ("   Loading include file music.con",         0.77,(200,200,200)),
            ("  * Found 0 warning(s) and 0 error(s).",   0.80,(100,255,100)),
            ("   Total Lines:1764.",                      0.83,(200,200,200)),
            ("   Code Size:12432 bytes.",                 0.86,(200,200,200)),
            ("Init engine...",                            0.88,(200,200,200)),
            ("Checking for multiplayer...",               0.91,(200,200,200)),
            ("Loading art...",                            0.93,(200,200,200)),
            ("Init colorize/remaps...",                   0.95,(200,200,200)),
            ("Init sound FX...",                          0.97,(200,200,200)),
            ("Reading sounds...",                         1.00,(200,200,200)),
        ]

        self._bg=Entity(parent=camera.ui,model='quad',scale=(2,1.15),color=color.black,z=0)
        self._ents.append(self._bg)
        for i in range(len(self._lines)):
            t=Text(text='',position=(-0.97,.47-i*.048),scale=0.70,
                   font='VeraMono.ttf',parent=camera.ui,z=-1)
            self._pool.append(t); self._ents.append(t)
        # cursor
        self._cur=Entity(parent=camera.ui,model='quad',scale=(.012,.018),color=color.white,z=-1)
        self._ents.append(self._cur)

    def update(self,dt):
        if self._done: return
        self._t+=dt; prog=min(1.,self._t/self._dur)
        for i,(txt,thr,clr) in enumerate(self._lines):
            if prog>=thr and i>=self._shown:
                self._pool[i].text=txt; self._pool[i].color=color.rgb(*clr)
                self._shown=i+1
        if self._shown>0:
            cy=.47-(self._shown-1)*.048
            cx=-0.97+len(self._lines[self._shown-1][0])*0.0093
            self._cur.position=(cx,cy,0)
            self._cur.color=color.white if int(self._t*4)%2==0 else color.clear
        if self._t>=self._dur+0.6:
            self._done=True; self.destroy(); self._on()

    def destroy(self):
        for e in self._ents: destroy(e); self._ents.clear()

# ══════════════════════════════════════════════════════════════════════════════
#  ATTRACT MODE  — INSERT COIN + demo flythrough + welcome messages
# ══════════════════════════════════════════════════════════════════════════════
class Attract:
    def __init__(self,gd,art,audio,on_coin):
        self.gd=gd; self.art=art; self.audio=audio; self.on_coin=on_coin
        self._t=0.; self._ct=0.; self._ents=[]; self._txts=[]
        self._mesh=None; self._spr=None; self._dm_idx=0
        self._cam_pos=Vec3(0,2,0); self._cam_ang=0.; self._loaded=False

        bg=Entity(parent=camera.ui,model='quad',scale=(2,1.15),color=color.rgba(0,0,0,220),z=0)
        self._ents.append(bg)

        # CRT scanlines
        if ARCADE['scanlines']:
            for i in range(28):
                sl=Entity(parent=camera.ui,model='quad',scale=(2.1,.014),
                          position=(0,.52-i*.038),color=color.rgba(0,0,0,30),z=-.5)
                self._ents.append(sl)

        kw=dict(font='VeraMono.ttf',parent=camera.ui,z=-1)
        # TOP: Arcade name — large, pulsing amber
        self._aname=Text(ARCADE['arcade_name'],origin=(0,0),position=(0,.44),
                         scale=2.8,color=color.rgb(AR,AG,AB),**kw)
        self._txts.append(self._aname)
        # Cabinet ID
        self._cid=Text(ARCADE['cabinet_id'],origin=(0,0),position=(0,.34),
                       scale=.80,color=color.rgb(AR//2,AG//2,0),**kw)
        self._txts.append(self._cid)
        # WELCOME TOP
        self._wtop=Text(ARCADE['welcome_top'],origin=(0,0),position=(0,.26),
                        scale=1.1,color=color.rgb(255,255,200),**kw)
        self._txts.append(self._wtop)
        # Separator
        self._txts.append(Text('─'*52,origin=(0,0),position=(0,.20),
                                scale=.8,color=color.rgb(AR//3,AG//3,0),**kw))
        # Center: demo/title/hiscore info
        self._clbl=Text('',origin=(0,0),position=(0,.04),
                         scale=1.6,color=color.rgb(AR,AG,AB),**kw)
        self._txts.append(self._clbl)
        self._slbl=Text('',origin=(0,0),position=(0,-.08),
                         scale=.85,color=color.rgb(220,220,180),**kw)
        self._txts.append(self._slbl)
        # INSERT COIN — bottom, blinking
        self._coin=Text('★  INSERT COIN  ★',origin=(0,0),position=(0,-.28),
                         scale=1.9,color=color.rgb(255,255,50),**kw)
        self._txts.append(self._coin)
        # WELCOME BOTTOM
        self._wbot=Text(ARCADE['welcome_bottom'],origin=(0,0),position=(0,-.38),
                         scale=.95,color=color.rgb(200,180,100),**kw)
        self._txts.append(self._wbot)
        # Credit line
        self._txts.append(Text(
            'BUILD ENGINE © 1993-1997 KEN SILVERMAN  |  LAMEDUKE © 1994 3D REALMS',
            origin=(0,0),position=(0,-.49),scale=.58,color=color.rgb(70,50,0),**kw))
        self._load_demo()
        audio.music(0)

    def _load_demo(self):
        dm=ARCADE['demo_maps']
        mf=dm[self._dm_idx%len(dm)]
        mp=self.gd/mf
        if self._mesh: self._mesh.destroy_all(); self._mesh=None
        if self._spr:  self._spr.destroy_all();  self._spr=None
        if mp.exists():
            md=parse_map(mp)
            if md:
                self._mesh=MapMesh(md,self.art)
                class _G:
                    def hurt(self,d): pass
                self._spr=Sprites(md,self.art,self._mesh,_G())
                self._cam_pos=self._mesh.spawn_pos()
                self._cam_ang=self._mesh.spawn_ang()
                camera.position=self._cam_pos
                camera.rotation_y=self._cam_ang
                self._loaded=True

    def _demo_cam(self,dt):
        if not self._loaded: return
        self._cam_ang+=10.*dt
        mv=Vec3(math.sin(math.radians(self._cam_ang))*1.5*dt,0,
                math.cos(math.radians(self._cam_ang))*1.5*dt)
        self._cam_pos+=mv
        camera.position=self._cam_pos
        camera.rotation_y=self._cam_ang
        camera.rotation_x=math.sin(self._t*.35)*4.

    def update(self,dt,credits):
        self._t+=dt; self._ct+=dt
        # INSERT COIN blink
        self._coin.visible=int(self._t*1.8)%2==0
        if credits>0:
            self._coin.text=f'PRESS START  —  {credits} CREDIT{"S"if credits!=1 else""}'
            self._coin.color=color.rgb(100,255,100); self._coin.visible=True
        else:
            self._coin.text='★  INSERT COIN  ★'; self._coin.color=color.rgb(255,255,50)
        # Phase cycling
        plen=ARCADE['attract_demo_sec']
        pi=int(self._ct/plen)%len(ARCADE['attract_cycle'])
        phase=ARCADE['attract_cycle'][pi]
        ni=int(self._ct/plen)%len(ARCADE['demo_maps'])
        if phase=='demo':
            if ni!=self._dm_idx: self._dm_idx=ni; self._load_demo()
            self._clbl.text='— DEMO PLAY —'
            self._slbl.text=ARCADE['demo_maps'][self._dm_idx%len(ARCADE['demo_maps'])]
            self._demo_cam(dt)
        elif phase=='title':
            self._clbl.text='LAMEDUKE'
            self._slbl.text='Duke Nukem 3D Prototype  ·  Build Engine Beta  ·  Dec 30 1994'
            camera.position=Vec3(0,5,-8); camera.rotation=Vec3(20,0,0)
        elif phase=='hiscore':
            self._clbl.text='HIGH SCORES'
            self._slbl.text=('1ST  DUKE    999999\n'
                             '2ND  ACE     888888\n'
                             '3RD  PIGCOP  777777')
            camera.position=Vec3(0,5,-8); camera.rotation=Vec3(20,0,0)
        # Arcade name pulse
        p=.85+.15*math.sin(self._t*1.8)
        self._aname.color=color.rgb(int(AR*p),int(AG*p),int(AB*p))

    def destroy(self):
        if self._mesh: self._mesh.destroy_all()
        if self._spr:  self._spr.destroy_all()
        for e in self._ents: destroy(e)
        for t in self._txts: destroy(t)

# ══════════════════════════════════════════════════════════════════════════════
#  LEVEL SELECT
# ══════════════════════════════════════════════════════════════════════════════
class LvlSel:
    def __init__(self,gd,on_sel,on_back):
        self.gd=gd; self.on_sel=on_sel; self.on_back=on_back
        self._s=0; self._E=[]; self._T=[]
        kw=dict(font='VeraMono.ttf',parent=camera.ui,z=-1)
        bg=Entity(parent=camera.ui,model='quad',scale=(2,1.15),color=color.rgba(0,0,0,225),z=0)
        self._E.append(bg)
        self._T.append(Text(ARCADE['arcade_name'],origin=(0,0),position=(0,.46),scale=2.2,color=color.rgb(AR,AG,AB),**kw))
        self._T.append(Text('SELECT STAGE',origin=(0,0),position=(0,.37),scale=1.5,color=color.rgb(255,255,150),**kw))
        self._pool=[]
        for i in range(20):
            t=Text('',position=(-.92,.28-i*.044),scale=.82,color=color.rgb(AR,AG,AB),**kw)
            self._pool.append(t); self._T.append(t)
        self._render()

    def _render(self):
        vs=max(0,self._s-9); ve=min(len(LEVELS),vs+20)
        for i in range(20):
            if vs+i<ve:
                _,__,mf,nm=LEVELS[vs+i]; ok=(self.gd/mf).exists(); sel=vs+i==self._s
                pfx='▶ ' if sel else '  '
                st='' if ok else ' [--]'
                clr=(color.rgb(255,255,50) if sel else (color.rgb(AR,AG,AB) if ok else color.rgb(80,40,40)))
                self._pool[i].text=f'{pfx}{nm}{st}'; self._pool[i].color=clr
            else: self._pool[i].text=''

    def nav(self,d): self._s=(self._s+d)%len(LEVELS); self._render()

    def sel(self):
        _,__,mf,___=LEVELS[self._s]
        if (self.gd/mf).exists(): self.on_sel(mf)

    def destroy(self):
        for e in self._E: destroy(e)
        for t in self._T: destroy(t)

# ══════════════════════════════════════════════════════════════════════════════
#  GAME OVER
# ══════════════════════════════════════════════════════════════════════════════
class GameOver:
    def __init__(self,kills,elapsed,on_done):
        self._t=0.; self._dur=8.; self.on_done=on_done; self._E=[]
        kw=dict(font='VeraMono.ttf',parent=camera.ui,z=-1)
        bg=Entity(parent=camera.ui,model='quad',scale=(2,1.15),color=color.rgba(0,0,0,225),z=0)
        self._E.append(bg)
        for txt,pos,sc,clr in [
            (ARCADE['arcade_name'],                 (0,.44),2.0,color.rgb(AR,AG,AB)),
            ('GAME  OVER',                           (0,.20),4.5,color.rgb(255,40,40)),
            (f'ENEMIES DESTROYED: {kills}',          (0,-.02),1.2,color.rgb(255,200,50)),
            (f'TIME: {int(elapsed)//60}:{int(elapsed)%60:02d}',
                                                     (0,-.12),1.2,color.rgb(255,200,50)),
            ('THANK YOU FOR PLAYING',                (0,-.26),1.0,color.rgb(200,200,200)),
            (ARCADE['welcome_bottom'],               (0,-.40),.9,color.rgb(160,130,80)),
        ]:
            t=Text(text=txt,origin=(0,0),position=pos,scale=sc,color=clr,**kw)
            self._E.append(t)

    def update(self,dt):
        self._t+=dt
        if self._t>=self._dur: self.destroy(); self.on_done()

    def destroy(self):
        for e in self._E: destroy(e)

# ══════════════════════════════════════════════════════════════════════════════
#  GAME MANAGER  ★ extends Entity, NOT Ursina — fixes the @singleton crash ★
# ══════════════════════════════════════════════════════════════════════════════
class GameManager(Entity):
    """
    FIX-01: Extends Entity, not Ursina.
    Ursina uses a @singleton decorator that forbids subclassing since v5.
    The correct pattern is: app=Ursina()  +  gm=GameManager(Entity)
    """
    def __init__(self, gd: Path):
        super().__init__(ignore_paused=True, eternal=True)
        self.gd  = gd
        self.pal = load_palette(gd)
        self.art = ArtLoader(gd, self.pal)
        self.au  = Audio(gd)

        # State machine
        self._st  = 'romcheck'
        self._cr  = ARCADE.get('starting_credits', 0)
        self._kills=0; self._elapsed=0.
        self._hp=100; self._arm=0; self._jp=False
        self._jp_on=False   # FIX-02: explicit bool flag for jetpack
        self._tl=float(ARCADE['time_limit_sec'])
        self._mname=''; self._lname=''; self._midx=0

        # Sub-objects
        self._rc=None; self._att=None; self._lvl=None
        self._hud=None; self._go=None
        self._mesh=None; self._spr=None
        self._plr=None; self._wpn=None

        # Scene
        scene.fog_color=color.rgb(10,8,12); scene.fog_density=0.05
        AmbientLight(color=color.rgba(60,50,80,255))
        dl=DirectionalLight(); dl.look_at(Vec3(1,-1,1))
        Sky(color=color.rgba(8,8,15,255))
        mouse.locked=False

        self._rc=RomCheck(gd, self._to_attract)

    # ── State transitions ──────────────────────────────────────────────────
    def _to_attract(self):
        self._st='attract'
        self._att=Attract(self.gd,self.art,self.au,None)
        mouse.locked=False; camera.rotation=Vec3(0,0,0)

    def _coin(self):
        self._cr+=ARCADE['credits_per_coin']; self.au.play('clipin')

    def _to_lvlsel(self):
        self._st='lvlsel'
        if self._att: self._att.destroy(); self._att=None
        self._lvl=LvlSel(self.gd,self._start,lambda:(self._lvl.destroy(),setattr(self,'_lvl',None),self._to_attract()).__class__.__call__(self._lvl.destroy()) or self._to_attract())
        mouse.locked=False

    def _to_lvlsel_clean(self):
        self._st='lvlsel'
        if self._att: self._att.destroy(); self._att=None
        self._lvl=LvlSel(self.gd, self._start, self._to_attract)
        mouse.locked=False

    def _start(self, mf):
        if self._cr<=0: return
        self._cr-=1
        if self._lvl: self._lvl.destroy(); self._lvl=None
        if self._att: self._att.destroy(); self._att=None
        self._st='loading'; self._mname=mf
        lt=Text(f'LOADING  {mf}...',origin=(0,0),scale=2.,color=color.rgb(AR,AG,AB),font='VeraMono.ttf',parent=camera.ui)
        invoke(self._do_load,mf,lt,delay=.05)

    def _do_load(self,mf,lt):
        destroy(lt)
        path=self.gd/mf
        if not path.exists(): self._to_attract(); return
        md=parse_map(path)
        if not md: self._to_attract(); return
        self._mesh=MapMesh(md,self.art)
        self._wpn=Weapons(self.au)
        self._spr=Sprites(md,self.art,self._mesh,self)
        sp=self._mesh.spawn_pos(); ag=self._mesh.spawn_ang()
        if self._plr: destroy(self._plr); self._plr=None
        self._plr=FirstPersonController(position=sp,speed=4.,height=PH,
                                        mouse_sensitivity=Vec2(60,60),
                                        jump_height=2.,gravity=.8)
        self._plr.rotation_y=ag
        camera.clip_plane_near=.05; camera.fov=90
        self._hp=100; self._arm=0; self._jp=False; self._jp_on=False
        self._kills=0; self._elapsed=0.
        self._tl=float(ARCADE['time_limit_sec'])
        for _,__,f,n in LEVELS:
            if f.upper()==mf.upper(): self._lname=n; break
        else: self._lname=mf.replace('.MAP','')
        for i,(_,__,f,___) in enumerate(LEVELS):
            if f.upper()==mf.upper(): self._midx=i%6; break
        self._hud=HUD(ARCADE['time_limit_sec'])
        self.au.music(self._midx)
        mouse.locked=True; self._st='playing'

    def _to_gameover(self):
        self._st='gameover'
        if self._hud: self._hud.destroy(); self._hud=None
        self._clean()
        mouse.locked=False
        self._go=GameOver(self._kills,self._elapsed,self._to_attract)

    def _clean(self):
        if self._mesh: self._mesh.destroy_all(); self._mesh=None
        if self._spr:  self._spr.destroy_all();  self._spr=None
        if self._plr:  destroy(self._plr);       self._plr=None
        self._wpn=None; self.au.stop()

    # ── Frame update ───────────────────────────────────────────────────────
    def update(self):
        dt=time.dt
        if   self._st=='romcheck' and self._rc:  self._rc.update(dt)
        elif self._st=='attract'  and self._att: self._att.update(dt,self._cr)
        elif self._st=='playing':                self._tick(dt)
        elif self._st=='gameover' and self._go:  self._go.update(dt)

    def _tick(self,dt):
        if not self._plr or not self._wpn: return
        self._elapsed+=dt; self._wpn.update(dt)
        # Time limit countdown
        if ARCADE['time_limit_sec']>0:
            self._tl-=dt
            if self._tl<=0: self._to_gameover(); return
        # Enemy AI
        pp=self._plr.position
        if self._spr:
            for en in self._spr.enemies: en.update(pp,dt,self)
            # Item pickup
            for item in list(self._spr.items):
                if not item or not item.enabled: continue
                if (item.position-pp).length()<1.: self._pickup(item)
        # Kill count
        if self._spr: self._kills=sum(1 for e in self._spr.enemies if not e.alive)
        # HUD
        if self._hud:
            w=WEAPONS[self._wpn.cur]; am=self._wpn.ammo.get(w['ammo'],0)
            self._hud.upd(max(0,self._hp),self._arm,w['name'],am,self._lname,self._tl)
            self._hud.tick(dt)

    def _pickup(self,item):
        nm=item.name
        if   nm.startswith('item_hp'):    self._hp=min(200,self._hp+item._iv); self.au.play('getweapn'); self._hud and self._hud.msg_show(f'+{item._iv} HEALTH')
        elif nm.startswith('item_ammo'):  self._wpn.pickup('bullet',item._iv); self.au.play('getweapn')
        elif nm.startswith('item_armor'): self._arm=min(100,self._arm+item._iv); self.au.play('getweapn')
        elif nm.startswith('item_jp'):    self._jp=True; self._hud and self._hud.msg_show('JETPACK FOUND!')
        elif nm.startswith('item_speed'): self._plr.speed=8. if self._plr else 8.
        else: return
        if self._spr and item in self._spr.items: self._spr.items.remove(item)
        destroy(item)

    # ── Called by enemies ──────────────────────────────────────────────────
    def hurt(self, dmg):
        if self._st!='playing': return
        if self._arm>0:
            ab=min(self._arm,dmg//2); self._arm-=ab; dmg-=ab
        self._hp-=dmg; self.au.play('land')
        if self._hud: self._hud.msg_show(f'HIT  -{dmg}HP')
        if self._hp<=0: self._to_gameover()

    # ── Input ──────────────────────────────────────────────────────────────
    def input(self, key):
        s=self._st
        if s in ('romcheck','attract'):
            # 5 or C = insert coin;  1 or Enter = start (if credits)
            if key in ('5','c'): self._coin()
            elif key=='1' and self._cr>0: self._to_lvlsel_clean()
            elif key=='enter' and self._cr>0: self._to_lvlsel_clean()

        elif s=='lvlsel' and self._lvl:
            if key in ('up arrow','w'):    self._lvl.nav(-1)
            elif key in ('down arrow','s'):self._lvl.nav(1)
            elif key in ('1','enter'):     self._lvl.sel()
            elif key=='escape':
                self._lvl.destroy(); self._lvl=None; self._to_attract()

        elif s=='playing':
            for i in range(5):
                if key==str(i+1): self._wpn and self._wpn.switch(i)
            if key=='left mouse button' and self._plr and self._wpn:
                ens=self._spr.enemies if self._spr else []
                msg=self._wpn.fire(self._plr.position,self._plr.forward,ens)
                if msg and self._hud: self._hud.msg_show(msg)
            elif key=='escape':
                self.au.stop(); self._clean()
                if self._hud: self._hud.destroy(); self._hud=None
                self._hp=100; self._arm=0; self._to_attract()
            elif key=='f' and self._jp:
                # FIX-02: use bool flag, not float comparison
                self._jp_on=not self._jp_on
                if self._plr: self._plr.gravity=0. if self._jp_on else .8
                if self._hud: self._hud.msg_show('JETPACK ON' if self._jp_on else 'JETPACK OFF')

        elif s=='gameover':
            if key in ('enter','space','1','5','c'):
                if self._go: self._go.destroy(); self._go=None
                self._to_attract()

# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
def find_game_dir():
    if len(sys.argv)>1:
        p=Path(sys.argv[1])
        if p.is_dir(): return p
    for p in [Path('.'),Path(__file__).parent,
              Path.home()/'LameDuke',Path('C:/Games/LameDuke')]:
        if p.is_dir() and ((p/'D3D.EXE').exists() or (p/'TILES000.ART').exists()):
            return p
    print("Usage: python lameduke_engine.py <lameduke_folder>")
    sys.exit(1)

if __name__=='__main__':
    gd=find_game_dir()
    print(f"[INIT] LameDuke Arcade Engine v3.0  |  {gd}")

    # ══════════════════════════════════════════════════════════
    #  CORRECT URSINA USAGE — create app instance, do NOT subclass
    #  class LameDukeGame(Ursina) → CRASH (singleton decorator)
    #  app = Ursina() + GameManager(Entity) → CORRECT
    # ══════════════════════════════════════════════════════════
    app = Ursina(
        title='LAMEDUKE ARCADE ENGINE v3.0',
        fullscreen=False,
        development_mode=False,
        borderless=False,
    )
    window.fps_counter.enabled=True
    window.exit_button.visible=False

    gm=GameManager(gd)
    app.run()
