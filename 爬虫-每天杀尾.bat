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
title Shawei Crawler

echo.
echo ================================
echo  Shawei Crawler
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
echo Running period %PERIOD%
echo.

where py >nul 2>nul
if %errorlevel%==0 (
  %PY_CMD% shawei_crawler.py --period %PERIOD%
) else (
  %PY_CMD% shawei_crawler.py --period %PERIOD%
)
set "CRAWLER_EXIT=%ERRORLEVEL%"
if not "%CRAWLER_EXIT%"=="0" (
  echo.
  echo Crawler or recent 10 cache update reported errors.
  pause
  exit /b %CRAWLER_EXIT%
)

echo.
echo Finished. Check files:
echo %PERIOD% period txt
echo %PERIOD% period failed txt
echo recent_10_cache.json
pause
