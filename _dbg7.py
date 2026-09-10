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
# inspect classes/styles of UL and leaves
out=js("""(function(){
  var ul=document.getElementById('searchMenuScreensUL');
  var li=document.getElementById('pt1:SearchLi8510');
  var ulcs=ul? getComputedStyle(ul):{};
  var lic=(li&&li.parentElement)? getComputedStyle(li.parentElement):{};
  return JSON.stringify({
    ulCls: ul? ul.className:'nf', ulD: ulcs.display, ulMH: ulcs.maxHeight, ulVis: ulcs.visibility,
    liD: lic.display, liMH: lic.maxHeight, liVis: lic.visibility,
    html:(ul? ul.outerHTML.slice(0,500):'')
  });
})()""")
print(out)
# force-show the whole chain
js("""(function(){
  var ul=document.getElementById('searchMenuScreensUL');
  if(ul){ul.style.setProperty('display','block','important');ul.style.setProperty('max-height','none','important');}
  var li=document.getElementById('pt1:SearchLi8510');
  var n=li; for(var i=0;i<8&&n;i++){n.style.setProperty('display','block','important');n.style.setProperty('visibility','visible','important');n.style.setProperty('opacity','1','important');n=n.parentElement;}
  return 'ok';
})()""")
time.sleep(1)
print("vis 8510:", js("(function(){var e=document.getElementById('pt1:SearchLi8510');var g=e.getBoundingClientRect();return e.offsetParent!==null?('V '+g.width+'x'+g.height):'h';})()"))
# now click
js("(function(){var e=document.getElementById('pt1:SearchLi8510');e.click();return 'ok';})()")
t0=time.time()
while time.time()-t0<30:
    time.sleep(1)
    if hf():
        print("FORM TRUE after %.1fs"%(time.time()-t0)); break
else:
    print("form still false after 30s")
ws.close()
