import ssl, urllib3, json, sys, time, urllib.request, websocket
urllib3.disable_warnings(); ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read())
ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t.get("type")=="page" and "BLS" in t.get("url",""))
ws = websocket.create_connection(ws_url, timeout=30)
_id=[0]
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
    return v.get("value","") if "value" in v else str(v)[:300]
# right click on the table to see if ADF context menu appears
r = js("""(function(){
  var t=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1');
  var g=t.getBoundingClientRect();
  var ev=new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:g.x+g.width/2,clientY:g.y+g.height/2});
  t.dispatchEvent(ev); return 'dispatched';})()""")
print(r)
time.sleep(2)
# look for any new popup/menu elements
out = js("""(function(){
  var hits=[];
  document.querySelectorAll('[class*="context"], [id*="cm"], .popup, [role="menu"], ul[class*="menu"]').forEach(function(e){
    if(e.offsetParent!==null) hits.push({id:(e.id||''), cls:(e.className||'').slice(0,60), txt:(e.innerText||'').replace(/\\s+/g,' ').trim().slice(0,120)});
  });
  return JSON.stringify(hits);
})()""")
print(out[:2500])
ws.close()
