import json, ssl, urllib.request
ssl._create_default_https_context = ssl._create_unverified_context
import websocket
tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read())
t = next((x for x in tabs if x.get("type")=="page" and "BLS" in x.get("url","")), None)
print("tab:", (t or {}).get("url","")[:90])
if not t: raise SystemExit
ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=20)
_id=[0]
def send(m,p=None):
    _id[0]+=1
    msg={"id":_id[0],"method":m}
    if p: msg["params"]=p
    ws.send(json.dumps(msg))
    while True:
        r=json.loads(ws.recv())
        if r.get("id")==_id[0]: return r.get("result",{})
JS = """(function(){
  var out={};
  var t=document.querySelector('table.af_table_data-table');
  out.bodyRows = t ? t.tBodies[0].rows.length : -1;
  out.theadRows = t ? t.tHead.rows.length : -1;
  out.theadCols = t ? t.tHead.rows[0].cells.length : -1;
  if(t){
    var r=t.tBodies[0].rows[0];
    out.firstBodyCols = r? r.cells.length : -1;
    out.firstBodyFirstCol = r ? r.cells[0].innerText.trim().slice(0,30) : '';
    out.firstBodyLastCol = r ? r.cells[r.cells.length-1].innerText.trim().slice(0,30) : '';
  }
  var nx=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_nx');
  out.nextExists = !!nx;
  out.nextText = nx? (nx.innerText||''):'';
  var fr=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_fr');
  out.firstExists = !!fr;
  var pv=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_pv');
  out.prevExists = !!pv;
  var cnt=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_cnt');
  out.cnt = cnt? cnt.innerText : '';
  var inp=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_in_pg');
  out.inp = inp? ('V='+inp.value) : '';
  var rng=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_rng');
  out.rng = rng? rng.innerText : '';
  return JSON.stringify(out);
})()
"""
r = send("Runtime.evaluate",{"expression":JS,"returnByValue":True})
print(r["result"]["value"][:2000])
