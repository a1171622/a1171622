@echo off
setlocal
cd /d "%~dp0"
echo.
echo  ===== SOFiSTiK MCP server - install =====
echo  Folder: "%CD%"
echo.

echo  Before you go on: fully quit Claude (right-click the Claude icon next to the clock, Quit),
echo  so it cannot overwrite its settings while this installs.
pause

rem --- 1. find 64-bit Python 3.10+: py launcher 3.13 ... 3.10, then py -3, then python ----
rem     (each candidate is checked; :trypy and :trypython are at the end of this file)
set "PY="
rem     The probe prints PYOK; findstr looks for it (an exit code alone can be a negative crash code).
set "CHECK=import sys; print('PYOK' if sys.version_info >= (3, 10) and sys.maxsize > 2**32 else 'PYBAD')"
call :trypy -3.13
if not defined PY call :trypy -3.12
if not defined PY call :trypy -3.11
if not defined PY call :trypy -3.10
if not defined PY call :trypy -3
if not defined PY call :trypython
if not defined PY goto nopython
echo  Python: %PY%

rem --- 2. private Python environment for the server (.venv) ------------------------------
rem     An existing .venv is kept only if its python.exe passes the same probe; otherwise it is made again.
if not exist ".venv\Scripts\python.exe" goto makevenv
".venv\Scripts\python.exe" -c "%CHECK%" 2>nul | findstr /c:"PYOK" >nul
if %errorlevel% equ 0 goto havevenv
echo  The existing .venv is not a working 64-bit Python 3.10 or newer: making it again ...
rmdir /s /q ".venv"
if exist ".venv" goto venvbusy
:makevenv
echo  Creating the Python environment ...
%PY% -m venv .venv
if %errorlevel% neq 0 goto failed
".venv\Scripts\python.exe" -c "%CHECK%" 2>nul | findstr /c:"PYOK" >nul
if %errorlevel% neq 0 goto failed
:havevenv
echo  Installing the MCP package (needs internet, about a minute) ...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if %errorlevel% neq 0 goto failed

rem --- 3. settings (kept if you already edited them) ---------------------------------------
if not exist settings.json copy /y settings.default.json settings.json >nul

rem --- 4. tell Claude Desktop and Claude Code about the server -----------------------------
echo.
echo  Registering the server with Claude ...
".venv\Scripts\python.exe" -m sofistik_mcp.configure_clients
if %errorlevel% neq 0 goto regfailed

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

:venvbusy
echo.
echo  The old .venv folder could not be removed: a program is still using it.
echo  Fully quit Claude (and close any window that runs the self-test), then run this again.
pause
exit /b 1

:failed
echo.
echo  Something went wrong above. Send Claude a screenshot of this window.
pause
exit /b 1

:regfailed
echo.
echo  Registering the server with Claude failed: see the NOT CHANGED lines above.
echo  Fix or rename the file named there, then run install.bat again.
pause
exit /b 1

rem --- subroutines: set PY if the candidate is a 64-bit Python 3.10 or newer ---------------
:trypy
py %1 -c "%CHECK%" 2>nul | findstr /c:"PYOK" >nul
if %errorlevel% equ 0 set "PY=py %1"
exit /b 0

:trypython
python -c "%CHECK%" 2>nul | findstr /c:"PYOK" >nul
if %errorlevel% equ 0 set "PY=python"
exit /b 0
