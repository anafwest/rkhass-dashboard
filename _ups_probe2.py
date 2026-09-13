# -*- coding: utf-8 -*-
import sys, json, urllib.request, time
sys.stdout.reconfigure(encoding='utf-8')
import websocket
tabs=json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json",timeout=5).read())
t=[t for t in tabs if "ups-backoffice" in t.get("url","")]
if not t: print("NO TAB"); sys.exit(0)
ws=websocket.create_connection(t[0]["webSocketDebuggerUrl"],timeout=30)
ID=[0]
def send(m,p=None):
    ID[0]+=1; msg={"id":ID[0],"method":m}
    if p: msg["params"]=p
    ws.send(json.dumps(msg))
    while True:
        r=json.loads(ws.recv())
        if r.get("id")==ID[0]: return r.get("result",{})
js=lambda e: send("Runtime.evaluate",{"expression":e,"returnByValue":True}).get("result",{}).get("value","")
# page size selector?
print("selects:", js("(function(){var o=[];document.querySelectorAll('select').forEach(function(e){o.push('sel:'+(e.id||'')+' opts='+Array.from(e.options).map(function(x){return x.text+'='+x.value}).join('|'));});return JSON.stringify(o);})()")[:600])
print("perPage text:", js("document.body.innerText.match(/صفحة|إظهار|عرض/g)||''")) 
ws.close()
