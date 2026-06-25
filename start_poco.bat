@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   POCO — Word 模板自动生成工具
echo ============================================
echo.
echo Starting POCO...
echo UI will open at http://localhost:8501
echo.
echo Press Ctrl+C in this window to stop.
echo ============================================
echo.
python -m streamlit run poco/ui/app.py --server.port=8501
pause
