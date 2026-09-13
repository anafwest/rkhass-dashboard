# -*- coding: utf-8 -*-
import sys, json, urllib.request, urllib.parse, time
sys.stdout.reconfigure(encoding='utf-8')
import websocket
url="https://ups-backoffice.alriyadh.gov.sa/ar/building-license-department?activeTab=requests&page=2"
req=urllib.request.Request("http://127.0.0.1:9222/json/new?"+urllib.parse.quote(url,safe=""),method="PUT")
nb=json.loads(urllib.request.urlopen(req,timeout=10).read())
ws=websocket.create_connection(nb["webSocketDebuggerUrl"],timeout=30)
ID=[0]
def send(m,p=None):
    ID[0]+=1; ws.send(json.dumps({"id":ID[0],"method":m,"params":p or {}}))
    while True:
        r=json.loads(ws.recv())
        if r.get("id")==ID[0]: return r.get("result",{})
send("Network.enable")
send("Page.enable")
send("Page.navigate",{"url":url})
seen=[]
t0=time.time(); ws.settimeout(3)
while time.time()-t0<12:
    try: r=json.loads(ws.recv())
    except Exception: continue
    if r.get("method")=="Network.requestWillBeSent":
        u=r["params"]["request"]["url"]
        if u.startswith("http") and u not in seen: seen.append(u)
print("ALL HTTP URLs:")
for u in seen: print(" -", u[:180])
send("Page.close")
ws.close()
