@echo off
cd /d "%~dp0"

py -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --windowed ^
    --icon=icon.png ^
    --name CapcutAuto ^
    capcut_gui.py ^
    --distpath .

echo.
echo Build complete!
pause
