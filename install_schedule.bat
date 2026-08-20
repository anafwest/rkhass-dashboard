@echo off
chcp 65001 >nul
echo جاري إنشاء مهمة مجدولة لسحب البيانات...
schtasks /create /tn "سحب بيانات الرخص" /tr "python \"C:\Users\HPProBook440G9\OneDrive - Riyadh Municipality\سطح المكتب\اوبن كود\scraper.py\"" /sc daily /st 08:00 /ri 180 /du 12:00 /f
schtasks /create /tn "سحب بيانات الرخص - 11" /tr "python \"C:\Users\HPProBook440G9\OneDrive - Riyadh Municipality\سطح المكتب\اوبن كود\scraper.py\"" /sc daily /st 11:00 /f
schtasks /create /tn "سحب بيانات الرخص - 14" /tr "python \"C:\Users\HPProBook440G9\OneDrive - Riyadh Municipality\سطح المكتب\اوبن كود\scraper.py\"" /sc daily /st 14:00 /f
echo تم بنجاح
pause
