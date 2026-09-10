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
F='pt1:cBodFDC:r1:0:masteraTable:Fromdate::content'
def hf(): return js("!!document.getElementById('"+F+"')")=="true"
# type then inspect attrs + top element at point
r=js("""(function(){
  var e=document.getElementById('pt1:myInput'); if(!e) return {err:'noinput'};
  e.focus(); e.value='8510';
  var ev=new Event('input',{bubbles:true}); e.dispatchEvent(ev);
  return null;
})()""")
time.sleep(2.5)
info=js("""(function(){
  var a=document.getElementById('pt1:SearchLi8510');
  var mi=document.getElementById('pt1:myInput');
  var g=a.getBoundingClientRect();
  var top=document.elementFromPoint(g.x+g.width/2, g.y+g.height/2);
  function desc(el){ if(!el) return null; var id=el.id||''; var c=el.className||''; return {tag:el.tagName, id:id.slice(0,60), cls:(typeof c==='string'?c:'').slice(0,60), txt:(el.innerText||'').replace(/\\s+/g,' ').trim().slice(0,40)}; }
  return {
    a_onclick: a? a.getAttribute('onclick'):null,
    a_href: a? a.getAttribute('href'):null,
    a_aria: a? a.getAttribute('aria-label'):null,
    mi_onkeydown: mi? mi.getAttribute('onkeydown'):null,
    mi_oninput: mi? mi.getAttribute('oninput'):null,
    mi_listener: mi? (JSON.stringify(mi.__listeners_||null)):null,
    mi_ph: mi? mi.getAttribute('placeholder'):null,
    topEl: desc(top),
    midChain: desc(a.parentElement? document.elementFromPoint(g.x, g.y) : null)
  };
})()""")
print(json.dumps(info, ensure_ascii=False, indent=1))
# try Enter on myInput
send("Input.dispatchKeyEvent", {"type":"keyDown","key":"Enter","code":"Enter","windowsVirtualKeyCode":13,"nativeVirtualKeyCode":13})
send("Input.dispatchKeyEvent", {"type":"keyUp","key":"Enter","code":"Enter","windowsVirtualKeyCode":13,"nativeVirtualKeyCode":13})
t0=time.time()
while time.time()-t0<25:
    time.sleep(1)
    if hf():
        print("FORM TRUE after Enter, %.1fs"%(time.time()-t0)); break
else:
    print("form still false after Enter")
ws.close()
