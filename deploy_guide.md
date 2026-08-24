# نشر داشبورد رخص البناء على Azure

## 1. إنشاء App Service في Azure

1. ادخل إلى https://portal.azure.com
2.新建 > Web App
3. الإعدادات:
   - **الاسم**: `rkhass-dashboard` (أو أي اسم متاح)
   - **Runtime Stack**: Python 3.12
   - **Region**: Saudi Arabia Central (وسط السعودية)
   - **Sku**: F1 (Free) أو B1 (~40 ريال/شهر)

## 2. رفع الملفات

```bash
# عبر Git أو FTP أو Azure CLI
az webapp up --name rkhass-dashboard --runtime "python:3.12"
```

أو استخدم FTP:
- المستخدم والرقم السري من Azure Portal > Deployment Center

## 3. إعداد البيانات

- ارفع ملف `data.xls` إلى مسار التطبيق
- عدّل كلمة السر في `.streamlit/secrets.toml`

## 4. إعداد Startup Command

في Azure Portal > App Service > Configuration:
```
streamlit run dashboard.py --server.port 8000 --server.address 0.0.0.0
```

## 5. تشغيل

- الرابط: `https://rkhass-dashboard.azurewebsites.net`
- كلمة المرور الافتراضية: `1234` (عدلها بعد أول دخول)

## 6. تحديث البيانات

كل ما تشغّل السكرابر ويتحدّث `الطلبات.xls`، ارفع الملف إلى Azure (يدوياً أو تلقائياً).
