import ssl, urllib3, json, sys, time, urllib.request, websocket
urllib3.disable_warnings(); ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read())
t=[x for x in tabs if x.get("type")=="page"]
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
    return v.get("value","") if "value" in v else str(v)[:400]
F='pt1:cBodFDC:r1:0:masteraTable:Fromdate::content'
def hf(): return js("!!document.getElementById('"+F+"')")=="true"
# top-level LIs of iq-sidebar-toggle
out=js("""(function(){
  var ul=document.getElementById('iq-sidebar-toggle');
  var o=[];
  if(ul) ul.querySelectorAll(':scope > li').forEach(function(li){
    var d=li.querySelector('a,span,div');
    o.push({cls:(li.className||'').slice(0,30), t:((d?d.innerText:'')||'').replace(/\\s+/g,' ').trim().slice(0,30), vis:li.offsetParent!==null, w:li.getBoundingClientRect().width, hasSub:!!li.querySelector('ul')});
  });
  return JSON.stringify(o);
})()""")
print("TOP LIs:", out)
ws.close()
