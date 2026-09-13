# -*- coding: utf-8 -*-
import sys, json, urllib.request, time
sys.stdout.reconfigure(encoding='utf-8')
import websocket
tabs=json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json",timeout=5).read())
t=[t for t in tabs if "ups-backoffice" in t.get("url","")]
ws=websocket.create_connection(t[0]["webSocketDebuggerUrl"],timeout=30)
ID=[0]
def send(m,p=None):
    ID[0]+=1; ws.send(json.dumps({"id":ID[0],"method":m,"params":p or {}}))
    while True:
        r=json.loads(ws.recv())
        if r.get("id")==ID[0]: return r.get("result",{})
js=lambda e: send("Runtime.evaluate",{"expression":e,"returnByValue":True}).get("result",{}).get("value","")
# inspect createdOn input container
s=js("(function(){var e=document.querySelector('input[name=createdOn]');if(!e)return 'none';var p=e.parentElement;var html=p? (p.outerHTML||'').slice(0,600):'';return JSON.stringify({val:e.value,ro:e.readOnly,ph:e.placeholder,cls:e.className.slice(0,80),outer:html});})()")
print("createdOn:", s[:900])
# list buttons near the form (text+class)
b=js("(function(){var o=[];document.querySelectorAll('button').forEach(function(e){var t=(e.innerText||'').trim()||'ICON';if(o.length<25)o.push(t+' @ '+(e.className||'').slice(0,40));});return JSON.stringify(o);})()")
print("buttons:", b[:1500])
# any datepicker component classes?
d=js("(function(){var o=[];document.querySelectorAll('[class*=picker],[class*=calendar],[class*=date]').forEach(function(e){o.push((e.tagName)+':'+(e.className||'').slice(0,60));});return JSON.stringify([...new Set(o)].slice(0,30));})()")
print("picker-cls:", d[:1200])
ws.close()
