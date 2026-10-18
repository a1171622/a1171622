@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run install.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m sofistik_mcp.selftest
echo.
echo Report: selftest\selftest_report.txt
pause
