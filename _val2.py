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
out=js("""(function(){
  var o={};
  var ids=['pt1:j_idt19','pt1:SearchLi8500','pt1:SearchLi8510'];
  o.items=[];
  ids.forEach(function(id){
    var e=document.getElementById(id); 
    o.items.push({id:id, exists:!!e, vis: e? (e.offsetParent!==null):false, rect:e?(function(){var g=e.getBoundingClientRect();return g.width+'x'+g.height} )():'nf'});
  });
  o.hasGlobalSearch=!!document.querySelector('input[type=text][class*=search]');
  document.querySelectorAll('input[type=text]').forEach(function(i){ if(i.offsetParent!==null) o.inputs=o.inputs||[]; if((o.inputs||[]).length<8) (o.inputs=o.inputs||[]).push({id:i.id,ph:i.placeholder});});
  var sidebar=document.getElementById('pt1:SideBarMainMenus');
  o.sidebar= sidebar? (sidebar.className||'')+' | vis='+(sidebar.offsetParent!==null) : 'nf';
  // inner text around BLS8000
  o.text8000= (function(){
    var a=document.getElementById('pt1:j_idt19'); return a? a.innerText.replace(/\\s+/g,' ').trim().slice(0,60):'nf';
  })();
  // search page toggle? the header links
  o.topLinks=[];
  document.querySelectorAll('header a, .iq-menu a').forEach(function(a){var t=(a.innerText||'').trim();if(t&&t.length<50)o.topLinks.push(t);});
  return JSON.stringify(o);
})()""")
d=json.loads(out)
print(d)
ws.close()
