@echo off
setlocal enabledelayedexpansion
title WebToApk Packager
cd /d "%~dp0"

set "PYEXE="

rem 1) Doubao bundled runtime python (filesystem path, no PATH needed)
for /d %%B in ("%LOCALAPPDATA%\Doubao\User Data\sandbox_runtime\bases\*") do (
  if not defined PYEXE if exist "%%B\python\python.exe" set "PYEXE=%%B\python\python.exe"
)

rem 2) common python install locations
if not defined PYEXE (
  for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "C:\Python314\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
  ) do (
    if not defined PYEXE if exist %%~P set "PYEXE=%%~P"
  )
)

rem 3) python on PATH as last resort
if not defined PYEXE (
  python -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PYEXE=python"
)

if not defined PYEXE (
  echo [ERROR] Python not found.
  echo Please install Python 3.10 or newer from:
  echo https://www.python.org/downloads/
  echo Remember to check "Add Python to PATH" during install.
  pause
  exit /b 1
)

echo Using Python: !PYEXE!

rem 4) check dependencies, install if missing
"!PYEXE!" -c "import PySide6.QtWebEngineWidgets" >nul 2>nul
if errorlevel 1 (
  echo First run: installing PySide6 ^(about 200MB, please wait^)...
  "!PYEXE!" -m pip install PySide6 -i https://mirrors.huaweicloud.com/repository/pypi/simple --retries 10 --timeout 60
  if errorlevel 1 (
    echo Mirror failed, trying official PyPI ...
    "!PYEXE!" -m pip install PySide6 --retries 10 --timeout 60
  )
)

rem 5) launch the app
"!PYEXE!" -m packager.main
if errorlevel 1 (
  echo.
  echo Program exited with an error. See crash.log for details.
  pause
)
endlocal
