```bat
@echo off
title Android Phone Control

echo ==============================
echo       ANDROID PHONE CONTROL
echo ==============================
echo.
echo 1. Restart Phone
echo 2. Power Off Phone
echo 3. Check Connection
echo 4. Exit
echo.

set /p choice=Enter choice: 

if "%choice%"=="1" adb reboot
if "%choice%"=="2" adb shell reboot -p
if "%choice%"=="3" adb devices
if "%choice%"=="4" exit

pause
```
