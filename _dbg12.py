import ssl, urllib3, json, sys, time, urllib.request, websocket
urllib3.disable_warnings(); ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
def pages():
    return json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read())
for i,p in enumerate([x for x in pages() if x.get("type")=="page"]):
    try:
        ws=websocket.create_connection(p["webSocketDebuggerUrl"],timeout=30); _id=[0]
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
        info=js(r"""(function(){
          var ins=[];
          document.querySelectorAll('input').forEach(function(i){
            var t=i.type||''; var id=i.id||'';
            if(t==='text'||t==='password'||t==='email') ins.push({id:id.slice(0,50), t:t, ph:(i.placeholder||'').slice(0,30), vis:i.offsetParent!==null});
          });
          var btns=[];
          document.querySelectorAll('button,span.af_button').forEach(function(b){
            var tx=(b.innerText||'').replace(/\\s+/g,' ').trim();
            if(tx) btns.push(tx.slice(0,30));
          });
          var _adf=(typeof window._adf!=='undefined');
          var forms=document.querySelectorAll('form').length;
          return {url:location.href, inputs:ins.slice(0,12), buttons:btns.slice(0,12), forms:forms, _adf:_adf, hasLogTable: !!document.getElementById('pt1:cBodFDC')} ;
        })()""")
        print("TAB", i, "->", json.dumps(info, ensure_ascii=False)[:900])
        ws.close()
    except Exception as e:
        print("TAB", i, "ERR", e)
