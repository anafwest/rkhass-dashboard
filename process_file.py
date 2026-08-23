import os, subprocess
from datetime import datetime
import pandas as pd

os.chdir(r"C:\Users\anaf\OneDrive - Riyadh Municipality\المستندات\Default Project\rkhass-dashboard")

df = pd.read_html("data.xls", encoding="utf-8")[0]
print(f"Read {len(df)} rows, {len(df.columns)} cols")

df.columns = [
    "طلب الخدمة", "السنة", "نوع الخدمة", "وصف المرحلة", "الجهة",
    "تاريخ الطلب", "تاريخ الطلب ميلادي", "رقم الرخصة", "سنة الرخصة",
    "نوع الهوية", "المالك", "رقم الهوية", "تاريخ المراجعة",
    "تاريخ المراجعة ميلادي", "رقم الطلب"
]

print(f"Sample: {df.iloc[0].to_dict()}")
df.to_excel("data.xlsx", index=False, engine="openpyxl")
print(f"Saved data.xlsx ({os.path.getsize('data.xlsx') // 1024} KB)")

subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
r = subprocess.run(
    ["git", "commit", "-m", f"update data {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
    capture_output=True, text=True
)
print(f"Commit: {r.returncode}")
if r.returncode == 0:
    p = subprocess.run(
        ["git", "push", "origin", "main"],
        capture_output=True, text=True, timeout=60
    )
    print(f"Push: {p.returncode} {p.stderr[:200]}")
else:
    print(f"No changes: {r.stderr[:200]}")
print("Done")
