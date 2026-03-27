#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  LAMEDUKE ENGINE  —  Modern Python/Ursina Source Port               ║
║  Duke Nukem 3D Prototype (Build Engine Beta, December 30, 1994)     ║
║                                                                      ║
║  Reads original LameDuke game data files:                           ║
║    TILES*.ART  → real textures with original VGA palette            ║
║    *.MAP       → Build Engine sector/wall/sprite geometry           ║
║    *.VOC       → Sound effects (Creative VOC format)                ║
║    *.MID       → Music (MIDI playback)                              ║
║    DEFS.CON    → Tile/actor definitions                             ║
║    PALETTE.DAT → VGA palette (256 colors, 6-bit)                   ║
║                                                                      ║
║  Features:                                                           ║
║    • Real Build Engine MAP → 3D Ursina geometry conversion         ║
║    • Sector/wall/portal reconstruction                              ║
║    • Original tile textures applied to walls/floors/ceilings        ║
║    • FPS controller with Build Engine feel                          ║
║    • 5 weapons (Tazer, Pistol, Chaingun, Grenade, RPG)             ║
║    • 3 enemy types (Femanoid, Mandroid, Troop)                     ║
║    • Interactive sprites (doors, items, pickups)                    ║
║    • VOC sound effects                                              ║
║    • MIDI music                                                     ║
║    • Amber CRT main menu & HUD                                      ║
║    • Level selector (all 31 maps)                                   ║
║    • Jetpack, steroids, armor items                                 ║
║                                                                      ║
║  Build Engine & Tools © 1993-1997 Ken Silverman                     ║
║  LameDuke © 1994-1997 3D Realms / Apogee Software                  ║
╚══════════════════════════════════════════════════════════════════════╝

Requirements:
    pip install ursina pillow pygame

Usage:
    python lameduke_engine.py [path/to/lameduke/folder]
    python lameduke_engine.py          # prompts for folder

Compile to EXE:
    pip install pyinstaller
    pyinstaller --onefile --windowed --name LameDuke lameduke_engine.py
