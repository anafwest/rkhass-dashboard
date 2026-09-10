import ssl, urllib3, json, sys, time, urllib.request, websocket
urllib3.disable_warnings(); ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read())
ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t.get("type")=="page" and "BLS" in t.get("url",""))
ws = websocket.create_connection(ws_url, timeout=30)
_id=[0]
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

print("Fromdate val before:", js("var e=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content'); e?e.value:'nf'"))
print("Todate val before:", js("var e=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Todate::content'); e?e.value:'nf'"))

# focus Fromdate
js("(function(){var e=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content');e.focus();e.select();return e.value;})()")
time.sleep(0.3)
# select all with Ctrl+A
send("Input.dispatchKeyEvent", {"type":"keyDown","modifiers":2,"key":"a","code":"KeyA","windowsVirtualKeyCode":65})
send("Input.dispatchKeyEvent", {"type":"keyUp","modifiers":2,"key":"a","code":"KeyA","windowsVirtualKeyCode":65})
time.sleep(0.2)
send("Input.insertText", {"text":"1447/04/13"})
time.sleep(0.3)
js("(function(){var e=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content');e.dispatchEvent(new Event('change',{bubbles:true}));e.blur();return 'ok';})()")
time.sleep(1.5)
print("Fromdate val after:", js("var e=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content'); e?e.value:'nf'"))
ws.close()
