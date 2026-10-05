# -*- coding: utf-8 -*-
"""verify_dashboard.py — فحص شامل لبيانات الداش بورد: تكرار؟ توزيع صحيح؟

يُنتج تقريراً مفصلاً (stdout) على البيانات الحالية:
  1) ups_requests.xlsx — تكرار رقم الطلب/رقم الرخصة + توزيع الحالة/الخدمة/الحي/السنة + فراغات
  2) data.xlsx (BLS)   — تكرار + توزيع نوع الخدمة/المرحلة/الجهة/السنة + فراغات
التشغيل: python verify_dashboard.py
"""
import sys, os, re
sys.stdout.reconfigure(encoding="utf-8")
import pandas as pd

PROJ = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJ)

def clean(df):
    df = df.copy().fillna("")
    for c in df.columns:
        df[c] = df[c].astype(str).str.strip().replace({"nan": "", "None": "", "NaT": ""})
    return df

def dup_report(df, key, label):
    out = []
    n_total = len(df)
    n_unique = df[key].nunique()
    n_dup_keys = df.duplicated(subset=[key]).sum()
    out.append(f"[{label}] المعرّف: {key}")
    out.append(f"  الصفوف الكلية: {n_total:,} | قيم فريدة: {n_unique:,} | تكرارات (صفوف إضافية): {n_dup_keys:,}")
    if n_dup_keys:
        seen, dups = set(), []
        for v in df[key]:
            if v in seen:
                dups.append(v)
            seen.add(v)
        out.append(f"  أول 10 مفاتيح مكررة: {dups[:10]}")
    empties = int((df[key] == "").sum())
    if empties:
        out.append(f"  ⚠ خانات فارغة للمعرّف: {empties:,}")
    return out, n_unique

def hist(df, col, label, top=None, split_multi=None):
    out = []
    s = df[col]
    if split_multi:
        items = []
        for v in s:
            for part in re.split(r"[،,،]+", v):
                part = part.strip()
                if part:
                    items.append(part)
        ser = pd.Series(items)
        out.append(f"[{label}] توزيع '{col}' (بعد فصل القيم المتعددة): عدد قيم {len(ser):,}")
    else:
        ser = s[s != ""]
        out.append(f"[{label}] توزيع '{col}': عدد قيم {len(ser):,}")
    vc = ser.value_counts()
    n_uniq = len(vc)
    out.append(f"  عدد الفئات المميزة: {n_uniq:,}")
    shown = vc.head(top if top else n_uniq)
    for k, v in shown.items():
        out.append(f"    {k or '(فارغ)'}: {v:,}  ({v/len(ser)*100:.1f}%)")
    n_empty = int((s == "").sum())
    out.append(f"  خانات فارغة: {n_empty:,}")
    return out

def report_ups(path):
    out = ["=" * 64, f"UPS — {path} ({os.path.getmtime(path) and __import__('datetime').datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M:%S')})"]
    df = clean(pd.read_excel(path))
    out.append(f"أعمدة: {list(df.columns)}")
    out.append(f"إجمالي الصفوف: {len(df):,}")
    # التكرار
    r, _ = dup_report(df, "رقم الطلب", "UPS")
    out += r
    r, _ = dup_report(df, "رقم الرخصة", "UPS")
    out += r
    # فراغات
    empty_info = []
    for c in df.columns:
        n = int((df[c] == "").sum())
        if n:
            empty_info.append(f"    {c}: {n:,} ({n/len(df)*100:.1f}%)")
    out.append("خرائط فارغة (أعمدة بها فراغ):")
    out += empty_info if empty_info else ["    لا يوجد"]
    # توزيع الحالة مع تحقق العملية KPI
    kpi_map = {
        "مكتمل": "مكتمل", "استكمال التعديلات": "استكمال التعديلات",
        "مرفوض": "مرفوض", "بانتظار السداد": "بانتظار السداد", "ملغي": "ملغي",
    }
    status = df["حالة الطلب"]
    vc = status[status != ""].value_counts()
    out.append(f"توزيع حالة الطلب (فئات: {len(vc):,}):")
    covered = set()
    for k, v in vc.items():
        grp = "قيد العمل" if "قيد العمل" in k else kpi_map.get(k, k)
        out.append(f"    {k or '(فارغ)'}: {v:,}  ({v/len(df)*100:.1f}%)  [مجموعة: {grp}]")
        covered.add(grp)
    known = {"مكتمل", "استكمال التعديلات", "مرفوض", "قيد العمل", "بانتظار السداد", "ملغي"}
    unknown = covered - known
    out.append(f"  مجموعات لا يغطيها الداش بورد (ستظهر ضمن الإجمالي فقط بدون KPI): {sorted(unknown) if unknown else 'لا يوجد'}")
    # تحقق الجمع
    out.append(f"  تحقق: مجموع الحالة {int(vc.sum()):,} مقابل الإجمالي {len(df):,} → {'متطابق' if int(vc.sum()) == len(df) else 'اختلاف!'}")
    # نوع الخدمة
    out += hist(df, "نوع الخدمة", "UPS")
    # الحي
    out += hist(df, "الحي", "UPS", split_multi=True, top=12)
    # السنة الهجرية
    def hy(s):
        m = re.search(r"(\d{3,4})\s*هـ", s)
        return ("هـ " + m.group(1)) if m else "غير محدد"
    ys = df["تاريخ الطلب"].apply(hy)
    out.append("توزيع السنة الهجرية (من تاريخ الطلب):")
    for k, v in ys.value_counts().items():
        out.append(f"    {k}: {v:,}  ({v/len(df)*100:.1f}%)")
    return out

def report_bls(path):
    out = ["=" * 64, f"BLS — {path}"]
    df = clean(pd.read_excel(path))
    out.append(f"أعمدة: {list(df.columns)}")
    out.append(f"إجمالي الصفوف: {len(df):,}")
    r, _ = dup_report(df, "رقم الطلب", "BLS")
    out += r
    r, _ = dup_report(df, "رقم الرخصة", "BLS")
    out += r
    # فراغات
    empty_info = []
    for c in df.columns:
        n = int((df[c] == "").sum())
        if n:
            empty_info.append(f"    {c}: {n:,} ({n/len(df)*100:.1f}%)")
    out.append("خرائط فارغة:")
    out += empty_info if empty_info else ["    لا يوجد"]
    out += hist(df, "نوع الخدمة", "BLS", top=15)
    out += hist(df, "وصف المرحلة", "BLS", top=20)
    out += hist(df, "الجهة", "BLS", top=10)
    out += hist(df, "السنة", "BLS", top=10)
    # توزيع ميلادي حسب السنة للتأكد
    def gy(s):
        m = re.search(r"(\d{4})", str(s))
        return m.group(1) if m else "غير محدد"
    yc = df["تاريخ الطلب ميلادي"].apply(gy)
    out.append("توزيع السنة الميلادية (من تاريخ الطلب ميلادي):")
    for k, v in yc.value_counts().sort_index().items():
        out.append(f"    {k}: {v:,}")
    # تحقق من مفتاح طلب الخدمة
    r, _ = dup_report(df, "طلب الخدمة", "BLS")
    out.append("[BLS] تحقق من مفتاح طلب الخدمة:")
    out += r
    return out

if __name__ == "__main__":
    for block in report_ups("ups_requests.xlsx") + report_bls("data.xlsx"):
        print(block)