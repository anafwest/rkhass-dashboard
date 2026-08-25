import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_excel('data.xlsx')
print(f'Loaded {len(df)} rows')

# Test process_data logic
cols = list(df.columns)
print(f'Columns: {cols}')

col_map = {
    "طلب الخدمة": "رقم طلب الخدمة", "نوع الخدمة": "نوع الخدمة",
    "الجهة": "الجهة", "الجهه": "الجهة",
    "السنة": "السنة", "سنه الرخصة": "سنه الرخصة",
    "المالك": "المالك", "الملالك": "المالك",
}
col_rename = {}
for c in cols:
    cs = c.strip()
    if cs in col_map:
        col_rename[c] = col_map[cs]
    elif "ميلادي" in cs and "تاريخ" in cs and "طلب" in cs:
        col_rename[c] = "تاريخ الطلب ميلادي"
    elif "ميلادي" in cs and "تاريخ" in cs and "مراجعة" in cs:
        col_rename[c] = "تاريخ المراجعة ميلادي"

print(f'Rename map: {col_rename}')
df.rename(columns=col_rename, inplace=True)

for dcol in ["تاريخ الطلب ميلادي", "تاريخ المراجعة ميلادي"]:
    if dcol in df.columns:
        df[dcol] = df[dcol].astype(str)
        df[dcol] = pd.to_datetime(df[dcol], format="%d/%m/%Y", errors="coerce")
        if df[dcol].isna().all():
            df[dcol] = pd.to_datetime(df[dcol].astype(str).str.strip(), errors="coerce")
        print(f'{dcol}: {df[dcol].notna().sum()} parsed, {df[dcol].isna().sum()} null')

if "تاريخ الطلب ميلادي" in df.columns:
    df["الشهر"] = df["تاريخ الطلب ميلادي"].dt.month
    df["اسم الشهر"] = df["تاريخ الطلب ميلادي"].dt.strftime("%Y-%m")
    df["اليوم"] = df["تاريخ الطلب ميلادي"].dt.day_name()
    if "تاريخ المراجعة ميلادي" in df.columns:
        df["مدة الإنجاز (أيام)"] = (df["تاريخ المراجعة ميلادي"] - df["تاريخ الطلب ميلادي"]).dt.days
        df["مدة الإنجاز (أيام)"] = df["مدة الإنجاز (أيام)"].clip(lower=0)
        print(f'Muda: {df["مدة الإنجاز (أيام)"].notna().sum()} valid')

print(f'\nAll good! {len(df)} rows ready')
