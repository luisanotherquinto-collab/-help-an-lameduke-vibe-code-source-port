@ECHO OFF
TITLE LameDuke Engine — Build EXE
COLOR 0E
ECHO.
ECHO  Building LameDuke Engine to standalone EXE...
ECHO  (No Python required on target machine)
ECHO.
pip show pyinstaller >NUL 2>&1 || pip install pyinstaller
ECHO.
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "LameDuke_Engine" ^
    --icon NONE ^
    --clean ^
    --add-data "requirements.txt;." ^
    lameduke_engine.py
IF ERRORLEVEL 1 ( ECHO BUILD FAILED & PAUSE & EXIT /B 1 )
ECHO.
ECHO  ══════════════════════════════════════════════════════════
ECHO   DONE: dist\LameDuke_Engine.exe
ECHO.
ECHO   Place LameDuke_Engine.exe in your LameDuke folder
ECHO   (same folder as D3D.EXE, TILES000.ART, L1.MAP, etc.)
ECHO   Then double-click to run — no Python needed!
ECHO  ══════════════════════════════════════════════════════════
PAUSE
