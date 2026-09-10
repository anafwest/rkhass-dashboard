# -*- coding: utf-8 -*-
"""probe6: تشخيص محدد حجم الصفحة nb_ls في جدول 8510 لرفع عدد الصفوف لكل صفحة."""
import ssl, os, urllib3, time, json, sys, subprocess, urllib.parse as up
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
import websocket, urllib.request

PORT = 9222
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE_DIR = r"C:\Users\anaf\ScraperProfile"
BLS_SSO_URL = "https://app.alriyadh.gov.sa/BLS/loginApi"
FROM_FIELD = "pt1:cBodFDC:r1:0:masteraTable:Fromdate::content"
FROM_DATE = "1447/04/13"
TO_DATE = "1448/12/29"
SEARCH_BTN = "pt1:cBodFDC:r1:0:masteraTable:search"
RNG_ID = "pt1:cBodFDC:r1:0:masteraTable:t1::nb_rng"

def get_tabs():
    try: return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json",timeout=5).read())
    except: return []

def connect_ws(url):
    ws = websocket.create_connection(url, timeout=60)
    ws.settimeout(30)
    _id = [0]
    def send(m, p=None):
        _id[0] += 1
        msg = {"id":_id[0],"method":m}
        if p: msg["params"] = p
        ws.send(json.dumps(msg))
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == _id[0]: return r.get("result",{})
    return ws, send

def js(send, expr, ap=False):
    r = send("Runtime.evaluate",{"expression":expr,"returnByValue":True,"awaitPromise":ap})
    v = r.get("result",{})
    if "value" in v: return v["value"]
    return v

def start():
    subprocess.call(["taskkill","/F","/IM","chrome.exe","/T"], stderr=subprocess.DEVNULL)
    time.sleep(3)
    subprocess.Popen([CHROME_PATH,f"--remote-debugging-port={PORT}","--remote-allow-origins=*",
        "--no-first-run","--disable-popup-blocking","--start-minimized",
        f"--user-data-dir={PROFILE_DIR}",BLS_SSO_URL])
    for i in range(30):
        time.sleep(2)
        ts = get_tabs()
        if ts: return ts
    return []

ts = start()
print("tabs:", len(ts))
ws_url = None
for t in ts:
    u = t.get("url","")
    if t.get("type")=="page" and "BLS" in u and u != "about:blank":
        ws_url = t.get("webSocketDebuggerUrl"); break
if not ws_url:
    for t in ts:
        if t.get("type")=="page":
            ws_url = t.get("webSocketDebuggerUrl"); break
print("ws:", ws_url)
ws, send = connect_ws(ws_url)

# انتظار ADF + myInput (إعادة مصادقة عبر SSO)
t0 = time.time()
while time.time()-t0 < 90:
    u = js(send,"document.location.href") or ""
    if "login" in u.lower() and "faces" not in u.lower():
        js(send,f"window.location.href='{BLS_SSO_URL}'")
    if js(send,'typeof AdfPage!=="undefined"?"ok":"wait"')=="ok" and js(send,"!!document.getElementById('myInput')"):
        break
    time.sleep(2)
print("URL:", (js(send,"document.location.href") or "")[:100])
print("myInput:", js(send,"!!document.getElementById('myInput')"))

# فتح 8510 عبر البحث
if js(send,"!!document.getElementById('myInput')"):
    js(send,"(function(){var e=document.getElementById('myInput');e.focus();})()")
    send("Input.dispatchKeyEvent",{"type":"keyDown","modifiers":2,"key":"a","code":"KeyA","windowsVirtualKeyCode":65})
    send("Input.dispatchKeyEvent",{"type":"keyUp","modifiers":2,"key":"a","code":"KeyA","windowsVirtualKeyCode":65})
    send("Input.insertText",{"text":"8510"})
    t0=time.time()
    while time.time()-t0<8:
        if js(send,"(function(){var a=document.getElementById('pt1:SearchLi8510');return !!a&&a.offsetParent!==null;})()"):
            break
        time.sleep(0.5)
    js(send,"(function(){var a=document.getElementById('pt1:SearchLi8510');if(a){a.click();return 'ok';}return 'nf';})()")
t0=time.time()
while time.time()-t0<25:
    if js(send,"!!document.getElementById('"+FROM_FIELD+"')"):
        print("form: ok"); break
    time.sleep(0.5)
