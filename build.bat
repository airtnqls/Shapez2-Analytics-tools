@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Build Shapez2 TMAM Web Studio 2.1.0

where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js 20.9 or newer is required to rebuild.
  echo The prebuilt release can still be opened with run.bat without Node.js.
  pause
  exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm was not found. Reinstall the official Node.js package.
  pause
  exit /b 1
)

node -e "const [a,b]=process.versions.node.split('.').map(Number); if(a<20 || (a===20 && b<9)){console.error('[ERROR] Node.js 20.9 or newer is required. Current: '+process.versions.node); process.exit(1)}"
if errorlevel 1 (
  pause
  exit /b 1
)

echo Node:
node -v
echo npm:
call npm -v

echo.
echo Installing exact dependencies from package-lock.json...
call npm ci --no-audit --no-fund
if errorlevel 1 goto :failed

echo.
echo Running tests, typecheck, production build, and smoke tests...
call npm run check
if errorlevel 1 goto :failed

echo.
echo [OK] Build completed. Starting the app...
call "%~dp0run.bat"
exit /b %ERRORLEVEL%

:failed
echo.
echo [ERROR] Build failed. The complete error is shown above.
pause
exit /b 1
