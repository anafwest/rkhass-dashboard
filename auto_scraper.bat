@echo off
chcp 65001 >nul
cd /d "C:\Users\anaf\OneDrive - Riyadh Municipality\المستندات\Default Project\rkhass-dashboard"
echo [%date% %time%] تشغيل تلقائي للسحب >> scraper_log.txt
taskkill /F /IM chrome.exe /T >nul 2>&1
timeout /t 3 /nobreak >nul
"C:\Users\anaf\AppData\Local\Programs\Python\Python312\python.exe" scraper.py
echo [%date% %time%] انتهت العملية >> scraper_log.txt
