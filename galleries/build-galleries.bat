
@echo off
cd /d "%~dp0"

echo.
echo ========================================
echo       CAMBO WALKS GALLERY BUILDER
echo ========================================
echo.

where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=py"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo Python could not be found.
        echo Please install Python from https://www.python.org/
        pause
        exit /b 1
    )
    set "PYTHON=python"
)

%PYTHON% -c "import PIL" >nul 2>&1
if errorlevel 1 (
    echo Installing the Pillow image library...
    %PYTHON% -m pip install --user Pillow
    if errorlevel 1 (
        echo.
        echo Pillow installation failed.
        pause
        exit /b 1
    )
)

echo.
echo Building the galleries...
echo.

%PYTHON% build_galleries.py

echo.
pause
