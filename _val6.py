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
def rng_txt():
    return js("(function(){var r=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_rng');return r?r.innerText.replace(/\\s+/g,' ').trim():'nf';})()")
def start_num(s):
    try: return int(s.split('-')[0].strip().strip('('))
    except: return -1
js("(function(){var b=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:search');if(b)b.click();return 'ok';})()")
t0=time.time(); s=''
for i in range(40):
    time.sleep(0.5)
    s=rng_txt(); st=start_num(s)
    if st>0 and '1249' in s: break
    if i%6==0: print("  wait", i, s)
print("search: %.1fs -> %s"%(time.time()-t0, rng_txt()))
# next-page timing over 8 pages
st=start_num(s); lat=[]
for k in range(8):
    js("(function(){var a=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_nx');if(a)a.click();return 'ok';})()")
    t0=time.time(); cur=st+k*5
    while start_num(rng_txt())<=cur and time.time()-t0<8:
        time.sleep(0.2)
    lat.append(time.time()-t0)
print("next latency avg %.2fs: %s"%(sum(lat)/len(lat), rng_txt()))
# jump to 400
js("(function(){var e=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_in_pg');e.focus();e.value='400';var ev=new KeyboardEvent('keydown',{bubbles:true,cancelable:true,keyCode:13,key:'Enter'});e.dispatchEvent(ev);return 'ok';})()")
t0=time.time(); cur=start_num(rng_txt())
while start_num(rng_txt())==cur and time.time()-t0<12:
    time.sleep(0.3)
print("jump 400: %.2fs -> %s"%(time.time()-t0, rng_txt()))
ws.close()
