import ssl, urllib3, json, sys, time, urllib.request, websocket
urllib3.disable_warnings(); ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read())
t=[x for x in tabs if x.get("type")=="page"]
ws=websocket.create_connection(t[0]["webSocketDebuggerUrl"],timeout=60); _id=[0]
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
def hasForm():
    return js("!!document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content')")
# full reload to clean ADF task
js("location.reload(true);")
time.sleep(12)
for i in range(20):
    if js('typeof AdfPage!=="undefined"?"ok":"wait"')=="ok": break
    time.sleep(1)
print("after reload hasForm:", hasForm())
# clear myInput and type 8510
js("(function(){var e=document.getElementById('myInput');if(!e)return 'nf';e.focus();return 'ok';})()")
send("Input.dispatchKeyEvent", {"type":"keyDown","modifiers":2,"key":"a","code":"KeyA","windowsVirtualKeyCode":65})
send("Input.dispatchKeyEvent", {"type":"keyUp","modifiers":2,"key":"a","code":"KeyA","windowsVirtualKeyCode":65})
send("Input.insertText", {"text":"8510"})
time.sleep(2.5)
vis=js("""(function(){
  var o=[];
  document.querySelectorAll('li').forEach(function(e){
    var t=(e.innerText||'').replace(/\\s+/g,' ').trim();
    var g=e.getBoundingClientRect();
    if(e.offsetParent!==null && /BLS\\s*8510/i.test(t) && g.width>0 && t.length<60) o.push({t:t.slice(0,45),w:g.width,h:g.height});
  });
  return JSON.stringify(o);
})()""")
print("visible LIs:", vis)
# click the topmost visible LI matching 8510
r=js("""(function(){
  var picks=[];
  document.querySelectorAll('li').forEach(function(e){
    var t=(e.innerText||'').replace(/\\s+/g,' ').trim();
    var g=e.getBoundingClientRect();
    if(e.offsetParent!==null && /BLS\\s*8510/i.test(t) && g.width>0 && t.length<60) picks.push(e);
  });
  if(picks.length){picks[0].click();return 'clicked '+picks.length;}
  return 'none';
})()""")
print("click:", r)
t0=time.time()
for i in range(30):
    if hasForm()=="true": break
    time.sleep(1)
print("form after %.1fs:"%(time.time()-t0), hasForm())
ws.close()
