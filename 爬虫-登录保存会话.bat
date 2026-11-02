@echo off
set "PY_CMD="
py -3 --version >nul 2>nul
if not errorlevel 1 set "PY_CMD=py -3"
if not defined PY_CMD (
  python --version >nul 2>nul
  if not errorlevel 1 set "PY_CMD=python"
)
if not defined PY_CMD (
  echo Cannot find Python. Please install Python and add it to PATH.
  pause
  exit /b 1
)

cd /d "%~dp0"
title Shawei Browser Login
%PY_CMD% shawei_browser_login.py
set "LOGIN_EXIT=%ERRORLEVEL%"
if not "%LOGIN_EXIT%"=="0" (
  echo.
  echo Login helper failed.
)
pause
exit /b %LOGIN_EXIT%
