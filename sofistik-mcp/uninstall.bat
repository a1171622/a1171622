@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Nothing to remove: install.bat was never run here.
  pause
  exit /b 0
)
".venv\Scripts\python.exe" -m sofistik_mcp.configure_clients --remove
echo.
echo The server is no longer registered. Restart Claude. You can now delete this folder.
pause
