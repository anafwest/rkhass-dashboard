# -*- coding: utf-8 -*-
import sys, json, urllib.request, time
sys.stdout.reconfigure(encoding='utf-8')
import websocket
tabs=json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json",timeout=5).read())
t=[t for t in tabs if "ups-backoffice" in t.get("url","")]
print("ups tab count:", len(t))
if not t:
    print("NO UPS TAB"); sys.exit(0)
ws=websocket.create_connection(t[0]["webSocketDebuggerUrl"],timeout=30)
ID=[0]
def send(m,p=None):
    ID[0]+=1; msg={"id":ID[0],"method":m}
    if p: msg["params"]=p
    ws.send(json.dumps(msg))
    while True:
        r=json.loads(ws.recv())
        if r.get("id")==ID[0]: return r.get("result",{})
r=send("Runtime.evaluate",{"expression":"document.location.href","returnByValue":True})
print("url:", r.get("result",{}).get("value","")[:100])
r=send("Runtime.evaluate",{"expression":"(document.body.innerText.match(/الصفحة\\s*(\\d+)\\s*من\\s*(\\d+)/)||['','0','0']).slice(1).join('/')","returnByValue":True})
print("pageinfo:", r.get("result",{}).get("value",""))
ws.close()
