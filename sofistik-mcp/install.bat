@echo off
setlocal
cd /d "%~dp0"
echo.
echo  ===== SOFiSTiK MCP server - install =====
echo  Folder: %CD%
echo.

echo  Before you go on: fully quit Claude (right-click the Claude icon next to the clock, Quit),
echo  so it cannot overwrite its settings while this installs.
pause

rem --- 1. find 64-bit Python 3.10+ (the py launcher first, then python) -----------------
set "PY="
set "CHECK=import sys; raise SystemExit(0 if sys.version_info >= (3, 10) and sys.maxsize > 2**32 else 1)"
py -3 -c "%CHECK%" >nul 2>nul
if errorlevel 1 goto trypython
set "PY=py -3"
goto havepython
:trypython
python -c "%CHECK%" >nul 2>nul
if errorlevel 1 goto nopython
set "PY=python"
:havepython
echo  Python: %PY%

rem --- 2. private Python environment for the server (.venv) ------------------------------
if not exist ".venv\Scripts\python.exe" (
  echo  Creating the Python environment ...
  %PY% -m venv .venv
  if errorlevel 1 goto failed
)
echo  Installing the MCP package (needs internet, about a minute) ...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto failed

rem --- 3. settings (kept if you already edited them) ---------------------------------------
if not exist settings.json copy /y settings.default.json settings.json >nul

rem --- 4. tell Claude Desktop and Claude Code about the server -----------------------------
echo.
echo  Registering the server with Claude ...
".venv\Scripts\python.exe" -m sofistik_mcp.configure_clients

rem --- 5. self-test: solve a cantilever and compare with a hand calculation ---------------
echo.
echo  Running the self-test (SOFiSTiK solves a small cantilever) ...
echo.
".venv\Scripts\python.exe" -m sofistik_mcp.selftest
echo.
echo  ======================================================================
echo   Next: open Claude again. Then ask Claude: "use the sofistik tools: status".
echo   If the self-test shows FAIL, send Claude selftest\selftest_report.txt
echo  ======================================================================
pause
exit /b 0

:nopython
echo  64-bit Python 3.10 or newer was not found.
echo  Install Python 3.12 or 3.13 from python.org, tick "Add python.exe to PATH", then run this again.
pause
exit /b 1

:failed
echo.
echo  Something went wrong above. Send Claude a screenshot of this window.
pause
exit /b 1
