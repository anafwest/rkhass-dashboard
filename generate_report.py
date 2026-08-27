# -*- coding: utf-8 -*-
# توليد تقرير يومي عن سير التشغيل + تذكير نهاية فترة الـ10 أيام
import sys, os, json
from datetime import datetime, date
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')

PROJ = r"C:\Users\anaf\OneDrive - Riyadh Municipality\المستندات\Default Project\rkhass-dashboard"
HIST = os.path.join(PROJ, "monitor_history.jsonl")
REPORT = os.path.join(PROJ, "daily_report.md")
START = date(2026, 8, 27)
TOTAL_DAYS = 10

day_counters = {"BLS": defaultdict(lambda: {"ok": 0, "fail": 0}),
                "UPS": defaultdict(lambda: {"ok": 0, "fail": 0})}
push_last = ""
last = {"bls": "no data", "ups": "no data", "rows": "no data"}
try:
    with open(HIST, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            ts = e.get("ts", "")
            d = ts[:10]
            if e.get("label") == "pipeline":
                last["bls"] = e.get("bls", "?")
                last["ups"] = e.get("ups", "?")
                last["push"] = e.get("push", "")
            elif e.get("label") in day_counters and d:
                key = e["label"]
                if e.get("status") == "OK":
                    day_counters[key][d]["ok"] += 1
                else:
                    day_counters[key][d]["fail"] += 1
except FileNotFoundError:
    pass

today = date.today()
day_num = (today - START).days + 1
done = max(0, min(day_num, TOTAL_DAYS))
prcnt = round(done / TOTAL_DAYS * 100)

def read_tail(path, n=0):
    try:
        with open(os.path.join(PROJ, path), encoding="utf-8", errors="replace") as f:
            lines = [l.strip() for l in f if l.strip()]
        return lines[-n] if n else lines[-1]
    except Exception:
        return "غير متاح"

dates = sorted(day_counters["BLS"])
lines = []
if day_num > TOTAL_DAYS:
    lines.append("\n# ✅ انتهت فترة المراقبة العشرينية بنجاح\n")
elif done >= TOTAL_DAYS:
    lines.append("\n# ✅ هذا هو اليوم الأخير من المراقبة — تنتهي اليوم\n")
else:
    lines.append(f"\n# 📌 يوم {done} من {TOTAL_DAYS} ({prcnt}%) — متبقٍ {TOTAL_DAYS - done} {('يوم' if TOTAL_DAYS - done < 3 else 'أيام')}\n")

lines.append(f"آخر تشغيل كامل: BLS={last.get('bls')} | UPS={last.get('ups')} | الرفع={last.get('push', '')}")
lines.append(f"آخر سطر بسجل BLS: {read_tail('scraper_log.txt')}")
lines.append(f"آخر سطر بسجل UPS: {read_tail('ups_scraper_log.txt')}\n")

lines.append("## ملخص العمليات اليومية (OK / FAIL)\n")
lines.append("| التاريخ | BLS | UPS |")
lines.append("|---|---|---|")
for d in dates:
    b = day_counters["BLS"][d]
    u = day_counters["UPS"][d]
    lines.append(f"| {d} | {b['ok']} / {b['fail']} | {u['ok']} / {u['fail']} |")

if not dates:
    lines.append("| _لا توجد عمليات بعد_ | | |")

fails = sum(b["fail"] for b in day_counters["BLS"].values()) + \
        sum(u["fail"] for u in day_counters["UPS"].values())
lines.append(f"\n**إجمالي حالات الفشل خلال الفترة: {fails}**")
if fails == 0:
    lines.append("الحالة: مستقرة — لا حاجة لأي تدخل.")
else:
    lines.append("الحالة: توجد إخفاقات أعلاه — مراجعة سجل `monitor_log.txt`.")

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("تم تحديث daily_report.md")