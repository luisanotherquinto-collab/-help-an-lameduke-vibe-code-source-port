═══════════════════════════════════════════════════════════════════
  LAMEDUKE ENGINE  —  Python/Ursina Modern Source Port
  Duke Nukem 3D Prototype (Build Engine Beta v1.3.95, Dec 30 1994)
═══════════════════════════════════════════════════════════════════

WHAT IS THIS?
  A complete from-scratch Python recreation of LameDuke using
  the Ursina 3D engine. Reads the original game data files
  (ART textures, MAP geometry, VOC sounds) directly.

  NO DOSBOX. NO DOS. Runs natively on Windows 10/11 (64-bit).

FILES INCLUDED:
  lameduke_engine.py   Main engine (single Python file, ~900 lines)
  LAUNCH.bat           Auto-install deps + launch (Windows)
  BUILD_EXE.bat        Compile to standalone .EXE (PyInstaller)
  requirements.txt     Python package list

REQUIREMENTS:
  Python 3.10+ from https://python.org
    (Enable "Add Python to PATH" during install!)
  
  Auto-installed by LAUNCH.bat:
    ursina    — 3D game engine
    pillow    — ART tile extraction
    pygame    — VOC/MIDI audio

USAGE:

  Option A — Quick launch (Windows):
    1. Copy lameduke_engine.py + LAUNCH.bat into your LameDuke folder
       (same folder as D3D.EXE, TILES000.ART, L1.MAP, etc.)
    2. Double-click LAUNCH.bat

  Option B — Command line:
    pip install ursina pillow pygame
    python lameduke_engine.py "C:\Games\LameDuke"

  Option C — Standalone EXE (no Python needed on target PC):
    Double-click BUILD_EXE.bat
    → dist\LameDuke_Engine.exe
    Copy the .EXE to your LameDuke folder and run it.

CONTROLS:
  WASD / Arrow Keys  — Move
  Mouse              — Look (mouselook)
  Left Click         — Fire weapon
  1 / 2 / 3 / 4 / 5 — Switch weapon (Tazer/Pistol/Chaingun/Grenade/RPG)
  Space              — Jump
  F                  — Jetpack toggle (if collected)
  ESC                — Return to main menu

MAIN MENU:
  W/S or Arrow Keys  — Navigate
  Enter              — Select
  ESC                — Back

WHAT GETS LOADED FROM GAME DATA:
  ✓ TILES*.ART   — All textures with original VGA palette applied
  ✓ PALETTE.DAT  — 256-color VGA palette (6-bit, 54 shade tables)
  ✓ *.MAP        — Sector/wall/sprite geometry (Build Engine format v5)
  ✓ *.VOC        — Sound effects (Creative VOC, auto-converted to WAV)
  ✓ *.MID        — Music tracks (MIDI)
  ✓ DEFS.CON     — Tile ID references for actor placement

LEVELS AVAILABLE:
  Episode 1 (L*.MAP): L1-L9  — Urban/Industrial (9 levels)
  Episode 2 (M*.MAP): M1-M8  — Military/Space   (8 levels)
  Episode 3 (N*.MAP): N1-N8  — Nuclear          (8 levels)
  Bonus     (O*.MAP): O1-O4  — Extra maps       (4 levels)
  War maps  (WAR*.MAP): WAR1, WAR2              (2 levels)
  Total: 31 maps

ENEMIES (placed from MAP sprite data):
  Femanoid (tile 408) — Fast melee, 20 HP
  Mandroid  (tile 490) — Tough shooter, 30 HP
  Drone     (tile 579) — Fast flying, 15 HP
  DrunkGuy  (tile 631) — Weak melee, 10 HP

WEAPONS:
  1 — Tazer       (tile OTHERSHOTSPARK) — Close range electric
  2 — Pistol      (tile SHOTSPARK1)    — Standard hitscan
  3 — Chaingun    (tile BULLET)        — Fast fire
  4 — Grenade     (tile HEAVYHBOMB)    — Explosive
  5 — RPG         (tile RPG)           — Long range

ITEMS (picked up by walking over):
  Sixpak  (tile 722) — +25 health
  Ammo    (tile 723) — +10 bullets
  BattAmmo(tile 1120)— +30 battery
  RPGAmmo (tile 1119)— +2 RPG rockets
  Shield  (tile 726) — +50 armor
  Jetpack (tile 728) — Enables F-key flight
  Steroids(tile 724) — Double speed

TECHNICAL NOTES:

  Build Engine MAP format (v5 Beta, LameDuke 1994):
    Sector: 37 bytes (no heinum fields — earlier than Duke3D release)
    Wall:   32 bytes (standard)
    Sprite: 44 bytes (standard)
    Coordinates: 1 Build unit ≈ 1/512 Ursina units (XY)
                 1 Build unit ≈ 1/4096 Ursina units (Z/height)

  ART tile format (Build Engine):
    Tiles stored column-major (X varies slowest in memory)
    Palette index 255 = transparent (RGBA alpha=0)
    6-bit VGA values × 4 = 8-bit RGB
    Stored in files TILES000.ART through TILES007.ART
    Total: ~2003 tiles covering full sprite/texture range

  VOC audio (Creative Voice File):
    Supports block types 1 (8-bit PCM) and 9 (extended PCM)
    Auto-converted to WAV for pygame.mixer playback

  MIDI music:
    FASTWAY.MID   — Episode 1 main theme
    FASTWAY1.MID  — Episode 2 main theme
    FASTWAY2.MID  — Episode 3 main theme
    BROWNEYE.MID  — Title/intro
    MISTACHE.MID  — Alternate
    E2M1.MID      — Alternate

KNOWN LIMITATIONS:
  • Build Engine uses 2.5D sector-portal rendering; this engine
    converts to true 3D (some visual differences expected)
  • Corrupt/degenerate sectors are skipped (common in beta maps)
  • Fan-modified maps (M4, N2-N5) may have irregular geometry
  • No save/load system (matches original LameDuke)
  • No Dukematch (original had none either)
  • Sector water effects not yet implemented
  • Moving sectors (elevators) use static geometry

CREDITS:
  Build Engine & Tools © 1993-1997 Ken Silverman
  https://advsys.net/ken/buildsrc/

  LameDuke © 1994-1997 3D Realms / Apogee Software
  Publicly released: January 29, 1997

  Ursina Engine: https://www.ursinaengine.org
  Python 3D game framework by Panda3D

  This engine is a fan preservation project.
  Duke Nukem is a trademark of Gearbox Software.
  No original executable code is used or modified.

═══════════════════════════════════════════════════════════════════
