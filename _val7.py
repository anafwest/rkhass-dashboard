import ssl, urllib3, json, sys, time, urllib.request, websocket
urllib3.disable_warnings(); ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read())
t=[x for x in tabs if x.get("type")=="page"]
ws=websocket.create_connection(t[0]["webSocketDebuggerUrl"],timeout=45); _id=[0]
def send(m,p=None):
    _id[0]+=1; d={"id":_id[0],"method":m}
    if p: d["params"]=p
    ws.send(json.dgs(d)) if False else None
    ws.send(json.dumps(d))
    while True:
        r=json.loads(ws.recv())
        if r.get("id")==_id[0]: return r.get("result",{})
def js(e):
    r=send("Runtime.evaluate",{"expression":e,"returnByValue":True})
    v=r.get("result",{})
    return v.get("value","") if "value" in v else str(v)[:400]
# fresh home
js("window.location.href='https://app.alriyadh.gov.sa/BLS/faces/home'")
time.sleep(10)
# wait ADF
for i in range(10):
    if js('typeof AdfPage!=="undefined"?"ok":"wait"')=="ok": break
    time.sleep(2)
o=js("(function(){var e=document.getElementById('myInput');var box=e? e.getBoundingClientRect():null;return JSON.stringify({has:!!e, vis: e? (e.offsetParent!==null):false, w:box?box.width:0});})()")
print("myInput:", o)
# type 8510
js("(function(){var e=document.getElementById('myInput');e.focus();return 'ok';})()")
send("Input.insertText", {"text":"8510"})
time.sleep(2)
res=js("""(function(){
  var o=[];
  document.querySelectorAll('li,a,span').forEach(function(e){
    var t=(e.innerText||'').replace(/\\s+/g,' ').trim();
    if(e.offsetParent!==null && /BLS\\s*8510/i.test(t) && t.length<60 && !o.some(function(z){return z.id&&z.id===e.id||z.tag===e.tagName&&z.t===t;})){
      var g=e.getBoundingClientRect(); o.push({tag:e.tagName,t:t.slice(0,45),id:e.id,w:g.width>0});
    }
  });
  return JSON.stringify(o.slice(0,8));
})()""")
print("results:", res)
ws.close()
