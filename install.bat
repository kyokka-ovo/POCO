@echo off
cd /d "%~dp0"

echo ============================================
echo POCO Environment Setup
echo ============================================
echo.

echo [1/4] Creating virtual environment...
py -m venv .venv
if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
)

echo [2/4] Activating...
call .venv\Scripts\activate

echo [3/4] Upgrading pip...
python -m pip install --upgrade pip

echo [4/4] Installing dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Installation completed.
echo Please run start_poco.bat
pause