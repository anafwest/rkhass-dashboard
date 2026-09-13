# -*- coding: utf-8 -*-
import sys, json, urllib.request, urllib.parse, time
sys.stdout.reconfigure(encoding='utf-8')
import websocket
def test(size):
    url=f"https://ups-backoffice.alriyadh.gov.sa/ar/building-license-department?activeTab=requests&page=1&size={size}"
    req=urllib.request.Request("http://127.0.0.1:9222/json/new?"+urllib.parse.quote(url,safe=""),method="PUT")
    nb=json.loads(urllib.request.urlopen(req,timeout=10).read())
    ws=websocket.create_connection(nb["webSocketDebuggerUrl"],timeout=30)
    ID=[0]
    def send(m,p=None):
        ID[0]+=1; ws.send(json.dumps({"id":ID[0],"method":m,"params":p or {}}))
        while True:
            r=json.loads(ws.recv())
            if r.get("id")==ID[0]: return r.get("result",{})
    js=lambda e: send("Runtime.evaluate",{"expression":e,"returnByValue":True}).get("result",{}).get("value","")
    send("Page.navigate",{"url":url})
    time.sleep(6)
    pi=js("(document.body.innerText.match(/الصفحة\\s*(\\d+)\\s*من\\s*(\\d+)/)||['','0','0']).slice(1).join('/')")
    nrows=js("document.querySelectorAll('table tbody tr').length")
    print(f"size={size}: pageinfo={pi} rows={nrows}")
    send("Page.close"); ws.close()
for s in (50,100):
    try: test(s)
    except Exception as e: print("err",s,e)
