import ssl, urllib3, json, sys, time, urllib.request, websocket, urllib.parse as up
urllib3.disable_warnings(); ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
req = urllib.request.Request("http://127.0.0.1:9222/json/new?"+up.quote("about:blank",safe=''), method="PUT")
nb = json.loads(urllib.request.urlopen(req, timeout=8).read())
ws=websocket.create_connection(nb["webSocketDebuggerUrl"],timeout=60); _id=[0]
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
    return v.get("value","") if "value" in v else str(v)[:300]
F='pt1:cBodFDC:r1:0:masteraTable:Fromdate::content'
def hf(): return "TRUE" if js("!!document.getElementById('"+F+"')")=="true" else "false"
print("blank tab state:", hf())
js("window.location.href='https://app.alriyadh.gov.sa/BLS/faces/home'")
t0=time.time()
while time.time()-t0<40:
    time.sleep(2)
    r=hf()
    if r=="TRUE":
        print("form TRUE after %.1fs"%(time.time()-t0)); break
else:
    print("form never true")
print("url:", js("document.location.href")[:90])
ws.close()
