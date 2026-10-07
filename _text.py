# -*- coding: utf-8 -*-
import json, sys, urllib.request, websocket

sys.stdout.reconfigure(encoding="utf-8")
tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=8).read())
t = next((x for x in tabs if x.get("type") == "page" and "adfs" in x.get("url", "")), None)
if not t:
    print("NO ADFS TAB")
    raise SystemExit(1)
ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=20)
ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                    "params": {"expression": "JSON.stringify({url:location.href, txt:document.body.innerText.slice(0,600), user:!!document.getElementById('userNameInput'), pwd:!!document.getElementById('passwordInput'), otp:!!document.getElementById('otpInput'), submit:!!document.getElementById('submitButton')})",
                               "returnByValue": True}}))
while True:
    r = json.loads(ws.recv())
    if r.get("id") == 1:
        v = r["result"]["result"].get("value", "{}")
        break
ws.close()
d = json.loads(v)
print("URL :", d["url"][:120])
print("user:", d["user"], "| pwd:", d["pwd"], "| otp:", d["otp"], "| submit:", d["submit"])
print("TEXT:")
print(d["txt"])