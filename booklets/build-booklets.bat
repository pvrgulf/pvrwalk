@echo off
setlocal
title PVR Walk - Build Booklets
cd /d "%~dp0"

echo.
echo ==========================================
echo       PVR Walk - Booklet Builder
echo ==========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found.
    echo Install Python and enable "Add python.exe to PATH".
    pause
    exit /b 1
)

python -c "import pymupdf, PIL" >nul 2>nul
if errorlevel 1 (
    echo Installing PyMuPDF and Pillow...
    python -m pip install pymupdf pillow
    if errorlevel 1 (
        echo ERROR: Package installation failed.
        pause
        exit /b 1
    )
)

echo.
echo Building booklets...
echo.
python tools\build_booklets.py

if errorlevel 1 (
    echo.
    echo BUILD FAILED.
    pause
    exit /b 1
)

echo.
echo BUILD COMPLETE.
echo Open index.html to test the booklet library.
echo.
pause
