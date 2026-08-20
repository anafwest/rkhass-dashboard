@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo __________________________________________________
echo.
echo    سحب البيانات من بوابة الدخول الموحد
echo    سجل دخولك في المتصفح ثم اضغط Enter
echo __________________________________________________
echo.
"C:\Users\anaf\AppData\Local\Programs\Python\Python312\python.exe" scraper.py
echo.
echo ✅ تم. اضغط أي مفتاح للخروج
pause
