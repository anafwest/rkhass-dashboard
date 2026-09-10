import ssl, urllib3, json, sys, time, urllib.request, websocket
urllib3.disable_warnings(); ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
def tabs():
    return json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read())
def connect_ws(url):
    ws=websocket.create_connection(url,timeout=60); _id=[0]
    def send(m,p=None):
        _id[0]+=1; d={"id":_id[0],"method":m}
        if p: d["params"]=p
        ws.send(json.dumps(d))
        while True:
            r=json.loads(ws.recv())
            if r.get("id")==_id[0]: return r.get("result",{})
    return ws,send
def js(send,e):
    r=send("Runtime.evaluate",{"expression":e,"returnByValue":True})
    v=r.get("result",{})
    return v.get("value","") if "value" in v else str(v)[:300]

# wait for BLS home
for i in range(20):
    t=[x for x in tabs() if x.get("type")=="page"]
    if t: break
    time.sleep(2)
url=None; ws=None; send=None
for i in range(25):
    for x in tabs():
        u=x.get("url","")
        if x.get("type")=="page" and "BLS" in u and "login" not in u.lower():
            ws,send=connect_ws(x["webSocketDebuggerUrl"]); url=js(send,"document.location.href"); break
    if url and "BLS" in str(url): break
    time.sleep(3)
print("tab url:", url)
time.sleep(5)
# wait ADF
for i in range(10):
    if js(send,'typeof AdfPage!=="undefined"?"ok":"wait"')=="ok": break
    time.sleep(2)
# is 8510 already?
has=js(send,"!!document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content')")
print("has search form:", has)
# nav by IDs
def cid(cid):
    return js(send,"(function(){var e=document.getElementById('"+cid+"');if(!e)return 'nf';e.click();return 'ok';})()")
def poll_has(t=12):
    t0=time.time()
    while time.time()-t0<t:
        if js(send,"!!document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content')")=="true": return True
        time.sleep(0.5)
    return False
if has=="true":
    print("8510 already open")
else:
    t0=time.time(); r=cid("pt1:j_idt19"); print("click 8000:",r,"%.1fs"%(time.time()-t0))
    time.sleep(2)
    t0=time.time(); r=cid("pt1:SearchLi8510"); print("click 8510:",r,"%.1fs"%(time.time()-t0))
    print("form after nav:", poll_has(12))
# search
js(send,"(function(){var b=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:search');if(b)b.click();return 'ok';})()")
total=-1; t0=time.time()
for i in range(20):
    time.sleep(0.5)
    s=js(send,"(function(){var r=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_rng');return r?r.innerText.replace(/\\s+/g,' ').trim():'nf';})()")
    if s!='nf':
        try: total=int(s.split('من')[1].replace('من','').replace(',','').split()[0])
        except: pass
    if total>0: break
print("search -> total=%s in %.1fs (%s)"%(total,time.time()-t0,s))
ws.close()
