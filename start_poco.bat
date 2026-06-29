@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found.
    echo Please run install.bat first.
    pause
    exit /b
)

.venv\Scripts\python.exe -m streamlit run poco/ui/app.py --server.port=8501

pause