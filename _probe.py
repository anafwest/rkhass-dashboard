import ssl, urllib3, json, sys, time, urllib.request, websocket
urllib3.disable_warnings(); ssl._create_default_https_context = ssl._create_unverified_context
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
out = js("""(function(){
  var ids=[];
  document.querySelectorAll('[id]').forEach(function(e){var id=e.id||'';
    if(id.indexOf('nb_')>=0 || id.indexOf('masteraTable')>=0){
      var o={id:id,tag:e.tagName};
      if(e.id.indexOf('nb_pg')>=0||e.id.indexOf('nb_nx')>=0||e.id.indexOf('nb_in_pg')>=0) o.html=e.outerHTML.slice(0,180);
      ids.push(o);
    }});
  var sel=[];
  document.querySelectorAll('select').forEach(function(s){sel.push({id:s.id,opts:s.options.length,v:s.value});});
  return JSON.stringify({ids:ids, select:sel});
})()""")
print(out[:4000])
print("RNG:", js("var r=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_rng'); r?r.innerText:'-1'"))
ws.close()
