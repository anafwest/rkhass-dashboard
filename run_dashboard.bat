@echo off
chcp 65001 >nul
cd /d "%~dp0"
set STREAMLIT_EMAIL=
start /B "" python -m streamlit run "%~dp0dashboard.py"
echo.
echo  تم تشغيل الداشبورد على http://localhost:8501
echo.
pause
