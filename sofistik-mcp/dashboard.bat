@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto noinstall
echo  SOFiSTiK dashboard: opens in your browser. Leave this window open while you watch.
".venv\Scripts\python.exe" -m sofistik_mcp.dashboard
pause
exit /b 0

:noinstall
echo  Run install.bat first.
pause
exit /b 1
