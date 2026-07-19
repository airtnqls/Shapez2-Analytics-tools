@echo off
setlocal
cd /d "%~dp0"
pushd "legacy_desktop"
python gui.py
set EXIT_CODE=%ERRORLEVEL%
popd
if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%
