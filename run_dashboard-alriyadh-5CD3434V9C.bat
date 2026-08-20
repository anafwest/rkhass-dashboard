@echo off
chcp 65001 >nul
title داشبورد رخص البناء
cd /d "C:\Users\HPProBook440G9\OneDrive - Riyadh Municipality\سطح المكتب\اوبن كود"
set PYTHONIOENCODING=utf-8
set STREAMLIT_EMAIL=
start /B "" "C:\Users\HPProBook440G9\AppData\Local\Programs\Python\Python313\python.exe" -m streamlit run dashboard.py
timeout /t 5 /nobreak >nul
start http://localhost:8501
echo.
echo تم تشغيل الداشبورد على http://localhost:8501
echo.
pause
