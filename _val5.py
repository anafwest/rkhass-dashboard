import ssl, urllib3, json, sys, time, urllib.request, websocket
urllib3.disable_warnings(); ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read())
t=[x for x in tabs if x.get("type")=="page"]
ws=websocket.create_connection(t[0]["webSocketDebuggerUrl"],timeout=60); _id=[0]
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
def val(f):
    return js("(function(){var e=document.getElementById('"+f+"');return e?e.value:'nf';})()")
F='pt1:cBodFDC:r1:0:masteraTable:Fromdate::content'
T='pt1:cBodFDC:r1:0:masteraTable:Todate::content'
print("F:",val(F),"| T:",val(T))
def type_into(fid, text):
    js("(function(){var e=document.getElementById('"+fid+"');if(!e)return;e.focus();if(e.select)e.select();return;})()")
    time.sleep(0.2)
    # clear via Ctrl+A + Backspace using JS selection (simpler)
    js("(function(){var e=document.getElementById('"+fid+"');e.focus();e.select();document.execCommand('selectAll',false,null);return;})()")
    send("Input.dispatchKeyEvent", {"type":"keyDown","modifiers":2,"key":"a","code":"KeyA","windowsVirtualKeyCode":65})
    send("Input.dispatchKeyEvent", {"type":"keyUp","modifiers":2,"key":"a","code":"KeyA","windowsVirtualKeyCode":65})
    send("Input.insertText", {"text":text})
    time.sleep(0.2)
    js("(function(){var e=document.getElementById('"+fid+"');e.dispatchEvent(new Event('change',{bubbles:true}));e.blur();return;})()")
    time.sleep(0.5)
    return val(fid)
print("try F:", type_into(F,"1447/04/13"))
print("try T:", type_into(T,"1448/12/29"))
ws.close()
