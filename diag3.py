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

# 1) إعادة تحميل الصفحة الرئيسية وانتظر ظهور صندوق البحث
js("window.location.href='https://app.alriyadh.gov.sa/BLS/faces/home'")
time.sleep(10)
for i in range(20):
    has = js("!!document.getElementById('myInput') && !!document.querySelector('a[onclick^=\"callAnyBtn\"]')")
    if has:
        print(f"انتظر: أدوات القائمة ظهرت بعد {(i+1)*3} ث")
        break
    time.sleep(3)
else:
    print("WARN: لم تظهر أدوات القائمة")
    print("body:", (js("document.body.innerText") or "").replace("\\s+" if False else "", "")[:400])
    sys.exit(1)

# 2) الكتابة في البحث
js("""(function(){
    var el = document.getElementById('myInput');
    el.focus();
    var proto = Object.getPrototypeOf(el);
    var setter = Object.getOwnPropertyDescriptor(proto, 'value');
    if(setter && setter.set) setter.set.call(el, 'BLS8510');
    else el.value = 'BLS8510';
    el.dispatchEvent(new Event('input', {bubbles:true}));
    el.dispatchEvent(new Event('keyup', {bubbles:true}));
    el.dispatchEvent(new Event('change', {bubbles:true}));
    return el.value;
})()""")
print("كتبنا في البحث: BLS8510")
found_8510 = None
for i in range(15):
    found_8510 = js("""(function(){
        var el = document.getElementById('pt1:SearchLi8510');
        if(!el) return null;
        var r = el.getBoundingClientRect();
        return {vis: r.width>0&&r.height>0, w:r.width, h:r.height, text:(el.innerText||'').replace(/\\s+/g,' ').trim().slice(0,60)};
    })()""")
    if found_8510:
        break
    time.sleep(2)
print("نتيجة البحث عن 8510:", found_8510)

# 3) النقر على النتيجة
if found_8510:
    print("نص النقر:", js("document.getElementById('pt1:SearchLi8510').click(); 'clicked'"))
    time.sleep(12)
    print("URL بعد النقر:", js("document.location.href"))
    print("هل ظهر جدول الاستعلام:", js("!!document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content')"))
    print("body:", (js("document.body.innerText") or "").replace("\\n"," ")[:500])

ws.close()