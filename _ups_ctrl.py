# -*- coding: utf-8 -*-
import sys, json, urllib.request, time
sys.stdout.reconfigure(encoding='utf-8')
import websocket
tabs=json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json",timeout=5).read())
t=[t for t in tabs if "ups-backoffice" in t.get("url","")]
print("ups tabs:", len(t))
if not t: sys.exit(0)
ws=websocket.create_connection(t[0]["webSocketDebuggerUrl"],timeout=30)
ID=[0]
def send(m,p=None):
    ID[0]+=1; ws.send(json.dumps({"id":ID[0],"method":m,"params":p or {}}))
    while True:
        r=json.loads(ws.recv())
        if r.get("id")==ID[0]: return r.get("result",{})
js=lambda e: send("Runtime.evaluate",{"expression":e,"returnByValue":True}).get("result",{}).get("value","")
# search for input/date/select controls in the requests view
ctrls=js("(function(){var o=[];document.querySelectorAll('input,select,button').forEach(function(e){var t=(e.tagName+'|'+(e.type||'')+'|'+(e.name||'')+'|'+(e.id||'')+'|'+(e.placeholder||'')+'|'+(e.getAttribute('aria-label')||'')).trim().slice(0,80);o.push(t);});return JSON.stringify([...new Set(o)].slice(0,80));})()")
print("CONTROLS:", ctrls[:2000])
# check for a search/filter UI text
txt=js("document.body.innerText.match(/(بحث|فلتر|ترشيح|حالة الطلب|من تاريخ|إلى تاريخ|رقم الطلب|رخصة)/g)||[]")
print("filter-words found:", txt)
ws.close()
