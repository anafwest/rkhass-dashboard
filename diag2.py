import ssl, os, urllib3, time, json, sys
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
import websocket, urllib.request

PORT = 9222

def get_tabs():
    try:
        return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=5).read())
    except Exception:
        return []

tabs = get_tabs()
ws_url = None
for t in tabs:
    u = t.get("url", "")
    if t.get("type") == "page" and "BLS" in u and u != "about:blank":
        ws_url = t.get("webSocketDebuggerUrl")
        break
if not ws_url:
    sys.exit("no tab")

ws = websocket.create_connection(ws_url, timeout=30)
_id = [0]
def send(m, p=None):
    _id[0] += 1
    msg = {"id": _id[0], "method": m}
    if p:
        msg["params"] = p
    ws.send(json.dumps(msg))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == _id[0]:
            return r.get("result", {})
def js(expr, ap=False):
    r = send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": ap})
    v = r.get("result", {})
    if "value" in v:
        return v["value"]
    return v

print("URL:", js("document.location.href"))
d = js("""(function(){
    var out = {};
    out.inputs = [];
    document.querySelectorAll('input,textarea').forEach(function(e){
        out.inputs.push({id:e.id, type:e.type, ph:e.placeholder||'', cls:(e.className||'').slice(0,60), vis:(e.getBoundingClientRect().width>0&&e.getBoundingClientRect().height>0)});
    });
    out.searchLi = {};
    ['SearchLi8100','SearchLi8200','SearchLi8300','SearchLi8500','SearchLi8510'].forEach(function(id){
        var el = document.getElementById(id);
        if(!el){out.searchLi[id]='NOT FOUND';return;}
        var r = el.getBoundingClientRect();
        out.searchLi[id] = {vis: r.width>0&&r.height>0, w:r.width, h:r.height,
                            text:(el.innerText||'').replace(/\\s+/g,' ').trim().slice(0,60),
                            parentCls:(el.parentElement&&el.parentElement.className||'').slice(0,60)};
    });
    out.sidebar = {};
    ['pt1:j_idt19','pt1:li'].forEach(function(id){
        var el = document.getElementById(id);
        if(!el){out.sidebar[id]='NOT FOUND';return;}
        var r = el.getBoundingClientRect();
        out.sidebar[id] = {vis: r.width>0&&r.height>0, w:r.width, h:r.height, text:(el.innerText||'').replace(/\\s+/g,' ').trim().slice(0,60)};
    });
    out.anyBtn = [];
    document.querySelectorAll('a[onclick^="callAnyBtn"]').forEach(function(e){
        var r = e.getBoundingClientRect();
        out.anyBtn.push({onclick:(e.getAttribute&&e.getAttribute('onclick')||''), vis:r.width>0&&r.height>0, text:(e.innerText||'').replace(/\\s+/g,' ').trim().slice(0,40)});
    });
    out.searchBoxText = (document.body.innerText||'').includes('البحث فى شاشات النظام');
    return JSON.stringify(out);
})()""", True)
print(d[:5000])
ws.close()