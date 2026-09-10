# -*- coding: utf-8 -*-
"""probe7: قياس سرعة قراءة الصفحات (تبويب واحد) — صفحة/ثانية."""
import ssl, os, urllib3, time, sys
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
import scraper as S

ws, send = None, None
tabs = S.get_tabs()
for t in tabs:
    u = t.get("url","")
    if t.get("type")=="page" and "BLS/faces" in u:
        ws, send = S.connect_ws(t["webSocketDebuggerUrl"]); break
if not send:
    print("لا تبويب BLS"); sys.exit(1)

if not S.has_form(send):
    if not S.ensure_8510(send):
        print("لا شاشة 8510"); sys.exit(1)
    S.ensure_dates(send)
    S.click_search(send)
S.ensure_dates(send)
info = S.read_info(send)
total = info["total"]; pp = info.get("perPage",5) or 5
print("total:", total, "pp:", pp, "pages:", (total+pp-1)//pp)

N = 40
t0 = time.time()
cur = 1
for i in range(N):
    info = S.read_info(send)
    if i < N-1:
        S.click_next(send)
        S.wait_advance(send, cur*pp, timeout=8)
        cur += 1
el = time.time()-t0
print(f"{N} صفحات في {el:.1f} ث = {N/el:.2f} صفحة/ث | كل الصفحات ~{ ( (total+pp-1)//pp ) / (N/el) /60:.1f} دقيقة")
ws.close()