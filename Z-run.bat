@echo off
echo ==============================
echo  Starting CapCut Automation
echo ==============================

py -3 capcut_gui.py
IF %ERRORLEVEL% NEQ 0 (
    python capcut_gui.py
)

echo.
echo ==============================
echo  Automation Finished
echo ==============================
pause
