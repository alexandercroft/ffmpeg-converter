@echo off
REM FFMPEG converter — Windows launcher.
setlocal
cd /d "%~dp0"
set PORT=8000

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3 not found. Install it:  winget install Python.Python.3.12
  echo   or download from https://www.python.org/downloads/
  pause
  exit /b 1
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo FFmpeg not found. Install it:  winget install Gyan.FFmpeg
  echo   or download from https://www.gyan.dev/ffmpeg/builds/  and add it to PATH
  pause
  exit /b 1
)

echo.
echo   FFMPEG // CONVERTER  -^>  http://localhost:%PORT%
echo   Ctrl+C - stop
echo.
start "" "http://localhost:%PORT%"
python server.py
