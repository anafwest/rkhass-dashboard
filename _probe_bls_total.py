# -*- coding: utf-8 -*-
"""مطابقة عدد سجلات بوابة BLS 8510 مع ملف data.xlsx (فحص اكتمال)."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Users\anaf\OneDrive - Riyadh Municipality\المستندات\Default Project\rkhass-dashboard")
import scraper as S
import update_bls_fast as F

ws, send = F.fresh_tab()
if not send:
    print("FATAL: لم يُفتح تبويب BLS (جلسة؟)")
    raise SystemExit(1)
info = S.read_info(send)
print("portal total:", info.get("total"), "| perPage:", info.get("perPage"),
      "| pages:", info.get("pages"), "| page:", info.get("page"),
      "| rows here:", len(info.get("rows") or []))
for r in (info.get("rows") or [])[:2]:
    print("  |".join(str(x)[:24] for x in r[:8]))
try:
    send("Page.close")
    ws.close()
except Exception:
    pass