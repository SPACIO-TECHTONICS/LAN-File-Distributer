@echo off
title Build LAN Relay Setup Executable
echo ====================================================
echo  Building Unified LAN_Relay_Setup.exe
echo ====================================================
echo.

pyinstaller --onefile --noconsole --name "LAN_Relay_Setup" --add-data "web;web" setup_wizard.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ====================================================
    echo [SUCCESS] LAN_Relay_Setup.exe generated in dist\ folder!
    echo You can copy dist\LAN_Relay_Setup.exe to your online PC
    echo and offline PC.
    echo ====================================================
) else (
    echo.
    echo [ERROR] Build failed. Please inspect logs above.
)

pause
