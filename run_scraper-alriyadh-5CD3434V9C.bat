@echo off
chcp 65001 >nul
title سكريبت سحب بيانات رخص البناء
cd /d "C:\Users\HPProBook440G9\OneDrive - Riyadh Municipality\سطح المكتب\اوبن كود"
set PYTHONIOENCODING=utf-8
echo جاري تشغيل السكريبت...
echo 1- Chrome بيفتح على صفحة البوابة
echo 2- سجل دخولك (يوزر + باسورد + كابتشا + كود OTP)
echo 3- بعدها السكريبت يكمل تلقائي
echo.
python scraper.py
echo.
pause
