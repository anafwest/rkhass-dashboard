# -*- coding: utf-8 -*-
import sys, json, urllib.request, urllib.parse, websocket, time, ssl, urllib3
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding="utf-8")
PORT = 9222
req = urllib.request.Request("http://127.0.0.1:%d/json/new?%s" % (PORT, urllib.parse.quote("https://app.alriyadh.gov.sa/BLS/loginApi", safe="")), method="PUT")
nb = json.loads(urllib.request.urlopen(req, timeout=10).read())
ws = websocket.create_connection(nb["webSocketDebuggerUrl"], timeout=60)
_i = [0]
def send(m, p=None):
    _i[0]+=1
    ws.send(json.dumps({"id":_i[0],"method":m,"params":p or {}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id")==_i[0]: return r.get("result",{})
def js(expr):
    r = send("Runtime.evaluate",{"expression":expr,"returnByValue":True})
    v = r.get("result",{})
    return v.get("value","ERR via %s"%v.get("description",""))
for i in range(14):
    time.sleep(5)
    url = js("document.location.href") or ""
    adf = js('typeof AdfPage!=="undefined"?"ok":"wait"')
    myinput = js("!!document.getElementById('myInput')")
    print(i, url[:110], adf, myinput, flush=True)
    if adf=="ok" and myinput: break
