@echo off
chcp 65001 >nul
cd /d "C:\Users\anaf\OneDrive - Riyadh Municipality\المستندات\Default Project\rkhass-dashboard"
echo [%date% %time%] تشغيل معالجة البيانات >> scraper_log.txt
"C:\Users\anaf\AppData\Local\Programs\Python\Python312\python.exe" scraper.py
echo [%date% %time%] انتهت العملية >> scraper_log.txt
