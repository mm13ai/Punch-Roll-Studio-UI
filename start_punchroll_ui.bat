@echo off
setlocal
cd /d "%~dp0"
title Punch and Roll Studio
set "PY="
py -3.13 -c "import sys" >nul 2>nul && set "PY=py -3.13"
if not defined PY py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY goto nopy
%PY% punchroll_ui.py --auto-setup %*
if errorlevel 1 pause
exit /b
:nopy
echo Python 3.10 or newer was not found.
echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH", then run this again.
pause
