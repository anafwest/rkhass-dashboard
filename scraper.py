import ssl, os, urllib3
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context

import pandas as pd
import shutil, subprocess
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)

def save(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with open("scraper_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)

save("=" * 60)
save("بدء معالجة البيانات المحمولة يدوياً")

SOURCE_FILE = None
for name in ["data.xls", "data.xlsx", "طلبات.xls", "الطلبات.xls"]:
    path = os.path.join(PROJECT_DIR, name)
    if os.path.exists(path):
        SOURCE_FILE = path
        break

if not SOURCE_FILE:
    available = [f for f in os.listdir(PROJECT_DIR) if f.endswith(('.xls', '.xlsx')) and not f.startswith('~')]
    save(f"لم يتم العثور على ملف مصدري. الملفات المتاحة: {available}")
    save("الرجاء نسخ ملف البيانات من البوابة إلى مجلد المشروع")
    os._exit(1)

save(f"الملف المصدري: {os.path.basename(SOURCE_FILE)} ({os.path.getsize(SOURCE_FILE) // 1024} KB)")

try:
    if SOURCE_FILE.endswith('.xlsx'):
        df = pd.read_excel(SOURCE_FILE, engine='openpyxl')
    else:
        df = pd.read_excel(SOURCE_FILE, engine='xlrd')

    save(f"تم قراءة {len(df)} صف و {len(df.columns)} عمود")
    save(f"الأعمدة: {list(df.columns[:10])}")

    if len(df) < 10:
        save("تحذير: الملف يحتوي على fewer من 10 صفوف - قد يكون خاطئاً")
        os._exit(1)

    output = os.path.join(PROJECT_DIR, "data.xlsx")
    df.to_excel(output, index=False, engine='openpyxl')
    save(f"تم حفظ data.xlsx ({os.path.getsize(output) // 1024} KB)")

    save("=== رفع البيانات إلى GitHub ===")
    os.chdir(PROJECT_DIR)
    subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
    commit_msg = f"تحديث البيانات - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    result = subprocess.run(["git", "commit", "-m", commit_msg], capture_output=True, text=True)
    if result.returncode == 0:
        save("تم حفظ التغييرات في Git")
        push_result = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True, timeout=60)
        if push_result.returncode == 0:
            save("تم رفع البيانات إلى GitHub بنجاح - Streamlit Cloud سيتحدث تلقائياً")
        else:
            save(f"خطأ في الرفع: {push_result.stderr[:200]}")
    else:
        save("لا توجد تغييرات جديدة للرفع")

    save("تمت المعالجة بنجاح")

except Exception as e:
    save(f"خطأ في المعالجة: {e}")
    os._exit(1)