else:
    print("form: NO"); sys.exit(1)

# ضبط التاريخين ثم البحث
def type_into(fid, val):
    js(send,"(function(){var e=document.getElementById('"+fid+"');e.focus();if(e.select)e.select();})()")
    send("Input.dispatchKeyEvent",{"type":"keyDown","modifiers":2,"key":"a","code":"KeyA","windowsVirtualKeyCode":65})
    send("Input.dispatchKeyEvent",{"type":"keyUp","modifiers":2,"key":"a","code":"KeyA","windowsVirtualKeyCode":65})
    send("Input.insertText",{"text":val})
    js(send,"(function(){var e=document.getElementById('"+fid+"');e.dispatchEvent(new Event('change',{bubbles:true}));e.blur();})()")
    time.sleep(0.6)

for fid,val in ((FROM_FIELD,FROM_DATE),):
    type_into(fid,val)
# To date
type_into("pt1:cBodFDC:r1:0:masteraTable:Todate::content", TO_DATE)
js(send,"(function(){var b=document.getElementById('"+SEARCH_BTN+"');b.click();})()")

t0=time.time(); info={}
while time.time()-t0<20:
    txt = js(send,"(function(){var r=document.getElementById('"+RNG_ID+"');return r?r.innerText.replace(/\\s+/g,' ').trim():'nf';})()")
    if txt!="nf" and "من" in txt:
        time.sleep(1); break
    time.sleep(0.5)
print("rng:", txt)

# DOM محدد nb_ls
print("--- nb_ls DOM ---")
print(js(send,"""(function(){
    var els=document.querySelectorAll('[id*="::nb_ls"], [id*=":nb_ls"]');
    var out=[];
    els.forEach(function(e){
        var opts=[];
        e.querySelectorAll('option').forEach(function(o){opts.push({v:o.value,t:o.text});});
        out.push({id:e.id,tag:e.tagName,opts:opts,html:e.outerHTML.slice(0,500)});
    });
    return JSON.stringify(out);
})()"""))
print("--- other select/range controls ---")
print(js(send,"""(function(){
    var out=[];
    document.querySelectorAll('select').forEach(function(e){
        var opts=[];
        e.querySelectorAll('option').forEach(function(o){opts.push(o.value+':'+o.text);});
        out.push({id:e.id,opts:opts});
    });
    return JSON.stringify(out);
})()"""))
print("--- current perPage spec ---")
pp = js(send,"""(function(){
    var el=document.querySelectorAll('[id*="::nb_ls"]')[0];
    if(!el) return 'nf';
    return {val:el.value, selIdx:el.selectedIndex, txt:(el.options&&el.options[el.selectedIndex])?el.options[el.selectedIndex].text:''};
})()""")
print(pp)

# جرّب تغيير القيمة لكل خيار وراقب النتيجة
import re
try:
    spec = json.loads(js(send,"""(function(){
        var el=document.querySelectorAll('[id*="::nb_ls"]')[0];
        if(!el) return 'nf';
        var opts=[];
        el.querySelectorAll('option').forEach(function(o){opts.push({v:o.value,t:o.text});});
        return JSON.stringify(opts);
    })()"""))
except Exception:
    spec = []
print("options:", spec)
if isinstance(spec, list) and spec:
    for o in spec:
        v = o.get("v"); t = o.get("t")
        js(send,"(function(){var el=document.querySelectorAll('[id*=\"::nb_ls\"]')[0];"
                "el.value='"+v+"';el.dispatchEvent(new Event('change',{bubbles:true}));})()")
        time.sleep(3)
        rng = js(send,"(function(){var r=document.getElementById('"+RNG_ID+"');return r?r.innerText.replace(/\\s+/g,' ').trim():'nf';})()")
        print(f"try {v} ({t}) -> {rng}")
        m = re.search(r"\((\d+)-(\d+)\s+من\s+([\d,]+)", rng or "")
        if m:
            lo, hi, tot = int(m.group(1)), int(m.group(2)), int(m.group(3).replace(',',''))
            if hi - lo + 1 > 5:
                print(f">> perPage أصبح {hi-lo+1} صف/صفحة, صفحات ~{ (tot + (hi-lo))//(hi-lo+1) }")
        time.sleep(0.5)
ws.close()
print("done")