"""

import sys, os, struct, math, time, random, glob, io, re, json, traceback
from pathlib import Path
from collections import defaultdict

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

# ─── Check dependencies ───────────────────────────────────────────────────────
def check_deps():
    missing = []
    for mod in ['ursina','PIL','pygame']:
        try: __import__(mod)
        except ImportError: missing.append(mod)
    if missing:
        print(f"Missing: {', '.join(missing)}")
        print(f"Install: pip install {' '.join(missing)}")
        sys.exit(1)
check_deps()

from PIL import Image
import pygame
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
from ursina.shaders import lit_with_shadows_shader

# ═══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS — Build Engine tile IDs from DEFS.CON
# ═══════════════════════════════════════════════════════════════════════════════
TILE = {
    'MUSICANDSFX':5, 'ACTIVATOR':31, 'TOUCHPLATE':32, 'LOCATORS':34,
    'SECTOREFFECTOR':175, 'RADIUSEXPLOSION':46, 'WATERTILE':49,
    'SEENINE':57, 'COKE':60, 'GLASS':179, 'VIEWSCREEN':180, 'HYDRENT':181,
    'SHOTSPARK1':191, 'LASERSITE':214, 'WATERBUBBLE':215, 'FAN':217,
    'BAT':247, 'CAMERA1':265, 'APLAYER':283, 'BOLT1':305,
    'BUTTON1':380, 'PARKINGMETER':381, 'BULLET':389, 'FEMANOID':408,
    'MAINMENU':481, 'TITLE':482, 'BLOOD':488, 'MANDROID':490,
    'RPG':563, 'DRONE1':579, 'REACTOR':620, 'EXPLODINGBARREL':627,
    'DRUNKGUY1':631, 'HEAVYHBOMB':721, 'SIXPAK':722, 'AMMO':723,
    'STEROIDS':724, 'SHIELD':726, 'AIRTANK':727, 'JETPACK':728,
    'RPGAMMO':1119, 'BATTERYAMMO':1120, 'OOZ':1122,
}

# Build Engine coordinate scale factors
# Build world coords → Ursina coords
BUILD_SCALE_XY = 1.0 / 512.0   # horizontal: 512 build units = 1 Ursina unit
BUILD_SCALE_Z  = 1.0 / 4096.0  # vertical: bigger divisor (z is 16× finer)

# Player height above floor
PLAYER_HEIGHT = 0.9

# ═══════════════════════════════════════════════════════════════════════════════
#  PALETTE LOADER
# ═══════════════════════════════════════════════════════════════════════════════
def load_palette(game_dir: Path) -> list:
    """Load VGA 6-bit palette from PALETTE.DAT → list of 256 (R,G,B) tuples."""
    path = game_dir / 'PALETTE.DAT'
    if not path.exists():
        # Fallback: grayscale
        return [(i,i,i) for i in range(256)]
    raw = path.read_bytes()
    pal = []
    for i in range(256):
        r = min(255, raw[i*3+0] * 4)
        g = min(255, raw[i*3+1] * 4)
        b = min(255, raw[i*3+2] * 4)
        pal.append((r, g, b))
    return pal

# ═══════════════════════════════════════════════════════════════════════════════
#  ART LOADER — Build Engine TILES*.ART format
# ═══════════════════════════════════════════════════════════════════════════════
class ArtLoader:
    """
    Parses Build Engine TILES*.ART files.
    Tiles are stored column-major (x varies slowest).
    Pixel 255 = transparent.
    """
    def __init__(self, game_dir: Path, palette: list):
        self.game_dir = game_dir
        self.palette  = palette
        self._tiles: dict[int, Image.Image] = {}  # tile_id -> PIL Image
        self._tex_cache: dict[int, Texture] = {}   # tile_id -> Ursina Texture
        self._load_all()

    def _load_all(self):
        for art_path in sorted(self.game_dir.glob('TILES*.ART')):
            self._parse_art(art_path)
        print(f"[ART] Loaded {len(self._tiles)} tiles from {self.game_dir}")

    def _parse_art(self, path: Path):
        data = path.read_bytes()
        if len(data) < 16:
            return
        ver, ntiles, tilestart, tileend = struct.unpack_from('<4i', data, 0)
        count = tileend - tilestart + 1
        if count <= 0 or count > 8192:
            return
        off = 16
        # Tile dimensions
        xsizes = list(struct.unpack_from(f'<{count}H', data, off)); off += count * 2
        ysizes = list(struct.unpack_from(f'<{count}H', data, off)); off += count * 2
        # Animation data (skip)
        off += count * 4

        pal = self.palette
        for i in range(count):
            w, h = xsizes[i], ysizes[i]
            if w == 0 or h == 0 or w > 2048 or h > 2048:
                continue
            sz = w * h
            if off + sz > len(data):
                break
            raw = data[off:off + sz]; off += sz
            img = Image.new('RGBA', (w, h))
            px  = img.load()
            for x in range(w):
                col_off = x * h
                for y in range(h):
                    idx = raw[col_off + y]
                    if idx == 255:
                        px[x, y] = (0, 0, 0, 0)
                    else:
                        r, g, b = pal[idx]
                        px[x, y] = (r, g, b, 255)
            self._tiles[tilestart + i] = img

    def get_pil(self, tile_id: int) -> Image.Image | None:
        return self._tiles.get(tile_id)

    def get_texture(self, tile_id: int) -> Texture | None:
        if tile_id in self._tex_cache:
            return self._tex_cache[tile_id]
        img = self._tiles.get(tile_id)
        if img is None:
            return None
        # Convert PIL -> Ursina Texture
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        tex = Texture(PIL_image=Image.open(buf))
        self._tex_cache[tile_id] = tex
        return tex

    def get_or_placeholder(self, tile_id: int, color=(80,80,80)) -> Texture:
        tex = self.get_texture(tile_id)
        if tex:
            return tex
        # Generate a solid-color placeholder
        if ('placeholder', tile_id) not in self._tex_cache:
            img = Image.new('RGB', (64, 64), color)
            buf = io.BytesIO(); img.save(buf, 'PNG'); buf.seek(0)
            self._tex_cache[('placeholder', tile_id)] = Texture(PIL_image=Image.open(buf))
        return self._tex_cache[('placeholder', tile_id)]

# ═══════════════════════════════════════════════════════════════════════════════
#  MAP PARSER — Build Engine MAP v5 format
# ═══════════════════════════════════════════════════════════════════════════════
class BuildSector:
    __slots__ = ['wallptr','wallnum','cz','fz','cstat','fstat',
                 'cpic','cshade','cpal','fpic','fshade','fpal',
                 'visibility','lotag','hitag']
    def __init__(self, *args):
        (self.wallptr, self.wallnum, self.cz, self.fz,
         self.cstat, self.fstat, self.cpic, self.cshade, self.cpal,
         self.fpic, self.fshade, self.fpal, self.visibility,
         self.lotag, self.hitag) = args

class BuildWall:
    __slots__ = ['x','y','point2','nextwall','nextsect','cstat',
                 'picnum','overpic','shade','pal','xrep','yrep',
                 'xpan','ypan','lotag','hitag']
    def __init__(self, *args):
        (self.x, self.y, self.point2, self.nextwall, self.nextsect,
         self.cstat, self.picnum, self.overpic, self.shade, self.pal,
         self.xrep, self.yrep, self.xpan, self.ypan,
         self.lotag, self.hitag) = args

class BuildSprite:
    __slots__ = ['x','y','z','cstat','picnum','shade','pal',
                 'clipdist','xrep','yrep','xoff','yoff',
                 'sectnum','statnum','ang','owner',
                 'xvel','yvel','zvel','lotag','hitag','extra']
    def __init__(self, *args):
        for slot, val in zip(BuildSprite.__slots__, args):
            setattr(self, slot, val)

class MapData:
    def __init__(self):
        self.version = 0
        self.px = self.py = self.pz = 0
        self.pang = 0
        self.cursect = 0
        self.sectors: list[BuildSector] = []
        self.walls:   list[BuildWall]   = []
        self.sprites: list[BuildSprite] = []

def parse_map(path: Path) -> MapData | None:
    """Parse Build Engine MAP v5 file."""
    try:
        data = path.read_bytes()
    except Exception as e:
        print(f"[MAP] Cannot read {path}: {e}")
        return None

    m = MapData()
    off = 0
    m.version,         = struct.unpack_from('<i', data, off); off += 4
    m.px, m.py, m.pz  = struct.unpack_from('<3i', data, off); off += 12
    m.pang,            = struct.unpack_from('<h', data, off); off += 2
    m.cursect,         = struct.unpack_from('<h', data, off); off += 2
    num_sectors,       = struct.unpack_from('<H', data, off); off += 2

    # Sector layout (37 bytes, LameDuke v5 beta)
    SECT_SZ = 37
    for _ in range(num_sectors):
        if off + SECT_SZ > len(data): break
        s = data[off:off+SECT_SZ]; off += SECT_SZ
        wallptr, wallnum   = struct.unpack_from('<2h', s, 0)
        cz, fz             = struct.unpack_from('<2i', s, 4)
        cstat, fstat       = struct.unpack_from('<2h', s, 12)
        cpic,              = struct.unpack_from('<h',  s, 16)
        cshade             = struct.unpack_from('<b',  s, 18)[0]
        cpal               = s[19]
        fpic,              = struct.unpack_from('<h',  s, 20)
        fshade             = struct.unpack_from('<b',  s, 22)[0]
        fpal               = s[23]
        visibility         = s[24]
        lotag, hitag       = struct.unpack_from('<2h', s, 31)
        m.sectors.append(BuildSector(
            wallptr, wallnum, cz, fz, cstat, fstat,
            cpic, cshade, cpal, fpic, fshade, fpal,
            visibility, lotag, hitag
        ))

    num_walls, = struct.unpack_from('<H', data, off); off += 2

    # Wall layout (32 bytes)
    WALL_SZ = 32
    for _ in range(num_walls):
        if off + WALL_SZ > len(data): break
        w = data[off:off+WALL_SZ]; off += WALL_SZ
        x, y               = struct.unpack_from('<2i', w, 0)
        point2, nextwall, nextsect = struct.unpack_from('<3h', w, 8)
        cstat,             = struct.unpack_from('<h',  w, 14)
        picnum, overpic    = struct.unpack_from('<2h', w, 16)
        shade              = struct.unpack_from('<b',  w, 20)[0]
        pal                = w[21]
        xrep, yrep, xpan, ypan = w[22], w[23], w[24], w[25]
        lotag, hitag       = struct.unpack_from('<2h', w, 26)
        m.walls.append(BuildWall(
            x, y, point2, nextwall, nextsect, cstat,
            picnum, overpic, shade, pal, xrep, yrep, xpan, ypan, lotag, hitag
        ))

    num_sprites, = struct.unpack_from('<H', data, off); off += 2

    # Sprite layout (44 bytes)
    SPRT_SZ = 44
    for _ in range(num_sprites):
        if off + SPRT_SZ > len(data): break
        s = data[off:off+SPRT_SZ]; off += SPRT_SZ
        x, y, z            = struct.unpack_from('<3i', s, 0)
        cstat, picnum      = struct.unpack_from('<2h', s, 12)
        shade              = struct.unpack_from('<b',  s, 16)[0]
        pal, clipdist      = s[17], s[18]
        xrep, yrep         = s[20], s[21]
        xoff               = struct.unpack_from('<b',  s, 22)[0]
        yoff               = struct.unpack_from('<b',  s, 23)[0]
        sectnum, statnum   = struct.unpack_from('<2h', s, 24)
        ang, owner         = struct.unpack_from('<2h', s, 28)
        xvel, yvel, zvel   = struct.unpack_from('<3h', s, 32)
        lotag, hitag, extra= struct.unpack_from('<3h', s, 38)
        m.sprites.append(BuildSprite(
            x, y, z, cstat, picnum, shade, pal, clipdist,
            xrep, yrep, xoff, yoff, sectnum, statnum, ang, owner,
            xvel, yvel, zvel, lotag, hitag, extra
        ))

    print(f"[MAP] {path.name}: v{m.version}  {len(m.sectors)} sectors  "
          f"{len(m.walls)} walls  {len(m.sprites)} sprites")
    return m

# ═══════════════════════════════════════════════════════════════════════════════
#  GEOMETRY BUILDER — Build Engine MAP → Ursina 3D mesh
# ═══════════════════════════════════════════════════════════════════════════════
class BuildMapMesh:
    """
    Converts a Build Engine MAP into Ursina Entity geometry.

    Build Engine coordinate system → Ursina:
      Build X → Ursina X  (× BUILD_SCALE_XY)
      Build Y → Ursina Z  (× BUILD_SCALE_XY, negated for handedness)
      Build Z → Ursina Y  (× BUILD_SCALE_Z, negated: Build Z goes DOWN)
    """

    WALL_HEIGHT_DEFAULT = 3.0   # Ursina units, used when z is unreliable

    def __init__(self, map_data: MapData, art: ArtLoader):
        self.md  = map_data
        self.art = art
        self.entities: list[Entity] = []
        self._collision_boxes: list[Entity] = []
        self._build()

    def _bx(self, bx): return  bx * BUILD_SCALE_XY
    def _by(self, by): return -by * BUILD_SCALE_XY   # negate Y for Ursina Z
    def _bz(self, bz): return -bz * BUILD_SCALE_Z    # negate Z (Build down=+)

    def _sector_heights(self, sect: BuildSector):
        """Return (floor_y, ceil_y) in Ursina Y coordinates."""
        # Build Z goes down, fz > 0 means below reference plane
        fy = self._bz(sect.fz)
        cy = self._bz(sect.cz)
        # Sanity clamp: avoid degenerate/corrupt sectors
        if abs(fy - cy) < 0.05 or abs(fy - cy) > 60:
            cy = fy + self.WALL_HEIGHT_DEFAULT
        return fy, cy   # floor y, ceiling y (ceil > floor)

    def _make_quad(self, verts, tex, name="wall"):
        """Create a quad entity from 4 3D vertices."""
        v0, v1, v2, v3 = [Vec3(*v) for v in verts]
        # Two triangles: (0,1,2) and (0,2,3)
        mesh = Mesh(
            vertices=[v0, v1, v2, v0, v2, v3],
            triangles=list(range(6)),
            uvs=[(0,0),(1,0),(1,1),(0,0),(1,1),(0,1)],
            mode='triangle',
        )
        e = Entity(model=mesh, texture=tex, double_sided=True,
                   collider=None)
        self.entities.append(e)
        return e

    def _make_floor_ceiling(self, sect_idx: int, sect: BuildSector,
                             is_floor: bool):
        """Build a polygon mesh for a floor or ceiling."""
        # Collect all walls in this sector
        walls_in_sect = []
        wp = sect.wallptr
        for i in range(sect.wallnum):
            if wp + i < len(self.md.walls):
                walls_in_sect.append(self.md.walls[wp + i])

        if len(walls_in_sect) < 3:
            return

        floor_y, ceil_y = self._sector_heights(sect)
        y = floor_y if is_floor else ceil_y
        pic = sect.fpic if is_floor else sect.cpic

        # Build polygon vertices (XZ plane at height Y)
        pts_xz = []
        for w in walls_in_sect:
            pts_xz.append((self._bx(w.x), self._by(w.y)))

        # Simple fan triangulation from centroid
        cx = sum(p[0] for p in pts_xz) / len(pts_xz)
        cz = sum(p[1] for p in pts_xz) / len(pts_xz)
        n  = len(pts_xz)

        verts = []
        uvs   = []
        uv_scale = 0.02

        for i in range(n):
            x0, z0 = pts_xz[i]
            x1, z1 = pts_xz[(i+1) % n]
            verts += [Vec3(cx, y, cz), Vec3(x0, y, z0), Vec3(x1, y, z1)]
            uvs   += [(0.5, 0.5),
                      (cx*uv_scale, cz*uv_scale),
                      (x1*uv_scale, z1*uv_scale)]

        if not verts:
            return

        tex = self.art.get_or_placeholder(pic,
              color=(40,40,60) if not is_floor else (50,40,30))
        mesh = Mesh(vertices=verts, triangles=list(range(len(verts))),
                    uvs=uvs, mode='triangle')
        e = Entity(model=mesh, texture=tex, double_sided=True, collider=None)
        self.entities.append(e)

        # Collision: add an invisible box at floor level
        if is_floor:
            extent_x = max(abs(p[0]-cx) for p in pts_xz) * 2
            extent_z = max(abs(p[1]-cz) for p in pts_xz) * 2
            box = Entity(
                model='cube',
                position=Vec3(cx, y - 0.15, cz),
                scale=Vec3(max(0.1, extent_x), 0.3, max(0.1, extent_z)),
                visible=False,
                collider='box',
                color=color.clear,
            )
            self._collision_boxes.append(box)

    def _make_wall_quad(self, w: BuildWall, sect: BuildSector):
        """Build a wall quad between two wall points."""
        wp = self.md.walls[w.point2]
        x0, z0 = self._bx(w.x),  self._by(w.y)
        x1, z1 = self._bx(wp.x), self._by(wp.y)

        floor_y, ceil_y = self._sector_heights(sect)

        # Solid wall
        if w.nextsect < 0 or w.nextsect >= len(self.md.sectors):
            verts = [
                (x0, floor_y, z0), (x1, floor_y, z1),
                (x1, ceil_y,  z1), (x0, ceil_y,  z0),
            ]
            tex = self.art.get_or_placeholder(w.picnum, color=(70,60,50))
            self._make_quad(verts, tex, "wall")
            # Wall collider
            mid_x = (x0 + x1) / 2
            mid_z = (z0 + z1) / 2
            mid_y = (floor_y + ceil_y) / 2
            length = max(0.05, math.sqrt((x1-x0)**2 + (z1-z0)**2))
            height = max(0.05, abs(ceil_y - floor_y))
            ang    = math.degrees(math.atan2(z1-z0, x1-x0))
            box = Entity(
                model='cube',
                position=Vec3(mid_x, mid_y, mid_z),
                rotation_y=-ang,
                scale=Vec3(length, height, 0.1),
                visible=False,
                collider='box',
                color=color.clear,
            )
            self._collision_boxes.append(box)
        else:
            # Portal wall: render step differences
            ns = self.md.sectors[w.nextsect]
            nf, nc = self._sector_heights(ns)
            # Lower step (below neighbour floor)
            if nf > floor_y + 0.05:
                verts = [
                    (x0, floor_y, z0), (x1, floor_y, z1),
                    (x1, nf, z1),      (x0, nf, z0),
                ]
                tex = self.art.get_or_placeholder(w.picnum, color=(60,50,40))
                self._make_quad(verts, tex, "step_lower")
            # Upper step (above neighbour ceiling)
            if nc < ceil_y - 0.05:
                verts = [
                    (x0, nc, z0), (x1, nc, z1),
                    (x1, ceil_y, z1), (x0, ceil_y, z0),
                ]
                tex = self.art.get_or_placeholder(w.overpic or w.picnum,
                                                  color=(55,45,35))
                self._make_quad(verts, tex, "step_upper")

    def _build(self):
        """Main build pass: iterate all sectors and construct geometry."""
        md = self.md
        processed = set()

        for si, sect in enumerate(md.sectors):
            # Skip degenerate sectors
            if sect.wallnum < 2 or sect.wallptr < 0:
                continue
            if sect.wallptr + sect.wallnum > len(md.walls):
                continue

            # Skip sectors with extreme z values (likely corrupt)
            fz_u = self._bz(sect.fz)
            cz_u = self._bz(sect.cz)
            if abs(fz_u) > 100 or abs(cz_u) > 100:
                continue

            # Floor and ceiling
            self._make_floor_ceiling(si, sect, is_floor=True)
            self._make_floor_ceiling(si, sect, is_floor=False)

            # Walls
            for wi in range(sect.wallnum):
                idx = sect.wallptr + wi
                if idx >= len(md.walls):
                    break
                w = md.walls[idx]
                if w.point2 < 0 or w.point2 >= len(md.walls):
                    continue
                # Avoid duplicate portal rendering
                key = (min(idx, w.nextwall), max(idx, w.nextwall))
                if w.nextwall >= 0 and key in processed:
                    continue
                processed.add(key)
                self._make_wall_quad(w, sect)

        print(f"[BUILD] Generated {len(self.entities)} mesh entities, "
              f"{len(self._collision_boxes)} colliders")

    def get_player_start(self):
        """Return Ursina Vec3 for player spawn."""
        x = self._bx(self.md.px)
        z = self._by(self.md.py)
        # Find floor height in start sector
        y = 0.0
        if 0 <= self.md.cursect < len(self.md.sectors):
            sect = self.md.sectors[self.md.cursect]
            fy, _ = self._sector_heights(sect)
            y = fy + PLAYER_HEIGHT
        return Vec3(x, y, z)

    def get_player_angle(self):
        """Convert Build engine angle (0-2047) to Ursina degrees."""
        # Build: 0 = East, 512 = South, 1024 = West, 1536 = North
        build_ang = self.md.pang % 2048
        degrees   = (build_ang / 2048.0) * 360.0
        return -degrees  # Ursina uses -Y rotation for yaw

    def destroy_all(self):
        for e in self.entities + self._collision_boxes:
            destroy(e)
        self.entities.clear()
        self._collision_boxes.clear()

# ═══════════════════════════════════════════════════════════════════════════════
#  SPRITE PLACER — Place game objects from MAP sprite data
# ═══════════════════════════════════════════════════════════════════════════════
ITEM_TILES = {
    TILE['SIXPAK']:    ('health',  25, color.rgb(200,255,200)),
    TILE['AMMO']:      ('ammo',    10, color.rgb(255,230,100)),
    TILE['BATTERYAMMO']:('ammo',   30, color.rgb(255,200, 50)),
    TILE['RPGAMMO']:   ('ammo',     2, color.rgb(255,150, 50)),
    TILE['SHIELD']:    ('armor',   50, color.rgb(150,200,255)),
    TILE['AIRTANK']:   ('oxygen', 100, color.rgb(100,200,255)),
    TILE['STEROIDS']:  ('speed',    1, color.rgb(255,100,255)),
    TILE['JETPACK']:   ('jetpack',  1, color.rgb(200,200,100)),
}
ENEMY_TILES = {
    TILE['FEMANOID']:  'femanoid',
    TILE['MANDROID']:  'mandroid',
    490: 'mandroid',
    579: 'drone',
    631: 'drunk',
}

class MapSpriteManager:
    def __init__(self, map_data: MapData, art: ArtLoader,
                 build_mesh: BuildMapMesh, game):
        self.md   = map_data
        self.art  = art
        self.mesh = build_mesh
        self.game = game
        self.items:   list[Entity]  = []
        self.enemies: list['Enemy'] = []
        self._place()

    def _build_pos(self, sp: BuildSprite) -> Vec3:
        x = self.mesh._bx(sp.x)
        z = self.mesh._by(sp.y)
        # Use sector floor for Y
        y = 0.0
        if 0 <= sp.sectnum < len(self.md.sectors):
            sect = self.md.sectors[sp.sectnum]
            fy, _ = self.mesh._sector_heights(sect)
            y = fy + 0.5
        return Vec3(x, y, z)

    def _place(self):
        for sp in self.md.sprites:
            pos = self._build_pos(sp)
            pic = sp.picnum & 0xFFFF  # mask off high bits

            # Items
            if pic in ITEM_TILES:
                kind, value, clr = ITEM_TILES[pic]
                tex = self.art.get_texture(pic)
                e = Entity(
                    model='quad',
                    position=pos,
                    scale=0.6,
                    color=clr,
                    texture=tex,
                    billboard=True,
                    collider='sphere',
                    name=f'item_{kind}_{value}',
                )
                e._item_kind  = kind
                e._item_value = value
                self.items.append(e)

            # Enemies
            elif pic in ENEMY_TILES:
                kind = ENEMY_TILES[pic]
                ang  = -(sp.ang / 2048.0) * 360.0
                en   = Enemy(pos, kind, ang, self.art, self.game)
                self.enemies.append(en)

            # Barrels
            elif pic == TILE['EXPLODINGBARREL']:
                tex = self.art.get_texture(pic)
                e = Entity(
                    model='cylinder',
                    position=pos,
                    scale=Vec3(0.4, 0.8, 0.4),
                    texture=tex,
                    collider='box',
                    name='barrel',
                    color=color.rgb(180,100,60),
                )
                e._health = 30
                self.items.append(e)

            # Decorative sprites (lights, cameras, etc.)
            elif 0 < pic < 2048:
                tex = self.art.get_texture(pic)
                if tex:
                    e = Entity(
                        model='quad',
                        position=pos,
                        scale=0.5,
                        texture=tex,
                        billboard=True,
                    )
                    self.items.append(e)

    def destroy_all(self):
        for e in self.items:
            destroy(e)
        for e in self.enemies:
            e.destroy()
        self.items.clear()
        self.enemies.clear()

# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIO SYSTEM — VOC + MIDI
# ═══════════════════════════════════════════════════════════════════════════════
class AudioSystem:
    """
    Loads Creative VOC sound files and MIDI music.
    Uses pygame.mixer for playback.
    """
    def __init__(self, game_dir: Path):
        self.game_dir = game_dir
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._music_files: list[Path] = []
        self._music_idx = 0
        self._enabled = False
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self._enabled = True
            self._load_vocs()
            self._index_midis()
            print(f"[AUDIO] Loaded {len(self._sounds)} sounds, "
                  f"{len(self._music_files)} MIDI tracks")
        except Exception as e:
            print(f"[AUDIO] Disabled: {e}")

    def _voc_to_wav(self, data: bytes) -> bytes | None:
        """Minimal Creative VOC → PCM WAV converter."""
        if not data.startswith(b'Creative Voice File\x1a'):
            return None
        # Find data blocks
        samples = bytearray()
        rate = 8000
        off = 26  # skip header
        while off < len(data):
            block_type = data[off]; off += 1
            if block_type == 0: break
            if off + 3 > len(data): break
            size = data[off] | (data[off+1]<<8) | (data[off+2]<<16); off += 3
            if block_type == 1:  # Sound data
                if size < 2: off += size; continue
                rate_byte = data[off]; off += 1
                codec     = data[off]; off += 1
                size -= 2
                if codec == 0:  # 8-bit unsigned PCM
                    rate = 1000000 // (256 - rate_byte) if rate_byte < 256 else 8000
                    samples.extend(data[off:off+size])
                off += size
            elif block_type == 9:  # Extended sound data
                if size < 12: off += size; continue
                sample_rate = struct.unpack_from('<I', data, off)[0]; off += 4
                bits = data[off]; off += 1
                channels = data[off]; off += 1
                codec = struct.unpack_from('<H', data, off)[0]; off += 2
                off += 4  # reserved
                size -= 12
                if codec == 0:  # PCM
                    rate = sample_rate
                    samples.extend(data[off:off+size])
                off += size
            else:
                off += size

        if not samples:
            return None

        # Build WAV
        pcm = bytes(samples)
        # Convert 8-bit unsigned to 16-bit signed
        pcm16 = bytes((b - 128) * 256 & 0xFFFF for b in
                      [(v&0xFF) for v in pcm]).replace(b'', b'')
        # Actually just use raw as 8-bit unsigned for simplicity
        num_samples = len(pcm)
        wav = bytearray()
        # RIFF header
        data_size = num_samples
        wav += b'RIFF'
        wav += struct.pack('<I', 36 + data_size)
        wav += b'WAVE'
        wav += b'fmt '
        wav += struct.pack('<I', 16)           # chunk size
        wav += struct.pack('<H', 1)            # PCM
        wav += struct.pack('<H', 1)            # mono
        wav += struct.pack('<I', rate)         # sample rate
        wav += struct.pack('<I', rate)         # byte rate
        wav += struct.pack('<H', 1)            # block align
        wav += struct.pack('<H', 8)            # bits per sample
        wav += b'data'
        wav += struct.pack('<I', data_size)
        wav += pcm
        return bytes(wav)

    def _load_vocs(self):
        for voc_path in self.game_dir.glob('*.VOC'):
            try:
                raw = voc_path.read_bytes()
                wav = self._voc_to_wav(raw)
                if wav:
                    sound = pygame.mixer.Sound(io.BytesIO(wav))
                    sound.set_volume(0.5)
                    name = voc_path.stem.lower()
                    self._sounds[name] = sound
            except Exception:
                pass

    def _index_midis(self):
        self._music_files = sorted(self.game_dir.glob('*.MID')) + \
                            sorted(self.game_dir.glob('*.mid'))

    def play(self, name: str):
        if not self._enabled: return
        snd = self._sounds.get(name.lower())
        if snd:
            try: snd.play()
            except Exception: pass

    def play_music(self, idx: int = 0):
        if not self._enabled or not self._music_files: return
        idx = idx % len(self._music_files)
        try:
            pygame.mixer.music.load(str(self._music_files[idx]))
            pygame.mixer.music.set_volume(0.4)
            pygame.mixer.music.play(-1)
            self._music_idx = idx
        except Exception: pass

    def stop_music(self):
        if not self._enabled: return
        try: pygame.mixer.music.stop()
        except Exception: pass

# ═══════════════════════════════════════════════════════════════════════════════
#  WEAPONS
# ═══════════════════════════════════════════════════════════════════════════════
WEAPONS = [
    {'name':'Tazer',    'ammo_type':'battery','damage': 8, 'rate':0.20, 'range':4.0,  'sound':'gun1'},
    {'name':'Pistol',   'ammo_type':'bullet', 'damage':12, 'rate':0.25, 'range':40.0, 'sound':'shooting'},
    {'name':'Chaingun', 'ammo_type':'bullet', 'damage': 8, 'rate':0.08, 'range':30.0, 'sound':'shooting'},
    {'name':'Grenade',  'ammo_type':'grenade','damage':60, 'rate':0.60, 'range':20.0, 'sound':'expl1'},
    {'name':'RPG',      'ammo_type':'rpg',    'damage':80, 'rate':0.90, 'range':60.0, 'sound':'rpg'},
]

class WeaponSystem:
    def __init__(self, audio: AudioSystem):
        self.audio    = audio
        self.current  = 1   # start with pistol
        self.ammo     = {'bullet':200, 'battery':50, 'grenade':10, 'rpg':5}
        self._cooldown = 0.0

    def fire(self, player_pos: Vec3, player_dir: Vec3,
             enemies: list, items: list, audio: AudioSystem) -> str | None:
        w = WEAPONS[self.current]
        if self._cooldown > 0:
            return None
        atype = w['ammo_type']
        if self.ammo.get(atype, 0) <= 0:
            audio.play('switch')
            return "OUT OF AMMO"

        self.ammo[atype] -= 1
        self._cooldown = w['rate']
        audio.play(w['sound'])

        # Hitscan: check enemies in range
        hit_msg = None
        for enemy in enemies:
            if not enemy.alive: continue
            diff = enemy.entity.position - player_pos
            dist = diff.length()
            if dist > w['range']: continue
            # Check if roughly in front of player
            diff_norm = diff.normalized()
            dot = player_dir.dot(diff_norm)
            if dot < 0.5: continue  # ~60° FOV check
            enemy.take_damage(w['damage'])
            audio.play('bodyblop')
            hit_msg = f"HIT! {enemy.kind} -{w['damage']} HP"
            break
        return hit_msg

    def update(self, dt: float):
        self._cooldown = max(0.0, self._cooldown - dt)

    def switch(self, idx: int):
        if 0 <= idx < len(WEAPONS):
            self.current = idx

    def pickup(self, ammo_type: str, amount: int):
        if ammo_type in self.ammo:
            self.ammo[ammo_type] = min(999, self.ammo[ammo_type] + amount)

# ═══════════════════════════════════════════════════════════════════════════════
#  ENEMY AI
# ═══════════════════════════════════════════════════════════════════════════════
ENEMY_STATS = {
    'femanoid': {'hp':20, 'speed':1.8, 'damage':8,  'range':8.0,  'color':(200,150,200)},
    'mandroid':  {'hp':30, 'speed':1.5, 'damage':12, 'range':10.0, 'color':(150,200,150)},
    'drone':     {'hp':15, 'speed':3.0, 'damage':6,  'range':12.0, 'color':(200,200,100)},
    'drunk':     {'hp':10, 'speed':1.0, 'damage':4,  'range':5.0,  'color':(200,150,100)},
}

class Enemy:
    def __init__(self, pos: Vec3, kind: str, angle: float,
                 art: ArtLoader, game):
        self.kind   = kind
        self.alive  = True
        self.game   = game
        stats = ENEMY_STATS.get(kind, ENEMY_STATS['femanoid'])
        self.hp     = stats['hp']
        self.speed  = stats['speed']
        self.damage = stats['damage']
        self.atk_range = stats['range']
        self._atk_cd = random.uniform(1.0, 3.0)

        # Tile lookup
        tile_map = {'femanoid': TILE['FEMANOID'],
                    'mandroid':  TILE['MANDROID'],
                    'drone':     TILE['DRONE1'],
                    'drunk':     TILE['DRUNKGUY1']}
        tile_id = tile_map.get(kind, TILE['FEMANOID'])
        tex = art.get_texture(tile_id)
        r,g,b = stats['color']

        self.entity = Entity(
            model='quad',
            position=pos,
            scale=0.9,
            texture=tex,
            color=color.rgb(r,g,b) if not tex else color.white,
            billboard=True,
            collider='sphere',
            name=f'enemy_{kind}',
        )
        self.entity.rotation_y = angle
        self._flash_timer = 0.0

    def take_damage(self, dmg: int):
        if not self.alive: return
        self.hp -= dmg
        self._flash_timer = 0.1
        if self.hp <= 0:
            self.die()

    def die(self):
        self.alive = False
        self.entity.color = color.rgb(180, 50, 50)
        invoke(destroy, self.entity, delay=2.0)

    def update(self, player_pos: Vec3, dt: float, audio: AudioSystem):
        if not self.alive: return
        diff  = player_pos - self.entity.position
        dist  = diff.length()

        # Flash on hit
        if self._flash_timer > 0:
            self._flash_timer -= dt
            self.entity.color = color.white if (int(time.time()*20)%2) else color.red
        elif self.alive:
            self.entity.color = color.white

        # Chase player
        if dist > 1.0 and dist < 20.0:
            move = diff.normalized() * self.speed * dt
            self.entity.position += Vec3(move.x, 0, move.z)

        # Attack player
        self._atk_cd -= dt
        if self._atk_cd <= 0 and dist < self.atk_range:
            self._atk_cd = random.uniform(1.5, 3.0)
            dmg = random.randint(self.damage//2, self.damage)
            self.game.player_take_damage(dmg, audio)

    def destroy(self):
        if self.entity and self.entity:
            destroy(self.entity)

# ═══════════════════════════════════════════════════════════════════════════════
#  HUD — Amber CRT style overlay
# ═══════════════════════════════════════════════════════════════════════════════
class HUD:
    def __init__(self):
        self._texts: list[Text] = []
        self._panels: list[Entity] = []
        self._build()

    def _build(self):
        # Bottom bar background
        bar = Entity(
            parent=camera.ui,
            model='quad',
            scale=(2, 0.12),
            position=(0, -0.46),
            color=color.rgba(0, 0, 0, 180),
            z=-1,
        )
        self._panels.append(bar)

        # Health
        self.health_label = Text(
            text='♥ 100',
            position=(-0.85, -0.43),
            scale=1.4,
            color=color.rgb(255, 80, 80),
            font='VeraMono.ttf',
            parent=camera.ui,
        )
        # Armor
        self.armor_label = Text(
            text='🛡 000',
            position=(-0.55, -0.43),
            scale=1.4,
            color=color.rgb(100, 180, 255),
            font='VeraMono.ttf',
            parent=camera.ui,
        )
        # Weapon
        self.weapon_label = Text(
            text='[PISTOL]',
            position=(-0.05, -0.43),
            scale=1.4,
            color=color.rgb(255, 200, 50),
            font='VeraMono.ttf',
            parent=camera.ui,
        )
        # Ammo
        self.ammo_label = Text(
            text='AMM 200',
            position=(0.45, -0.43),
            scale=1.4,
            color=color.rgb(255, 180, 50),
            font='VeraMono.ttf',
            parent=camera.ui,
        )
        # Level name
        self.level_label = Text(
            text='LAMEDUKE ENGINE',
            position=(-0.85, 0.45),
            scale=1.0,
            color=color.rgb(255, 160, 0),
            font='VeraMono.ttf',
            parent=camera.ui,
        )
        # Crosshair
        self.crosshair = Text(
            text='+',
            origin=(0,0),
            position=(0,0),
            scale=2.0,
            color=color.rgb(255, 200, 0),
            font='VeraMono.ttf',
            parent=camera.ui,
        )
        # Message line
        self.msg_label = Text(
            text='',
            position=(-0.85, -0.36),
            scale=1.1,
            color=color.rgb(200, 255, 150),
            font='VeraMono.ttf',
            parent=camera.ui,
        )
        self._msg_timer = 0.0
        self._texts = [self.health_label, self.armor_label, self.weapon_label,
                       self.ammo_label, self.level_label, self.crosshair,
                       self.msg_label]

    def update_stats(self, health, armor, weapon_name, ammo, level_name):
        self.health_label.text = f'♥ {health:3d}'
        self.armor_label.text  = f'◈ {armor:3d}'
        self.weapon_label.text = f'[{weapon_name.upper():<8}]'
        self.ammo_label.text   = f'● {ammo:3d}'
        self.level_label.text  = level_name

    def show_msg(self, msg: str, duration=2.5):
        self.msg_label.text = msg
        self._msg_timer = duration

    def tick(self, dt: float):
        if self._msg_timer > 0:
            self._msg_timer -= dt
            if self._msg_timer <= 0:
                self.msg_label.text = ''

    def destroy(self):
        for t in self._texts:
            destroy(t)
        for p in self._panels:
            destroy(p)

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN MENU
# ═══════════════════════════════════════════════════════════════════════════════
MENU_ASCII = """
 ██╗      █████╗ ███╗   ███╗███████╗██████╗ ██╗   ██╗██╗  ██╗███████╗
 ██║     ██╔══██╗████╗ ████║██╔════╝██╔══██╗██║   ██║██║ ██╔╝██╔════╝
 ██║     ███████║██╔████╔██║█████╗  ██║  ██║██║   ██║█████╔╝ █████╗  
 ██║     ██╔══██║██║╚██╔╝██║██╔══╝  ██║  ██║██║   ██║██╔═██╗ ██╔══╝  
 ███████╗██║  ██║██║ ╚═╝ ██║███████╗██████╔╝╚██████╔╝██║  ██╗███████╗
 ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚══════╝
