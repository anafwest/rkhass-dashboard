import ssl, os, urllib3, time, json, sys, glob
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
import websocket, urllib.request

PORT = 9222
DL = r"C:\Users\anaf\AppData\Local\Temp\opencode\bls_export"

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
    print("no tab"); sys.exit(1)

ws = websocket.create_connection(ws_url, timeout=60)
ws.settimeout(30)
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

os.makedirs(DL, exist_ok=True)
send("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": DL})
print("URL:", js("document.location.href"))
print("has_form:", js("!!document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content')"))
print("exportBtn:", js("!!document.getElementById('pt1:cBodFDC:r1:0:masteraTable:b11')"))
print("rng:", js("(function(){var r=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_rng');return r?r.innerText.replace(/\\s+/g,' ').trim():'nf';})()"))

# فحص عناصر التصدير المحتملة حول الجدول
print("btns:", js("""(function(){var o=[];document.querySelectorAll('a,button,[role=button]').forEach(function(e){
    var t=(e.innerText||'').replace(/\\s+/g,' ').trim();
    if(/تصدير|توجيه|excel|csv|pdf|تحميل|export/i.test(t)&&t.length<40)o.push({id:e.id,tag:e.tagName,onclick:(e.getAttribute&&e.getAttribute('onclick')||''),t:t});
});return JSON.stringify(o.slice(0,15));})()"""))

# النقر على زر التصدير
r = js("(function(){var b=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:b11');if(b){b.click();return 'clicked';}return 'nf';})()")
print("click b11:", r)
time.sleep(5)
print("dialog:", js("""(function(){var o=[];document.querySelectorAll('.af_panelWindow, [class*=dialog], [class*=PopUp], [class*=popup], [class*=modal]').forEach(function(e){
    var t=e.innerText||''; if(t&&t.trim()) o.push(t.replace(/\\s+/g,' ').trim().slice(0,300));
});return JSON.stringify(o.slice(0,8));})()"""))
time.sleep(4)
fl = glob.glob(os.path.join(DL, "*"))
print("downloaded:", fl)

# حدث _popup جديد؟
try:
    pop = send("Target.getTargets", {})
    infos = [t for t in pop.get("targetInfos", [])]
    for i in infos[:20]:
        print("target:", i.get("type"), "|", i.get("url", "")[:120])
except Exception as e:
    print("targets err", e)
ws.close()