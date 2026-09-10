import ssl, urllib3, json, sys, time, urllib.request, websocket
urllib3.disable_warnings(); ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
def pages():
    return json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read())
t=[x for x in pages() if x.get("type")=="page"]
ws=websocket.create_connection(t[0]["webSocketDebuggerUrl"],timeout=60); _id=[0]
def send(m, par=None):
    _id[0]+=1; d={"id":_id[0],"method":m}
    if par: d["params"]=par
    ws.send(json.dumps(d))
    while True:
        r=json.loads(ws.recv())
        if r.get("id")==_id[0]: return r.get("result",{})
def js(e):
    r=send("Runtime.evaluate",{"expression":e,"returnByValue":True})
    v=r.get("result",{})
    return v.get("value") if "value" in v else None
def hf():
    v=js("!!document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content')")
    return bool(v)
print("form exists NOW:", hf())
state=js(r"""(function(){
  var h=[];
  document.querySelectorAll('h1,h2,h3,h4,h5,h6,.iq-page-title,.card-title,.af_panelBox_title,legend').forEach(function(e){
    var tx=(e.innerText||'').replace(/\\s+/g,' ').trim();
    if(tx) h.push(tx.slice(0,60));
  });
  return {headings:h.slice(0,15)};
})()""")
print("screen info:", json.dumps(state, ensure_ascii=False)[:1000])
ws.close()
