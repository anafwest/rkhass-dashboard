@echo off
chcp 65001 >nul
echo __________________________________________________
echo.
echo    إعداد المهمة اليومية لسحب البيانات
echo    الساعة 8:00 صباحاً يومياً
echo __________________________________________________
echo.
schtasks /create /tn "rkhass-daily-scraper" /tr "\"C:\Users\anaf\OneDrive - Riyadh Municipality\المستندات\Default Project\rkhass-dashboard\run_scraper.bat\"" /sc daily /st 08:00 /f
echo.
echo ✅ تم إعداد المهمة. اضغط أي مفتاح للخروج
pause
