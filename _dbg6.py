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
def vis(cid):
    return js("(function(){var e=document.getElementById('"+cid+"');return e? (e.offsetParent!==null?'V':'h'):'M';})()")
# click the parent LI (البحث فى شاشات النظام) - click its inner link/span
r=js("""(function(){
  var li=null;
  document.querySelectorAll('#iq-sidebar-toggle > li').forEach(function(l){
    var t=(l.innerText||'').replace(/\\s+/g,' ');
    if(!li && /البحث\\s*فى\\s*شاشات\\s*النظام/.test(t)) li=l;
  });
  if(!li) return 'nf';
  var a=li.querySelector('a'); if(a){a.click(); return 'clicked a';}
  li.click(); return 'clicked li';
})()""")
print("expand:", r)
time.sleep(2.5)
print("SearchLi8510 now:", vis('pt1:SearchLi8510'), "| 8500:", vis('pt1:SearchLi8500'))
# click the leaf
js("(function(){var e=document.getElementById('pt1:SearchLi8510');if(e)e.click();return 'ok';})()")
t0=time.time()
while time.time()-t0<30:
    time.sleep(1)
    if hf():
        print("FORM TRUE after %.1fs"%(time.time()-t0)); break
else:
    print("form still false after 30s")
ws.close()
