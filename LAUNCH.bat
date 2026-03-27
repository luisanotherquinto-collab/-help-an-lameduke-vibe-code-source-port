@ECHO OFF
TITLE LameDuke Engine - Setup & Launch
COLOR 06
ECHO.
ECHO  ==========================================================
ECHO  =  LAMEDUKE ENGINE - Python/Ursina Source Port           =
ECHO  =  Duke Nukem 3D Prototype (Build Engine, Dec 1994)      =
ECHO  ==========================================================
ECHO.

:: Check Python
python --version >NUL 2>&1
IF ERRORLEVEL 1 (
    ECHO [ERROR] Python not found.
    ECHO         Download from: https://python.org
    ECHO         Enable "Add Python to PATH" during install!
    PAUSE
    EXIT /B 1
)

FOR /F "tokens=2" %%V IN ('python --version 2^>^&1') DO SET PYVER=%%V
ECHO [OK] Python %PYVER% found.

:: Install dependencies
ECHO.
ECHO Installing dependencies (ursina, pillow, pygame)...
pip install ursina pillow pygame --quiet --upgrade
IF ERRORLEVEL 1 (
    ECHO [WARN] Some packages may not have installed. Trying anyway...
) ELSE (
    ECHO [OK] Dependencies ready.
)

:: Find game data
ECHO.
:: Get script directory and safely remove the trailing backslash
SET "GAME_DIR=%~dp0"
IF "%GAME_DIR:~-1%"=="\" SET "GAME_DIR=%GAME_DIR:~0,-1%"

IF EXIST "%GAME_DIR%\D3D.EXE" (
    ECHO [OK] Game data found: %GAME_DIR%
    GOTO :LAUNCH
)
IF EXIST "%GAME_DIR%\..\D3D.EXE" (
    SET "GAME_DIR=%GAME_DIR%\.."
    ECHO [OK] Game data found: %GAME_DIR%
    GOTO :LAUNCH
)

ECHO [WARN] D3D.EXE not found. Trying with TILES000.ART...
IF EXIST "%GAME_DIR%\TILES000.ART" (
    ECHO [OK] Tile data found: %GAME_DIR%
    GOTO :LAUNCH
)

ECHO.
ECHO [ERROR] LameDuke game data not found!
ECHO         Place this script IN the same folder as D3D.EXE and TILES000.ART
ECHO         OR pass the folder as an argument:
ECHO           python lameduke_engine.py "C:\Games\LameDuke"
ECHO.
PAUSE
EXIT /B 1

:LAUNCH
ECHO.
ECHO  ==========================================================
ECHO   LAUNCHING LAMEDUKE ENGINE...
ECHO   Controls:
ECHO     WASD        - Move
ECHO     Mouse       - Look
ECHO     Left Click  - Fire
ECHO     1-5         - Switch weapon
ECHO     Space       - Jump
ECHO     F           - Jetpack (if collected)
ECHO     ESC         - Menu
ECHO  ==========================================================
ECHO.
TIMEOUT /T 2 /NOBREAK >NUL

:: Safe launch command with properly formatted paths
python "%~dp0lameduke_engine.py" "%GAME_DIR%"
IF ERRORLEVEL 1 (
    ECHO.
    ECHO [ERROR] Engine crashed. See error above.
    PAUSE
)