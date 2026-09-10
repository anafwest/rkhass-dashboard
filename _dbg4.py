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
    return v.get("value","") if "value" in v else str(v)[:600]
out=js("""(function(){
  var e=document.getElementById('pt1:SearchLi8510');
  if(!e) return JSON.stringify({err:'missing'});
  var chain=[]; var n=e;
  for(var i=0;i<8&&n;i++){
    var cs=(n.className||''); var t=(n.innerText||'').replace(/\\s+/g,' ').trim().slice(0,30);
    chain.push({tag:n.tagName, id:(n.id||'').slice(0,40), cls:cs.slice(0,60), style:(n.getAttribute('style')||'').slice(0,60), vis:n.offsetParent!==null, w:n.getBoundingClientRect().width});
    n=n.parentElement;
  }
  // toggles / buttons visible
  var btns=[];
  document.querySelectorAll('button,a[class*=sidebar-toggler],a[href="#"][class*=toggle],.iq-navbar-toggler,.sidebar-toggle').forEach(function(b){
    var g=b.getBoundingClientRect();
    if(g.width>0&&g.height>0) btns.push({tag:b.tagName,id:(b.id||''),cls:(b.className||'').slice(0,50),t:(b.innerText||b.title||'').trim().slice(0,20)});
  });
  return JSON.stringify({chain:chain, btns:btns.slice(0,10)});
})()""")
import json as J
d=J.loads(out)
print("CHAIN:")
for c in d["chain"]: print("  ", c)
print("VISIBLE TOGGLES:", len(d.get("btns",[])))
for b in d.get("btns",[]): print("  ", b)
ws.close()
