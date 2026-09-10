import ssl, urllib3, json, sys, time, urllib.request, websocket, os, glob
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
def js(e,ap=False):
    r=send("Runtime.evaluate",{"expression":e,"returnByValue":True,"awaitPromise":ap})
    v=r.get("result",{})
    return v.get("value","") if "value" in v else str(v)[:400]

DL = os.path.expandvars(r"%USERPROFILE%\Downloads")
before = set(os.listdir(DL)) if os.path.isdir(DL) else set()
print("Downloads:", DL, "exists:", os.path.isdir(DL))

def set_field(fid, value):
    for attempt in range(3):
        r = js("(function(){var el=document.getElementById('"+fid+"');if(!el)return 'nf';"
               "el.focus();el.removeAttribute('readonly');"
               "var proto=Object.getPrototypeOf(el);"
               "var setter=Object.getOwnPropertyDescriptor(proto,'value');"
               "if(setter&&setter.set)setter.set.call(el,'"+value+"');else el.value='"+value+"';"
               "el.dispatchEvent(new Event('input',{bubbles:true}));"
               "el.dispatchEvent(new Event('change',{bubbles:true}));"
               "el.blur();return JSON.stringify({val:el.value});})()")
        if not r or r == 'nf': return False, r
        time.sleep(0.6)
        got = js("var el=document.getElementById('"+fid+"'); el?el.value:''")
        if got == value: return True, got
    return False, ''

f = set_field('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content', '1448/09/01')
t = set_field('pt1:cBodFDC:r1:0:masteraTable:Todate::content', '1448/12/29')
print("set dates:", f[0], t[0], "| vals:", f[1], t[1])
time.sleep(1)
js("(function(){var b=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:search'); if(b)b.click(); return 'ok';})()")
total = 0
for i in range(15):
    time.sleep(3)
    info = json.loads(js(js if False else "(function(){var t=document.querySelector('table.af_table_data-table');if(!t)return JSON.stringify({rows:0,total:0});var rows=t.tBodies&&t.tBodies[0]?t.tBodies[0].rows.length:0;var r=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_rng');return JSON.stringify({rows:rows,total:(r?r.innerText:'')});})()"))
    total = info.get('total','')
    print("after search:", i, info)
    if info.get('total') != '' and '0' != (info.get('total') or '?'):
        break
print("--- clicking export ---")
r = js("(function(){var b=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:b11');if(!b)return {err:'nf'};b.click();return {ok:1};})()")
print("click:", r)
for i in range(12):
    time.sleep(2)
    now = set(os.listdir(DL)) if os.path.isdir(DL) else set()
    new = now - before
    if new:
        print("NEW FILES:", new)
        for n in new:
            p = os.path.join(DL, n)
            print("  ", n, os.path.getsize(p)//1024, "KB", time.strftime('%H:%M:%S', time.localtime(os.path.getmtime(p))))
        break
else:
    print("no new file after 24s", "current:", set(os.listdir(DL)) - (before & set(os.listdir(DL))))
ws.close()
