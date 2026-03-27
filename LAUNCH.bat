@ECHO OFF
TITLE LAMEDUKE ARCADE ENGINE v3.0
COLOR 0E
ECHO.
ECHO  ╔══════════════════════════════════════════════════════════╗
ECHO  ║  LAMEDUKE ARCADE ENGINE v3.0 — Python/Ursina           ║
ECHO  ║  Duke Nukem 3D Prototype (Build Engine, Dec 1994)       ║
ECHO  ╠══════════════════════════════════════════════════════════╣
ECHO  ║  FIXES:  TypeError singleton crash RESOLVED             ║
ECHO  ║  ARCADE: INSERT COIN + attract mode + ROM/RAM check     ║
ECHO  ╚══════════════════════════════════════════════════════════╝
ECHO.
ECHO  ARCADE CONTROLS:
ECHO    5 or C      Insert Coin (attract mode)
ECHO    1 or Enter  Start Game / Select Level
ECHO    (no other hints shown during gameplay)
ECHO.

python --version >NUL 2>&1
IF ERRORLEVEL 1 (ECHO [ERROR] Python not found. Install from python.org & PAUSE & EXIT /B 1)

pip install ursina pillow pygame --quiet --upgrade 2>NUL
ECHO [OK] Dependencies ready.
ECHO.

SET GAME_DIR=%~dp0
IF EXIST "%GAME_DIR%D3D.EXE"      GOTO :LAUNCH
IF EXIST "%GAME_DIR%TILES000.ART" GOTO :LAUNCH
IF EXIST "%GAME_DIR%..\D3D.EXE"   (SET GAME_DIR=%GAME_DIR%.. & GOTO :LAUNCH)

ECHO [WARN] Place this script in your LameDuke folder (with D3D.EXE)
ECHO        or run: python lameduke_engine.py "path\to\lameduke"
PAUSE & EXIT /B 1

:LAUNCH
ECHO Launching...
python "%~dp0lameduke_engine.py" "%GAME_DIR%"
IF ERRORLEVEL 1 (ECHO. & ECHO [ERROR] See error above. & PAUSE)