"""

LEVEL_LIST = [
    # (vol, lvl, map_file, display_name)
    (1,1,'L1.MAP','E1L1 — Urban Streets'),
    (1,2,'L2.MAP','E1L2 — Police Station'),
    (1,3,'L3.MAP','E1L3 — Underground'),
    (1,4,'L4.MAP','E1L4 — OctaBrain Preview'),
    (1,5,'L5.MAP','E1L5 — Industrial Complex'),
    (1,6,'L6.MAP','E1L6 — Subway Terminal'),
    (1,7,'L7.MAP','E1L7 — Reactor Core'),
    (1,8,'L8.MAP','E1L8 — [stub]'),
    (1,9,'L9.MAP','E1L9 — [stub]'),
    (2,1,'M1.MAP','E2L1 — Military Base'),
    (2,2,'M2.MAP','E2L2 — Space Station'),
    (2,3,'M3.MAP','E2L3 — The Hangar'),
    (2,4,'M4.MAP','E2L4 — [fan map]'),
    (2,5,'M5.MAP','E2L5 — Orbital Platform'),
    (2,6,'M6.MAP','E2L6 — Alien Hive'),
    (2,7,'M7.MAP','E2L7 — Command Center'),
    (2,8,'M8.MAP','E2L8 — [stub]'),
    (3,1,'N1.MAP','E3L1 — Nuclear Facility'),
    (3,2,'N2.MAP','E3L2 — [fan map]'),
    (3,3,'N3.MAP','E3L3 — [fan map]'),
    (3,4,'N4.MAP','E3L4 — [fan map]'),
    (3,5,'N5.MAP','E3L5 — [fan map]'),
    (3,6,'N6.MAP','E3L6 — Derelict (→ DN3D)'),
    (3,7,'N7.MAP','E3L7 — Outpost'),
    (3,8,'N8.MAP','E3L8 — [stub]'),
    (4,1,'O1.MAP','BONUS 1'),
    (4,2,'O2.MAP','BONUS 2'),
    (4,3,'O3.MAP','BONUS 3'),
    (4,4,'O4.MAP','BONUS 4'),
    (0,0,'WAR1.MAP','WAR MAP 1'),
    (0,0,'WAR2.MAP','WAR MAP 2'),
]

class MainMenu:
    def __init__(self, game_dir: Path, art: ArtLoader,
                 audio: AudioSystem, on_start):
        self.game_dir = game_dir
        self.on_start = on_start
        self.audio    = audio
        self.entities: list[Entity] = []
        self.texts:    list[Text]   = []
        self._sel     = 0
        self._mode    = 'main'  # 'main' | 'levels'
        self._build_main()
        audio.play_music(0)

    def _txt(self, text, pos, scale=1.0, clr=None, **kw):
        t = Text(text=text, position=pos, scale=scale,
                 color=clr or color.rgb(255, 176, 0),
                 font='VeraMono.ttf', parent=camera.ui, **kw)
        self.texts.append(t)
        return t

    def _panel(self, pos, scale, clr=None):
        e = Entity(parent=camera.ui, model='quad', position=pos,
                   scale=scale, color=clr or color.rgba(0,0,0,200), z=0)
        self.entities.append(e)
        return e

    def _build_main(self):
        self._clear()
        self._mode = 'main'
        self._panel((0, 0), (2.1, 1.15), color.rgba(0,0,0,210))
        # CRT scanline effect
        for i in range(30):
            y = 0.55 - i * 0.038
            self._panel((0, y), (2.1, 0.001),
                        color.rgba(255,176,0, 12))
        # Title
        self._txt(MENU_ASCII, (-0.88, 0.32), scale=0.55,
                  clr=color.rgb(255,180,0))
        self._txt('Duke Nukem 3D Prototype · Build Engine Beta v1.3.95 · Dec 30 1994',
                  (-0.75, 0.13), scale=0.75, clr=color.rgb(160,110,0))
        self._txt('Python/Ursina Source Port · Modern Windows Edition',
                  (-0.55, 0.06), scale=0.75, clr=color.rgb(120,80,0))

        sep = '─' * 72
        self._txt(sep, (-0.88, 0.00), scale=0.7, clr=color.rgb(80,50,0))

        self._menu_items = [
            ('▶  START GAME  (Episode 1, Level 1)', lambda: self.on_start('L1.MAP', 0)),
            ('▶  SELECT LEVEL',                     self._open_levels),
            ('▶  QUICKSTART  (WAR1.MAP)',            lambda: self.on_start('WAR1.MAP', 1)),
            ('',                                     None),
            ('   BUILD ENGINE & TOOLS  © 1993-1997 KEN SILVERMAN', None),
            ('   LAMEDUKE © 1994-1997 3D REALMS / APOGEE SOFTWARE', None),
            ('   URSINA ENGINE  —  Python Port  —  Fan Preservation',None),
            ('',                                     None),
            ('▶  EXIT',                              application.quit),
        ]
        self._sel = 0
        self._render_menu_items()
        self._txt('[ WASD/ARROWS to navigate · ENTER to select ]',
                  (-0.55, -0.46), scale=0.8, clr=color.rgb(100,70,0))

    def _render_menu_items(self):
        for t in getattr(self, '_item_texts', []):
            destroy(t)
        self._item_texts = []
        y_start = -0.07
        for i, (label, _) in enumerate(self._menu_items):
            clr = (color.rgb(255,230,50) if i == self._sel and _ is not None
                   else (color.rgb(255,176,0) if _ is not None
                         else color.rgb(80,55,0)))
            prefix = '» ' if (i == self._sel and _ is not None) else '  '
            t = Text(text=prefix+label,
                     position=(-0.88, y_start - i*0.046),
                     scale=0.85, color=clr, font='VeraMono.ttf',
                     parent=camera.ui)
            self._item_texts.append(t)
            self.texts.append(t)

    def _open_levels(self):
        self._clear()
        self._mode = 'levels'
        self._panel((0,0), (2.1, 1.15), color.rgba(0,0,0,210))
        self._txt('[ SELECT LEVEL ]', (-0.88, 0.46), scale=1.1,
                  clr=color.rgb(255,230,50))
        self._txt('WASD/ARROWS navigate · ENTER select · ESC back',
                  (-0.88, -0.47), scale=0.8, clr=color.rgb(100,70,0))
        self._lv_sel = 0
        self._render_levels()

    def _render_levels(self):
        for t in getattr(self, '_lv_texts', []):
            destroy(t)
        self._lv_texts = []
        visible_start = max(0, self._lv_sel - 10)
        visible_end   = min(len(LEVEL_LIST), visible_start + 22)
        y = 0.38
        for i in range(visible_start, visible_end):
            vol, lvl, mfile, name = LEVEL_LIST[i]
            exists = (self.game_dir / mfile).exists()
            prefix = '» ' if i == self._lv_sel else '  '
            status = '' if exists else ' [MISSING]'
            clr = (color.rgb(255,230,50) if i==self._lv_sel
                   else (color.rgb(255,176,0) if exists
                         else color.rgb(100,60,60)))
            t = Text(text=f'{prefix}{name}{status}',
                     position=(-0.88, y), scale=0.82, color=clr,
                     font='VeraMono.ttf', parent=camera.ui)
            self._lv_texts.append(t)
            self.texts.append(t)
            y -= 0.040
            if y < -0.44: break

    def navigate(self, delta: int):
        if self._mode == 'main':
            items = [i for i,(l,fn) in enumerate(self._menu_items) if fn]
            if not items: return
            cur = items.index(self._sel) if self._sel in items else 0
            cur = (cur + delta) % len(items)
            self._sel = items[cur]
            self._render_menu_items()
        else:
            self._lv_sel = (self._lv_sel + delta) % len(LEVEL_LIST)
            self._render_levels()

    def select(self):
        if self._mode == 'main':
            _, fn = self._menu_items[self._sel]
            if fn: fn()
        else:
            _, __, mfile, name = LEVEL_LIST[self._lv_sel]
            if (self.game_dir / mfile).exists():
                self.on_start(mfile, self._lv_sel)
            else:
                self.audio.play('switch')

    def back(self):
        if self._mode == 'levels':
            self._build_main()

    def _clear(self):
        for e in self.entities: destroy(e)
        for t in self.texts:    destroy(t)
        for t in getattr(self,'_item_texts',[]): destroy(t)
        for t in getattr(self,'_lv_texts',  []): destroy(t)
        self.entities.clear()
        self.texts.clear()

    def destroy(self):
        self._clear()

# ═══════════════════════════════════════════════════════════════════════════════
#  GAME — Main game state
# ═══════════════════════════════════════════════════════════════════════════════
class LameDukeGame(Ursina):
    def __init__(self, game_dir: Path):
        super().__init__(
            title='LameDuke Engine — Duke Nukem 3D Prototype 1994',
            fullscreen=False,
            borderless=False,
            development_mode=False,
        )
        window.fps_counter.enabled = True
        window.exit_button.visible = False

        self.game_dir   = game_dir
        self.palette    = load_palette(game_dir)
        self.art        = ArtLoader(game_dir, self.palette)
        self.audio      = AudioSystem(game_dir)

        # Game state
        self._state     = 'menu'  # 'menu' | 'loading' | 'playing' | 'dead'
        self._map_mesh  = None
        self._sprite_mgr= None
        self._player    = None
        self._weapons   = None
        self._hud       = None
        self._menu      = None
        self._health    = 100
        self._armor     = 0
        self._jetpack   = False
        self._steroids  = False
        self._dead_timer= 0.0
        self._level_name= ''
        self._kill_count= 0
        self._map_name  = ''
        self._music_idx = 0

        # Ambient world
        self._setup_world()
        self._open_menu()

    def _setup_world(self):
        """Sky, ambient light, fog."""
        scene.fog_color  = color.rgb(10, 8, 12)
        scene.fog_density = 0.06
        AmbientLight(color=color.rgba(60,50,80,255))
        sun = DirectionalLight()
        sun.look_at(Vec3(1,-1,1))
        sky = Sky(color=color.rgba(8,8,15,255))

    def _open_menu(self):
        self._state = 'menu'
        if self._player:
            destroy(self._player)
            self._player = None
        if self._hud:
            self._hud.destroy()
            self._hud = None
        if self._map_mesh:
            self._map_mesh.destroy_all()
            self._map_mesh = None
        if self._sprite_mgr:
            self._sprite_mgr.destroy_all()
            self._sprite_mgr = None
        camera.position = Vec3(0, 2, -5)
        camera.rotation = Vec3(0, 0, 0)
        mouse.locked = False
        self._menu = MainMenu(self.game_dir, self.art, self.audio, self._start_level)

    def _start_level(self, map_file: str, music_idx: int):
        if self._menu:
            self._menu.destroy()
            self._menu = None

        self._state = 'loading'
        self._map_name = map_file
        self._music_idx = music_idx

        # Show loading text briefly
        load_txt = Text(
            text=f'LOADING  {map_file}...',
            origin=(0,0), position=(0,0),
            scale=2.0, color=color.rgb(255,176,0),
            font='VeraMono.ttf', parent=camera.ui,
        )
        invoke(self._do_load, map_file, music_idx, load_txt, delay=0.05)

    def _do_load(self, map_file: str, music_idx: int, load_txt):
        destroy(load_txt)

        # Parse and build map
        map_path = self.game_dir / map_file
        if not map_path.exists():
            self._open_menu()
            return

        md = parse_map(map_path)
        if md is None:
            self._open_menu()
            return

        self._map_mesh   = BuildMapMesh(md, self.art)
        self._weapons    = WeaponSystem(self.audio)
        self._sprite_mgr = MapSpriteManager(md, self.art, self._map_mesh, self)

        # Player spawn
        spawn = self._map_mesh.get_player_start()
        ang   = self._map_mesh.get_player_angle()

        self._player = FirstPersonController(
            position=spawn,
            speed=4.0,
            height=PLAYER_HEIGHT,
            mouse_sensitivity=Vec2(60, 60),
            jump_height=2.0,
            gravity=0.8,
        )
        self._player.rotation_y = ang
        camera.clip_plane_near = 0.05
        camera.fov = 90

        self._health = 100
        self._armor  = 0
        self._kill_count = 0
        self._jetpack = False
        self._steroids = False

        # Format level name
        for vol,lvl,mf,name in LEVEL_LIST:
            if mf.upper() == map_file.upper():
                self._level_name = name
                break
        else:
            self._level_name = map_file.replace('.MAP','')

        self._hud = HUD()
        self._hud.update_stats(self._health, self._armor,
                               WEAPONS[1]['name'], 200, self._level_name)
        self.audio.play_music(music_idx)
        mouse.locked = True
        self._state = 'playing'
        print(f"[GAME] Level loaded: {self._level_name}")

    def player_take_damage(self, dmg: int, audio: AudioSystem):
        if self._armor > 0:
            absorbed = min(self._armor, dmg // 2)
            self._armor -= absorbed
            dmg -= absorbed
        self._health -= dmg
        audio.play('land')
        if self._hud:
            self._hud.show_msg(f'OUCH! -{dmg} HP')
        if self._health <= 0:
            self._die()

    def _die(self):
        self._state = 'dead'
        self._dead_timer = 3.0
        mouse.locked = False
        if self._hud:
            self._hud.show_msg('YOU HAVE BEEN KILLED! Press ENTER to respawn.')

    def _respawn(self):
        if self._map_name:
            self._start_level(self._map_name, self._music_idx)

    def update(self):
        dt = time.dt
        if self._state == 'menu':
            self._tick_menu()
        elif self._state == 'playing':
            self._tick_game(dt)
        elif self._state == 'dead':
            self._dead_timer -= dt
            if self._dead_timer <= 0 or held_keys['enter']:
                self._respawn()

    def _tick_menu(self):
        pass  # Menu handles its own input in input()

    def _tick_game(self, dt: float):
        if not self._player or not self._weapons:
            return

        self._weapons.update(dt)

        # Update enemies
        if self._sprite_mgr:
            ppos = self._player.position
            for enemy in self._sprite_mgr.enemies:
                enemy.update(ppos, dt, self.audio)

        # Item pickup check
        if self._sprite_mgr:
            ppos = self._player.position
            for item in list(self._sprite_mgr.items):
                if not item or not item.enabled:
                    continue
                diff = (item.position - ppos)
                if diff.length() < 1.0:
                    self._pickup(item)

        # HUD update
        if self._hud:
            w  = WEAPONS[self._weapons.current]
            am = self._weapons.ammo.get(w['ammo_type'], 0)
            self._hud.update_stats(max(0, self._health), self._armor,
                                    w['name'], am, self._level_name)
            self._hud.tick(dt)

    def _pickup(self, item: Entity):
        name = item.name
        if name.startswith('item_health'):
            val = item._item_value
            self._health = min(200, self._health + val)
            self.audio.play('getweapn')
            if self._hud: self._hud.show_msg(f'+{val} HEALTH')
        elif name.startswith('item_ammo'):
            val = item._item_value
            self._weapons.pickup('bullet', val)
            self.audio.play('getweapn')
            if self._hud: self._hud.show_msg(f'+{val} AMMO')
        elif name.startswith('item_armor'):
            val = item._item_value
            self._armor = min(100, self._armor + val)
            self.audio.play('getweapn')
            if self._hud: self._hud.show_msg(f'+{val} ARMOR')
        elif name.startswith('item_jetpack'):
            self._jetpack = True
            if self._hud: self._hud.show_msg('JETPACK!')
        elif name.startswith('item_speed'):
            self._steroids = True
            if self._player:
                self._player.speed = 8.0
            if self._hud: self._hud.show_msg('STEROIDS!')
        elif name == 'barrel':
            return  # Shot, not walked into
        else:
            return
        self._sprite_mgr.items.remove(item)
        destroy(item)

    def input(self, key):
        if self._state == 'menu' and self._menu:
            if key in ('up arrow','w'):
                self._menu.navigate(-1)
            elif key in ('down arrow','s'):
                self._menu.navigate(1)
            elif key in ('enter','space'):
                self._menu.select()
                self.audio.play('clipin')
            elif key == 'escape':
                self._menu.back()
        elif self._state == 'playing':
            # Weapon switch
            for i in range(5):
                if key == str(i+1):
                    self._weapons.switch(i)
            # Fire
            if key == 'left mouse button' and self._player:
                ppos = self._player.position
                pfwd = self._player.forward
                enemies = self._sprite_mgr.enemies if self._sprite_mgr else []
                items   = self._sprite_mgr.items   if self._sprite_mgr else []
                msg = self._weapons.fire(ppos, pfwd, enemies, items, self.audio)
                if msg and self._hud:
                    self._hud.show_msg(msg)
                # Update kill count
                if msg and 'HIT' in msg:
                    killed = [e for e in enemies if not e.alive]
                    self._kill_count = len(killed)
            # Pause / back to menu
            elif key == 'escape':
                self.audio.stop_music()
                self._open_menu()
            # Jetpack toggle
            elif key == 'f' and self._jetpack:
                if self._player:
                    self._player.gravity = 0.0 if self._player.gravity else 0.8

# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
def find_game_dir() -> Path:
    """Auto-detect LameDuke game folder or prompt user."""
    # Check command line argument
    if len(sys.argv) > 1:
        p = Path(sys.argv[1])
        if p.is_dir() and (p / 'D3D.EXE').exists():
            return p

    # Check common locations
    candidates = [
        Path('.'),
        Path(__file__).parent,
        Path.home() / 'LameDuke',
        Path('C:/Games/LameDuke'),
        Path('C:/LameDuke'),
    ]
    for p in candidates:
        if p.is_dir() and (p / 'D3D.EXE').exists():
            print(f"[INIT] Found game data at: {p}")
            return p

    # Check if we're running from within the game folder
    here = Path(__file__).parent
    if (here / 'TILES000.ART').exists():
        return here

    # Last resort: use current dir even without D3D.EXE
    # (will work if ART/MAP files are present)
    if (Path('.') / 'TILES000.ART').exists():
        return Path('.')

    print("\n[ERROR] LameDuke game folder not found!")
    print("Usage: python lameduke_engine.py <path/to/lameduke/folder>")
    print("\nThe folder must contain: D3D.EXE, TILES000.ART, L1.MAP, etc.")
    print("\nExample:")
    print("  python lameduke_engine.py C:\\Games\\LameDuke")
    print("\nSearched:")
    for p in candidates:
        print(f"  {p} {'✓' if p.exists() else '✗'}")
    sys.exit(1)


if __name__ == '__main__':
    game_dir = find_game_dir()
    print(f"[INIT] LameDuke Engine starting | Game dir: {game_dir}")
    print(f"[INIT] Python {sys.version.split()[0]}  |  Ursina engine")
    game = LameDukeGame(game_dir)
    game.run()
