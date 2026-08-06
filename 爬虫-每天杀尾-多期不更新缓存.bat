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
title Shawei Multi Period Crawler

echo.
echo ==========================================
echo  Shawei Multi Period Crawler
echo  Multi period mode, no recent_10_cache update
echo ==========================================
echo.

set "PERIODS="
set /p "PERIODS=Input periods, example 187 188 189 190: "
if "%PERIODS%"=="" (
  echo No periods input. Exit.
  pause
  exit /b 1
)

echo.
echo Running periods: %PERIODS%
echo.

%PY_CMD% shawei_multi_period_crawler.py --periods "%PERIODS%"
set "CRAWLER_EXIT=%ERRORLEVEL%"

echo.
echo Finished. Check each period success/fail txt and the multi-period summary report.
pause
exit /b %CRAWLER_EXIT%
