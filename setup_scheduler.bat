@echo off
setlocal
echo ====================================================
echo  LAN File Distributor - Windows Task Scheduler Setup
echo ====================================================
echo.

set SCRIPT_DIR=%~dp0
set SCRIPT_PATH=%SCRIPT_DIR%check_updates.py

echo This will create a Windows Task Scheduler job named:
echo "LANFileDistributor_DailyCheck"
echo.
echo It will run silently every morning at 11:00 AM using pythonw.exe
echo (Zero background memory when idle).
echo.

schtasks /Create /SC DAILY /TN "LANFileDistributor_DailyCheck" /TR "pythonw \"%SCRIPT_PATH%\"" /ST 11:00 /F

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] Scheduled task registered successfully!
    echo It will check for GitHub releases daily at 11:00 AM.
) else (
    echo.
    echo [ERROR] Failed to register task. Please run this .bat as Administrator.
)

echo.
pause
