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
title Shawei Duplicate Check

echo.
echo ================================
echo  Shawei Duplicate Check
echo ================================
echo.

set "PERIOD="
set /p "PERIOD=Input current period, example 125: "
if "%PERIOD%"=="" (
  echo No period input. Exit.
  pause
  exit /b 1
)

echo.
echo Running period %PERIOD%, fixed 10-period window
echo.

%PY_CMD% shawei_consecutive_duplicate_checker.py --period %PERIOD%

echo.
echo Finished. Check files:
echo %PERIOD% period same data sites txt
echo %PERIOD% period failed txt
pause
