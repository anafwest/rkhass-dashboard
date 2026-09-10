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
        if r.get("id")==_id[0]: return r.get("result",{"_id":_id[0]})
def js(e):
    r=send("Runtime.evaluate",{"expression":e,"returnByValue":True})
    v=r.get("result",{})
    return v.get("value","") if "value" in v else str(v)[:300]
def rng():
    return js("(function(){var r=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_rng');return r?r.innerText.replace(/\\s+/g,' ').trim():'nf';})()")
def jump(pg):
    js("(function(){var e=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_in_pg');e.focus();e.value='"+str(pg)+"';var ev=new KeyboardEvent('keydown',{bubbles:true,cancelable:true,keyCode:13,key:'Enter'});e.dispatchEvent(ev);return 'ok';})()")
print("before jump:", rng())
t0=time.time(); jump(200)
while time.time()-t0 < 12:
    time.sleep(0.3)
    s=rng()
    if s not in ('nf',) and ('200' in s):
        break
print("after jump (%.2fs):" % (time.time()-t0), rng())
# now time a next-page click
t0=time.time()
js("(function(){var a=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_nx'); if(a)a.click(); return 'ok';})()")
st=rng().split('من')[0].strip().strip('(')
# poll start change
while time.time()-t0 < 10:
    time.sleep(0.25)
    s=rng()
    if s and s.split('من')[0].strip().strip('(')!=st:
        break
print("after next (%.2fs):" % (time.time()-t0), rng())
ws.close()
