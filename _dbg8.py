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
    return v.get("value") if "value" in v else None
F='pt1:cBodFDC:r1:0:masteraTable:Fromdate::content'
def hf(): return js("!!document.getElementById('"+F+"')")=="true"
js("""(function(){
  var li=document.getElementById('pt1:SearchLi8510');
  var n=li; for(var i=0;i<8&&n;i++){n.style.setProperty('display','block','important');n.style.setProperty('visibility','visible','important');n=n.parentElement;}
  return 'ok';
})()""")
time.sleep(0.5)
xy=js("""(function(){
  var e=document.getElementById('pt1:SearchLi8510');
  var g=e.getBoundingClientRect();
  return [g.x+g.width/2, g.y+g.height/2];
})()""")
if not isinstance(xy,(list,tuple)):
    print("xy bad:", xy); sys.exit()
x,y=float(xy[0]),float(xy[1])
print("coords:", (x,y))
send("Input.dispatchMouseEvent", {"type":"mouseMoved","x":x,"y":y})
time.sleep(0.3)
send("Input.dispatchMouseEvent", {"type":"mousePressed","x":x,"y":y,"button":"left","clickCount":1})
send("Input.dispatchMouseEvent", {"type":"mouseReleased","x":x,"y":y,"button":"left","clickCount":1})
t0=time.time()
while time.time()-t0<30:
    time.sleep(1)
    if hf():
        print("FORM TRUE after %.1fs"%(time.time()-t0)); break
else:
    print("form still false after 30s")
ws.close()
