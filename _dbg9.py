import ssl, urllib3, json, sys, time, urllib.request, websocket
urllib3.disable_warnings(); ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
def pages():
    return json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read())
def page_ws(page=None):
    t=[x for x in pages() if x.get("type")=="page"]
    if page is not None and page>=len(t): page=0
    return websocket.create_connection(t[page]["webSocketDebuggerUrl"],timeout=60)
# list page tabs + urls BEFORE
for p in pages():
    if p.get("type")=="page": print("TAB0:", p.get("url"), "|", p.get("title"))
ws=page_ws(0); _id=[0]
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
def showResults():
    return js("""(function(){
      var u=document.getElementById('searchMenuScreensUL');
      if(!u) return 'no ul';
      var out=[];
      u.querySelectorAll('li').forEach(function(li){
        var a=li.querySelector('a.af_link'); var s=(a?a.innerText||'':'');
        out.push({id:li.id, a:(a?a.id:''), t:s.replace(/\\s+/g,' ').trim().slice(0,40), vis:li.offsetParent!==null});
      });
      return out;
    })()""")
# ---- type query in myInput
r=js("(function(){var e=document.getElementById('pt1:myInput');if(!e)return 'noinput';e.focus();e.value='';return 'ok';})()")
print("focus:",r)
for ch in '8510':
    js("(function(){var e=document.getElementById('pt1:myInput');e.value=e.value+'CH';var ev=new Event('input',{bubbles:true});e.dispatchEvent(ev);return 'ok';})()".replace('CH',ch))
    time.sleep(1.2)
time.sleep(2)
print("URL:", js("location.href"))
rows=showResults()
print("ROWS:", json.dumps(rows, ensure_ascii=False)[:1200])
# find the leaf A with id SearchLi8510
target=js("""(function(){
  var u=document.getElementById('searchMenuScreensUL');
  var a=u? u.querySelector('a[id="pt1:SearchLi8510"]') : null;
  if(!a) return 'miss';
  var g=a.getBoundingClientRect();
  return {ok:true, v:a.offsetParent!==null, x:g.x+g.width/2, y:g.y+g.height/2, t:(a.innerText||'').replace(/\\S+/g,' ').replace(/\\s+/g,' ').trim()};
})()""")
print("TARGET:", js("location.href"))
print("TARGET2:", target)
if isinstance(target,dict) and target.get("ok"):
    x,y=target["x"],target["y"]
    send("Input.dispatchMouseEvent", {"type":"mouseMoved","x":x,"y":y})
    time.sleep(0.3)
    send("Input.dispatchMouseEvent", {"type":"mousePressed","x":x,"y":y,"button":"left","clickCount":1})
    send("Input.dispatchMouseEvent", {"type":"mouseReleased","x":x,"y":y,"button":"left","clickCount":1})
    print("clicked at", (x,y))
t0=time.time()
while time.time()-t0<45:
    time.sleep(1)
    if hf():
        print("FORM TRUE after %.1fs"%(time.time()-t0)); break
else:
    print("form still false after 45s")
print("URL AFTER:", js("location.href"))
print("TABS AFTER:")
for p in pages():
    if p.get("type")=="page": print("  ", p.get("url"), "|", p.get("title"))
ws.close()
