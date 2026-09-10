import ssl, os, urllib3, time, json, sys, re
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
import websocket, urllib.request, subprocess

PORT = 9222
BLS_URL = "https://app.alriyadh.gov.sa/BLS/faces/home"
PROFILE_DIR = r"C:\Users\anaf\ScraperProfile"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

def log(msg):
    print(msg, flush=True)

def get_tabs():
    try:
        return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=5).read())
    except Exception:
        return []

def connect_ws(url):
    ws = websocket.create_connection(url, timeout=30)
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
    if t.get("type") == "page" and "BLS/faces" in u:
        ws_url = t.get("webSocketDebuggerUrl")
        break
if not ws_url:
    for t in tabs:
        u = t.get("url", "")
        if t.get("type") == "page" and "BLS" in u and u != "about:blank":
            ws_url = t.get("webSocketDebuggerUrl")
            break

if not ws_url:
    log("لا يوجد تبويب BLS — تشغيل Chrome...")
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True)
    time.sleep(3)
    subprocess.Popen([CHROME_PATH, f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
                      "--no-first-run", "--disable-popup-blocking", "--start-minimized",
                      f"--user-data-dir={PROFILE_DIR}", BLS_URL])
    time.sleep(25)
    tabs = get_tabs()
    for t in tabs:
        u = t.get("url", "")
        if t.get("type") == "page" and "BLS" in u and u != "about:blank":
            ws_url = t.get("webSocketDebuggerUrl")
            break
    if not ws_url:
        log("FATAL: لا تبويب BLS")
        sys.exit(1)

log(f"تبويب: {ws_url[:80]}...")
ws, send = connect_ws(ws_url)

url = js(send, "document.location.href")
log(f"الرابط الحالي: {url}")

if "login" in url.lower():
    log("صفحة دخول — محاولة استعادة الجلسة...")
    js(send, f"window.location.href='https://app.alriyadh.gov.sa/BLS/loginApi'")
    time.sleep(20)
    url = js(send, "document.location.href")
    log(f"بعد الاستعادة: {url}")

for i in range(10):
    if js(send, 'typeof AdfPage !== "undefined" ? "ok" : "wait"') == "ok":
        break
    log(f"انتظار ADF... ({i+1})")
    time.sleep(3)

log("=" * 60)
log("فحص الصفحة:")
log(f"URL: {js(send, 'document.location.href')}")

d = js(send, "(function(){"
            "var o={};"
            "o.titles=[];"
            "document.querySelectorAll('h1,h2,h3,legend,strong,.af_panelWindow_title').forEach(function(e){var t=(e.innerText||'').trim();if(t&&t.length<80)o.titles.push(t);});"
            "o.menuItems=[];"
            "document.querySelectorAll('a,span,div,td,li,h4,h5').forEach(function(e){var t=(e.innerText||'').replace(/\\s+/g,' ').trim();if(/BLS\\s*8\\d\\d\\d/.test(t)&&t.length<120){o.menuItems.push({tag:e.tagName,t:t.slice(0,80),detailed:(e.outerHTML||'').slice(0,300)});}});"
            "o.hasTable=!!document.querySelector('table.af_table_data-table');"
            "o.hasFromdate=!!document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content');"
            "o.bodyLen=(document.body.innerText||'').length;"
            "o.bodyHead=(document.body.innerText||'').replace(/\\s+/g,' ').slice(0,1500);"
            "return JSON.stringify(o);})()")
try:
    info = json.loads(d)
except Exception:
    log("تعذر فك النتيجة:")
    log(str(d)[:2000])
    sys.exit(1)

log(f"العناوين: {info.get('titles')}")
log(f"حضور الجدول: {info.get('hasTable')} | حقل التاريخ: {info.get('hasFromdate')}")
log(f"طول نص الصفحة: {info.get('bodyLen')}")
log(f"بداية النص:\n{info.get('bodyHead')}")
log("=" * 60)
menus = info.get("menuItems") or []
log(f"عدد عناصر القائمة المطابقة: {len(menus)}")
for m in menus:
    log(f"  [{m['tag']}] {m['t']}")
    log(f"      HTML: {m['detailed']}")

# محاولة الوصول المباشر عبر عنصر masteraTable لو ظهر
ws.close()