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
# 1) check visibility of top links
out=js("""(function(){
  var o={links:[],hasForm:!!document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content')};
  document.querySelectorAll('header a, .iq-menu a, a.af_link').forEach(function(a){
    var t=(a.innerText||'').replace(/\\s+/g,' ').trim();
    if(/BLS\\s*8510/i.test(t)){var g=a.getBoundingClientRect();o.links.push({t:t.slice(0,50),vis:a.offsetParent!==null,w:g.width,h:g.height,id:a.id,href:a.getAttribute('href')});}
  });
  return JSON.stringify(o);
})()""")
print("links:", out)
# 2) type into myInput
js("(function(){var e=document.getElementById('myInput');if(!e)return 'nf';e.focus();return e.value;})()")
send("Input.insertText", {"text":"8510"})
time.sleep(2)
out2=js("""(function(){
  var o={val:(document.getElementById('myInput')||{}).value};
  o.vis=[];
  document.querySelectorAll('li,a').forEach(function(e){
    var t=(e.innerText||'').replace(/\\s+/g,' ').trim();
    if(e.offsetParent!==null && /8510/i.test(t) && t.length<60) o.vis.push({tag:e.tagName,t:t,id:e.id});
  });
  return JSON.stringify(o);
})()""")
print("after typing:", out2)
ws.close()
