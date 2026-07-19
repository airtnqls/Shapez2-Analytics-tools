@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Shapez2 TMAM Web Studio 2.1.0

if not exist "out\index.html" (
  echo [ERROR] out\index.html is missing. Run build.bat first.
  pause
  exit /b 1
)

python -m backend.server --port 4173
if errorlevel 1 pause
