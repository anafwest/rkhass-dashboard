# -*- coding: utf-8 -*-
import base64, json, sys, urllib.request, websocket

tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=8).read())
t = next((x for x in tabs if x.get("type") == "page" and "adfs" in x.get("url", "")), None)
if not t:
    print("NO ADFS TAB")
    raise SystemExit(1)
ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=20)
ws.send(json.dumps({"id": 1, "method": "Page.captureScreenshot", "params": {"format": "png"}}))
while True:
    r = json.loads(ws.recv())
    if r.get("id") == 1:
        data = r["result"]["data"]
        break
ws.close()
open(r"C:\Users\anaf\AppData\Local\Temp\opencode\adfs.png", "wb").write(base64.b64decode(data))
print("saved adfs.png")
