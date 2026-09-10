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
# DA attributes of ancestors + globals
info=js("""(function(){
  var a=document.getElementById('pt1:SearchLi8510');
  if(!a) return 'miss';
  var chain=[];
  var n=a;
  for(var i=0;i<9&&n;i++){
    var o={tag:n.tagName, id:(n.id||'').slice(0,40), cls:(typeof n.className==='string'?n.className:'').slice(0,60)};
    var da={};
    for(var j=0;j<n.attributes.length;j++){var at=n.attributes[j].name; if(at.indexOf('data-')===0) da[at]=n.attributes[j].value.slice(0,60);}
    o.da=da;
    chain.push(o);
    n=n.parentElement;
  }
  return chain;
})()""")
print("CHAIN:", json.dumps(info, ensure_ascii=False)[:2500])
glob=js("""(function(){
  return {
    _adf: typeof _adf, Adf: typeof Adf, adf: typeof adf, AF: typeof AF,
    AdfWndId: (typeof AdfWndId!=='undefined'? AdfWndId : (window.AdfWindowId? AdfWindowId:'n/a')),
    wins: ['_adf','AdfRich','AFMetaEntities'].filter(function(k){return typeof window[k]!=='undefined';})
  };
})()""")
print("GLOB:", json.dumps(glob))
ws.close()
