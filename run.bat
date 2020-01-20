@echo off
echo ==============================
echo  🚀 Starting CapCut Automation
echo ==============================

REM --- Python path auto detect ---
REM --- Agar python command system me registered hai to ye kaam karega ---

python capcut_auto_basic.py
IF %ERRORLEVEL% NEQ 0 (
    echo ❌ 'python' command failed. Trying 'python3'...
    python3 capcut_auto_basic.py
)

echo.
echo ==============================
echo  ✅ Automation Finished
echo ==============================
pause
