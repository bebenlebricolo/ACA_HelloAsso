@echo off
chcp 65001 >nul

echo ========================================
echo  HelloAsso Syncer - Build Script
echo ========================================
echo.

 REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if %errorlevel% neq 0 (
    echo PyInstaller is not installed!
    echo Please run: pip install pyinstaller
    pause
    exit /b 1
)

echo Building with PyInstaller...
echo This may take a few minutes...
echo.

python build.py

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo  Build Successful!
    echo ========================================
    echo.
    echo The executable has been created in the dist/ directory.
    echo You can now distribute the HelloAssoSyncer.exe file.
    echo.
) else (
    echo.
    echo ========================================
    echo  Build Failed!
    echo ========================================
)

pause
