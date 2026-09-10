import ssl, urllib3, json, sys, time, urllib.request, websocket
urllib3.disable_warnings(); ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read())
t=[x for x in tabs if x.get("type")=="page" and "BLS" in x.get("url","")]
print("num bls tabs:", len(t)); [print(" -", x.get("url","")[:70], x["id"][:8]) for x in t]
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
    return v.get("value","") if "value" in v else str(v)[:300]
F='pt1:cBodFDC:r1:0:masteraTable:Fromdate::content'
def hf(): return "TRUE" if js("!!document.getElementById('"+F+"')")=="true" else "false"
print("step0 has_form:", hf())
for cid in ("pt1:j_idt19","pt1:SearchLi8500","pt1:SearchLi8510"):
    r=js("(function(){var e=document.getElementById('"+cid+"');if(e){e.click();return 'ok';}return 'missing';})()")
    print("click", cid, "->", r)
    for k in range(20):
        time.sleep(1.0)
        s=hf()
        if s=="TRUE":
            print("  form TRUE after", k+1, "s"); break
    else:
        print("  form still false after 20s")
ws.close()
