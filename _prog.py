# -*- coding: utf-8 -*-
import json, re, sys, urllib.request, websocket
sys.stdout.reconfigure(encoding="utf-8")
tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=8).read())
pages = [t for t in tabs if t.get("type") == "page" and "ups-backoffice" in t.get("url", "")]
print("ups tabs:", len(pages))
seen = []
for t in pages:
    try:
        ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=10)
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                            "params": {"expression": "document.body.innerText", "returnByValue": True}}))
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == 1:
                txt = r["result"]["result"].get("value", "") or ""
                break
        ws.close()
        m = re.search(r"الصفحة\s*(\d+)\s*من\s*(\d+)", txt)
        seen.append((int(m.group(1)), int(m.group(2))) if m else (None, None))
    except Exception as e:
        seen.append(("err", str(e)[:30]))
for s in seen:
    print("  page:", s)