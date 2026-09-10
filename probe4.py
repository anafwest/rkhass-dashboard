import ssl, os, urllib3, time, json, sys, re
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
import websocket, urllib.request, subprocess

PORT = 9222
BLS_URL = "https://app.alriyadh.gov.sa/BLS/faces/home"
PROFILE_DIR = r"C:\Users\anaf\ScraperProfile"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

def get_tabs():
    try:
        return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=5).read())
    except Exception:
        return []

def connect_ws(url):
    ws = websocket.create_connection(url, timeout=60)
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
    return ws, send

def js(send, expr, ap=False):
    r = send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": ap})
    v = r.get("result", {})
    if "value" in v:
        return v["value"]
    if v.get("subtype") == "error":
        return "ERR:" + v.get("description", "")
    return v

tabs = get_tabs()
ws_url = None
for t in tabs:
    u = t.get("url", "")
    if t.get("type") == "page" and "BLS" in u and u != "about:blank":
        ws_url = t.get("webSocketDebuggerUrl")
        break
if not ws_url:
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True)
    time.sleep(3)
    subprocess.Popen([CHROME_PATH, f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
                      "--no-first-run", "--disable-popup-blocking", "--start-minimized",
                      "--user-data-dir=" + PROFILE_DIR, BLS_URL])
    time.sleep(30)
    tabs = get_tabs()
    for t in tabs:
        u = t.get("url", "")
        if t.get("type") == "page" and "BLS" in u and u != "about:blank":
            ws_url = t.get("webSocketDebuggerUrl")
            break
if not ws_url:
    print("FATAL: no BLS tab"); sys.exit(1)

ws, send = connect_ws(ws_url)
url = js(send, "document.location.href") or ""
print("URL:", url)
print("myInput:", js(send, "!!document.getElementById('myInput')"))
print("bodyHead:", (js(send, "document.body.innerText") or "").replace("\\n" if False else "\n", " ")[:260])

if "login" in url.lower():
    print("=> صفحة دخول")
    js(send, "window.location.href='https://app.alriyadh.gov.sa/BLS/loginApi'")
    time.sleep(20)
    url = js(send, "document.location.href") or ""
    print("بعد الاستعادة:", url)
    print("myInput:", js(send, "!!document.getElementById('myInput')"))

# فتح 8510 عبر البحث
print("has_form:", js(send, "!!document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content')"))
if not js(send, "!!document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content')"):
    js(send, "(function(){var e=document.getElementById('myInput');if(!e)return'e no';e.focus();return 'ok';})()")
    send("Input.dispatchKeyEvent", {"type": "keyDown", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65})
    send("Input.dispatchKeyEvent", {"type": "keyUp", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65})
    send("Input.insertText", {"text": "8510"})
    for i in range(20):
        if js(send, "!!document.getElementById('pt1:SearchLi8510')"):
            break
        time.sleep(0.5)
    print("SearchLi8510 الظاهرة:", js(send, "(function(){var a=document.getElementById('pt1:SearchLi8510');var r=a?a.getBoundingClientRect():null;return r?(r.width>0&&r.height>0):'no';})()"))
    js(send, "(function(){var a=document.getElementById('pt1:SearchLi8510');if(a){a.click();return 'ok';}return 'nf';})()")
    for i in range(30):
        if js(send, "!!document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content')"):
            break
        time.sleep(1)
print("بعد الفتح has_form:", js(send, "!!document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content')"))

# ضبط التواريخ والبحث
def setter(fid, val):
    js(send, "(function(){var e=document.getElementById('" + fid + "');if(!e)return;e.focus();if(e.select)e.select();})()")
    send("Input.dispatchKeyEvent", {"type": "keyDown", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65})
    send("Input.dispatchKeyEvent", {"type": "keyUp", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65})
    send("Input.insertText", {"text": val})
    js(send, "(function(){var e=document.getElementById('" + fid + "');e.dispatchEvent(new Event('change',{bubbles:true}));e.blur();})()")
    time.sleep(0.5)
    return js(send, "var e=document.getElementById('" + fid + "'); e ? e.value : ''")

print("From set:", setter("pt1:cBodFDC:r1:0:masteraTable:Fromdate::content", "1447/04/13"))
print("To set:", setter("pt1:cBodFDC:r1:0:masteraTable:Todate::content", "1448/12/29"))
js(send, "(function(){var b=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:search');if(b){b.click();return'ok';}return'nf';})()")
time.sleep(7)

r = js(send, """(function(){
    var t=null;
    document.querySelectorAll('table').forEach(function(x){if(x.className&&x.className.indexOf('af_table_data-table')>=0){if(!t||x.rows.length>t.rows.length)t=x;}});
    var out={perPage:0,rows:0};
    var rng=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_rng');
    out.rng=rng?rng.innerText.replace(/\\s+/g,' ').trim():'nf';
    out.nbLs=[];
    document.querySelectorAll('[id*=nb_ls]').forEach(function(x){out.nbLs.push(x.id);var opts=[];x.querySelectorAll('option').forEach(function(o){opts.push(o.value+'='+o.text);});out.nbLsOpts=opts;});
    out.exportBtn=!!document.getElementById('pt1:cBodFDC:r1:0:masteraTable:b11');
    if(t){out.rows=t.rows.length;}
    return JSON.stringify(out);
})()""")
print("table:", r)

# تصدير؟ قراءة سريعة لعدد الصفحات عبر النطاق
ws.close()