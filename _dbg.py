import ssl, urllib3, json, sys, time, urllib.request, websocket
urllib3.disable_warnings(); ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read())
print("tabs:", [(x.get("id","")[:6], x.get("url","")[:60]) for x in tabs if x.get("type")=="page"])
t=[x for x in tabs if x.get("type")=="page" and "BLS" in x.get("url","")]
ws=websocket.create_connection(t[0]["webSocketDebuggerUrl"],timeout=45); _id=[0]
def send(m,p=None):
    _id[0]+=1; d={"id":_id[0],"method":m}
    if p: d["params"]=p
    ws.send(json.dumps(d))
    while True:
        r=json.loads(ws.recv())
        if r.get("id")==_id[0]: return r.get("result",{})
def js(e):
    r=send("Runtime.evaluate",{"expression":e,"returnByValue":True})
    v=r.get("result",{})
    return v.get("value","") if "value" in v else str(v)[:400]
print("URL:", js("document.location.href")[:120])
print("hasForm:", js("!!document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content')"))
print("myInput:", js("!!document.getElementById('myInput')"))
print("j_idt19:", js("(function(){var e=document.getElementById('pt1:j_idt19');return e? (e.offsetParent!==null?'visible':'hidden'):'missing';})()"))
print("SearchLi8510:", js("(function(){var e=document.getElementById('pt1:SearchLi8510');return e? (e.offsetParent!==null?'visible':'hidden'):'missing';})()"))
o=js("(function(){var t=(document.body.innerText||'').replace(/\\s+/g,' ').trim();return t.slice(0,600);})()")
print("BODY:", o)
ws.close()
