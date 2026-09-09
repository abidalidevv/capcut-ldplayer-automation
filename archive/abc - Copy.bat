@echo off
echo Checking phone...
adb devices
echo.
echo 1 = Restart
echo 2 = Power Off
echo.

set /p choice=Choice:

if "%choice%"=="1" adb reboot
if "%choice%"=="2" adb shell reboot -p

pause