import ssl, urllib3, json, sys, time, urllib.request, websocket, urllib.parse as up
urllib3.disable_warnings(); ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
def tabs():
    return json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read())
req = urllib.request.Request("http://127.0.0.1:9222/json/new?"+up.quote("about:blank",safe=''), method="PUT")
nb = json.loads(urllib.request.urlopen(req, timeout=8).read())
ws=websocket.create_connection(nb["webSocketDebuggerUrl"],timeout=60); _id=[0]
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
js("window.location.href='https://app.alriyadh.gov.sa/BLS/faces/home'")
time.sleep(12)
for i in range(15):
    if js('typeof AdfPage!=="undefined"?"ok":"wait"')=="ok": break
    time.sleep(2)
print("url:", js("document.location.href")[:80])
print("hasForm at start:", js("!!document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content')"))
o=js("(function(){var e=document.getElementById('myInput');var g=e?e.getBoundingClientRect():null;return JSON.stringify({has:!!e,vis:e?e.offsetParent!==null:false,w:g?g.width:0});})()")
print("myInput:", o)
js("(function(){var e=document.getElementById('myInput');if(!e)return;e.focus();})()")
send("Input.dispatchKeyEvent", {"type":"keyDown","modifiers":2,"key":"a","code":"KeyA","windowsVirtualKeyCode":65})
send("Input.dispatchKeyEvent", {"type":"keyUp","modifiers":2,"key":"a","code":"KeyA","windowsVirtualKeyCode":65})
send("Input.insertText", {"text":"8510"})
time.sleep(3)
r=js("""(function(){
  var found=null;
  document.querySelectorAll('li').forEach(function(e){var t=(e.innerText||'').replace(/\\s+/g,' ').trim();var g=e.getBoundingClientRect();
    if(!found && e.offsetParent!==null && /BLS\\s*8510/i.test(t) && g.width>0 && t.length<60) found=e;});
  if(found){found.click(); return 'clicked:'+found.innerText.slice(0,30).replace(/\\s+/g,' ');}
  return 'none';
})()""")
print("click result:", r)
t0=time.time(); res=None
for i in range(30):
    res=js("!!document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content')")
    if res=="true": break
    time.sleep(1)
print("form after %.1fs:"%(time.time()-t0), res)
ws.close()
