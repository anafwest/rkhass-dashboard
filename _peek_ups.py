# -*- coding: utf-8 -*-
import json, urllib.request, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Users\anaf\OneDrive - Riyadh Municipality\المستندات\Default Project\rkhass-dashboard")
import ups_sync_fast as U

tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=8).read())
ups = [t for t in tabs if t.get("type") == "page" and "ups-backoffice" in t.get("url", "")]
pages = []
for t in ups:
    try:
        ws, send = U.connect_ws(t["webSocketDebuggerUrl"])
        info = U.read_rows(send)
        pages.append(info.get("page"))
        try:
            ws.close()
        except Exception:
            pass
    except Exception:
        pages.append(None)
pages = [p for p in pages if p]
print("current pages:", sorted(pages))
if pages:
    print("max page reached:", max(pages), "of 3567 →", round(max(pages) / 3567 * 100, 1), "%")