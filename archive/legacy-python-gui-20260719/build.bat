@echo off
chcp 65001 >nul
echo ========================================
echo Shapez2Analyzer Build Started
echo ========================================

REM Check and install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Run PyInstaller build
echo Starting PyInstaller build...
pyinstaller --noconfirm gui.spec

echo.
echo ========================================
echo Build completed successfully!
echo Shapez2Analyzer.exe is in the dist folder
echo ========================================
pause
