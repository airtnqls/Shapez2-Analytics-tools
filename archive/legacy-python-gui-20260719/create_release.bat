@echo off
chcp 65001 >nul
echo ========================================
echo Creating GitHub Release Package for Shapez2Analyzer
echo ========================================

REM Version info (modify if needed)
set VERSION=1.0.0
set RELEASE_NAME=Shapez2Analyzer-Windows-x64-v%VERSION%

echo Version: %VERSION%
echo Release Name: %RELEASE_NAME%

REM Remove existing package
if exist "%RELEASE_NAME%.zip" del "%RELEASE_NAME%.zip"

REM Check if dist folder exists
if not exist "dist" (
    echo ERROR: dist folder not found. Please run build first.
    pause
    exit /b 1
)

REM Check Windows executable
if not exist "dist\Shapez2Analyzer.exe" (
    echo ERROR: Shapez2Analyzer.exe not found. Please run build first.
    pause
    exit /b 1
)

echo.
echo Creating release package...

REM Use 7-Zip if available, otherwise use PowerShell
where 7z >nul 2>nul
if %ERRORLEVEL% == 0 (
    echo Using 7-Zip for compression...
    7z a -tzip "%RELEASE_NAME%.zip" "dist\Shapez2Analyzer.exe"
) else (
    echo Using PowerShell for compression...
    powershell -command "Compress-Archive -Path 'dist\Shapez2Analyzer.exe' -DestinationPath '%RELEASE_NAME%.zip' -Force"
)

if exist "%RELEASE_NAME%.zip" (
    echo.
    echo SUCCESS: %RELEASE_NAME%.zip created!
    echo.
    echo GitHub Release Instructions:
    echo 1. Create new Release on GitHub
    echo 2. Tag: v%VERSION%
    echo 3. Title: Shapez2Analyzer %VERSION% (Windows)
    echo 4. Attach the zip file above
    echo.
    echo File size: 
    for %%A in ("%RELEASE_NAME%.zip") do echo %%~zA bytes
) else (
    echo ERROR: Failed to create package.
)

pause
