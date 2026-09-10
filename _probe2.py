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
    return v.get("value","") if "value" in v else str(v)[:400]
out = js("""(function(){
  var o={};
  var ws3=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:smc3::pop');
  o.smc3 = ws3? ws3.innerText.replace(/\\s+/g,' ').trim() : 'n/a';
  var w1=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:smc1::pop');
  o.smc1 = w1? w1.innerText.replace(/\\s+/g,' ').trim() : 'n/a';
  var inp=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:smc3::content');
  o.smc3input = inp? inp.value : 'n/a';
  var nx=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_nx');
  var pg=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_pg_1');
  o.nx= nx? nx.textContent.trim() : 'n/a';
  var pag = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_cnt');
  o.cnt= pag? pag.innerText.replace(/\\s+/g,' ').trim() : 'n/a';
  var all=[], qs=document.querySelectorAll('a[href*="void"],a.af_commandButton,button');
  qs.forEach(function(a){var t=(a.textContent||'').trim();if(t&&t.length<40) all.push(t);});
  o.buttons=all.slice(0,40);
  return JSON.stringify(o);
})()""")
print(out[:3000])
ws.close()
