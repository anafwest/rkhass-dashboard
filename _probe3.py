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
def js(e,ap=False):
    r=send("Runtime.evaluate",{"expression":e,"returnByValue":True,"awaitPromise":ap})
    v=r.get("result",{})
    return v.get("value","") if "value" in v else str(v)[:300]
# find the pagination bar container and dump its structure
out = js("""(function(){
  var root=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_cnt');
  var p=root; for(var i=0;i<6&&p;i++) p=p.parentElement;
  var bar=p||document.body;
  var ids=[];
  bar.querySelectorAll('[id]').forEach(function(e){
    var id=e.id||'';
    if(id.indexOf('nb_')>=0) ids.push({id:id,tag:e.tagName,cls:(e.className||'').slice(0,50),
      ipt: e.tagName==='INPUT'? e.value : undefined,
      vis: e.offsetParent!==null});
  });
  var rng=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_rng');
  var txt=rng? rng.innerText.replace(/\\s+/g,' ').trim() : 'n/a';
  return JSON.stringify({ids:ids, rng:txt, barHTML:(bar.outerHTML||'').slice(0,3000)});
})()""")
d=json.loads(out)
print("RNG:", d["rng"])
for x in d["ids"]: print(x)
print("---- BAR ----")
print(d["barHTML"])
ws.close()
