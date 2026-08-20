@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [%date% %time%] تشغيل تلقائي للسحب >> scraper_log.txt
"C:\Users\anaf\AppData\Local\Programs\Python\Python312\python.exe" scraper.py
echo [%date% %time%] انتهت العملية >> scraper_log.txt
