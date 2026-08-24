import ssl, os, urllib3, time, json, sys, glob
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
import websocket, urllib.request, pandas as pd, subprocess
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE_DIR = r"C:\Users\anaf\ScraperProfile"
PORT = 9222
BLS_URL = "https://app.alriyadh.gov.sa/BLS/faces/home"
SSO_URL = "https://app.alriyadh.gov.sa/SSO/loginApi"
COLS = ["طلب الخدمة","السنة","نوع الخدمة","وصف المرحلة","الجهة","تاريخ الطلب",
        "تاريخ الطلب ميلادي","رقم الرخصة","سنة الرخصة","نوع الهوية","المالك",
        "رقم الهوية","تاريخ المراجعة","تاريخ المراجعة ميلادي","رقم الطلب"]

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with open("scraper_log.txt","a",encoding="utf-8") as f: f.write(line+"\n")
    print(line)

def get_tabs():
    try: return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json",timeout=5).read())
    except: return []

def connect_ws(url):
    ws = websocket.create_connection(url, timeout=30)
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
    if v.get("subtype")=="error": return "ERR:"+v.get("description","")
    return v

def kill_chrome():
    subprocess.run(["taskkill","/F","/IM","chrome.exe","/T"], capture_output=True)
    time.sleep(3)

def cdp_type(send, text):
    send("Input.insertText", {"text": text})

def start_chrome():
    kill_chrome()
    subprocess.Popen([CHROME_PATH,f"--remote-debugging-port={PORT}","--remote-allow-origins=*",
        "--no-first-run","--disable-popup-blocking",f"--user-data-dir={PROFILE_DIR}",SSO_URL])
    log("انتظار Chrome...")
    for i in range(20):
        time.sleep(2)
        if get_tabs(): return True
    return False

READ_DATA_JS = """(function(){
    var table = null;
    var tables = document.querySelectorAll('table');
    tables.forEach(function(t){
        if(t.className && t.className.indexOf('af_table_data-table') >= 0){
            if(!table || t.rows.length > table.rows.length) table = t;
        }
    });
    if(!table) return JSON.stringify({rows:[],total:0,pages:0,page:0});
    var rows = [];
    for(var r=1; r<table.rows.length; r++){
        var tds = table.rows[r].querySelectorAll('td');
        var row = [], hasData = false;
        tds.forEach(function(td){
            var txt = (td.innerText||'').trim();
            row.push(txt);
            if(txt.length > 0) hasData = true;
        });
        if(hasData && row.length >= 10) rows.push(row);
    }
    var text = document.body.innerText;
        var m = text.match(/\\(([\\d,]+)-(\\d[\\d,]+)\\s+من\\s+(\\d[\\d,]+)/);
        var m2 = text.match(/العدد\\s*(\\d[\\d,]*)/);
        var total = 0;
        if(m) total = parseInt(m[3].replace(/,/g,''));
        else if(m2) total = parseInt(m2[1].replace(/,/g,''));
        if(!total) total = rows.length;
        var page = m ? parseInt(m[1].replace(/,/g,'')) : 1;
        var perPage = m ? parseInt(m[2].replace(/,/g,'')) - parseInt(m[1].replace(/,/g,'')) + 1 : rows.length;
        var pages = total > 0 ? Math.ceil(total / perPage) : 1;
    return JSON.stringify({rows:rows,total:total,pages:pages,page:page,perPage:perPage});
})()"""

def next_page_js(target):
    return f"""(function(){{
        var target = {target};
        var anchors = document.querySelectorAll('a');
        for(var i=0; i<anchors.length; i++){{
            var t = anchors[i].innerText.trim();
            if(t === String(target) && anchors[i].id && anchors[i].id.indexOf('nb_pg') >= 0){{
                anchors[i].click();
                return JSON.stringify({{ok:true, next:target}});
            }}
        }}
        for(var i=0; i<anchors.length; i++){{
            var t = anchors[i].innerText.trim();
            if(t === String(target) && anchors[i].href && anchors[i].href.indexOf('void') >= 0){{
                anchors[i].click();
                return JSON.stringify({{ok:true, next:target}});
            }}
        }}
        return JSON.stringify({{error:'link for page '+target+' not found'}});
    }})()"""

EXPORT_JS = """(function(){
    var btn = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:b11');
    if(!btn) return JSON.stringify({error:'export btn not found'});
    btn.click();
    return JSON.stringify({ok:true});
})()"""

# ==================== MAIN ====================
log("="*60)
log("بدء السحب التلقائي")

tabs = get_tabs()
has_bls = any("BLS" in t.get("url","") and "login" not in t.get("url","").lower()
              for t in tabs if t.get("type")=="page")

if not has_bls:
    if not start_chrome():
        log("FATAL: Chrome didnt start"); sys.exit(1)
    log("انتظار SSO..."); time.sleep(20)

for attempt in range(5):
    tabs = get_tabs()
    ws_url = None
    for t in tabs:
        u = t.get("url","")
        if t.get("type")=="page" and "alriyadh" in u and u != "about:blank":
            ws_url = t.get("webSocketDebuggerUrl"); break
    if ws_url: break
    log(f"انتظار تبويب البوابة... ({attempt+1})"); time.sleep(5)

if not ws_url:
    log("FATAL: no tab"); sys.exit(1)

ws, send = connect_ws(ws_url)
url = js(send, "document.location.href")
log(f"متصل: {url[:100]}")

# Wait for ADF to be ready
for i in range(10):
    r = js(send, 'typeof AdfPage !== "undefined" ? "ok" : "wait"')
    if r == "ok": break
    log(f"انتظار ADF... ({i+1})"); time.sleep(3)

url = js(send, "document.location.href")
log(f"الرابط: {url[:100]}")

# If we're on SSO home, navigate to BLS
if "BLS" not in url:
    log("الانتقال لـ BLS...")
    js(send, f"window.location.href='{BLS_URL}'")
    time.sleep(15)
    url = js(send, "document.location.href")
    log(f"بعد الانتقال: {url[:100]}")

# Handle login page
# Handle login page - try re-establishing session
if "login" in url.lower():
    log("صفحة دخول - محاولة إعادة تأسيس الجلسة...")
    # Go back to SSO loginApi to refresh session
    js(send, f"window.location.href='{SSO_URL}'")
    time.sleep(15)
    url = js(send, "document.location.href")
    log(f"SSO: {url[:100]}")
    # Wait for ADF
    for i in range(8):
        r = js(send, 'typeof AdfPage !== "undefined" ? "ok" : "wait"')
        if r == "ok": break
        time.sleep(3)
    # Now try BLS again
    js(send, f"window.location.href='{BLS_URL}'")
    time.sleep(15)
    url = js(send, "document.location.href")
    log(f"BLS retry: {url[:100]}")

if "login" in url.lower():
    log("ما نقدر نتجاوز صفحة الدخول"); ws.close(); sys.exit(1)

# Wait for BLS page to fully load
for i in range(6):
    info = json.loads(js(send, READ_DATA_JS))
    if info.get("rows"): break
    log(f"انتظار بيانات... ({i+1})"); time.sleep(5)

if not info.get("rows"):
    log("الجدول فاضي - ضبط التواريخ والبحث...")
    from_date = "1447/04/13"
    to_date = "1448/12/29"

    # Focus From date, get position, triple-click to select, type
    r = js(send, """(function(){
        var el = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content');
        if(!el) return 'not found';
        el.focus();
        el.removeAttribute('readonly');
        var rect = el.getBoundingClientRect();
        return JSON.stringify({x:rect.x+rect.width/2, y:rect.y+rect.height/2});
    })()""")
    if r and r != 'not found':
        pos = json.loads(r)
        time.sleep(0.3)
        send("Input.dispatchMouseEvent", {"type":"mousePressed", "x":pos["x"], "y":pos["y"], "button":"left", "clickCount":3})
        send("Input.dispatchMouseEvent", {"type":"mouseReleased", "x":pos["x"], "y":pos["y"], "button":"left", "clickCount":3})
        time.sleep(0.2)
        send("Input.insertText", {"text": from_date})
        time.sleep(0.5)
        js(send, "document.body.click()")
        time.sleep(1)
    log(f"From date set: {from_date}")

    # Focus To date, get position, triple-click to select, type
    r = js(send, """(function(){
        var el = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Todate::content');
        if(!el) return 'not found';
        el.focus();
        el.removeAttribute('readonly');
        var rect = el.getBoundingClientRect();
        return JSON.stringify({x:rect.x+rect.width/2, y:rect.y+rect.height/2});
    })()""")
    if r and r != 'not found':
        pos = json.loads(r)
        time.sleep(0.3)
        send("Input.dispatchMouseEvent", {"type":"mousePressed", "x":pos["x"], "y":pos["y"], "button":"left", "clickCount":3})
        send("Input.dispatchMouseEvent", {"type":"mouseReleased", "x":pos["x"], "y":pos["y"], "button":"left", "clickCount":3})
        time.sleep(0.2)
        send("Input.insertText", {"text": to_date})
        time.sleep(0.5)
        js(send, "document.body.click()")
        time.sleep(1)
    log(f"To date set: {to_date}")

    # Click search
    js(send, """(function(){
        var btn = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:search');
        if(btn) btn.click();
        return 'ok';
    })()""")
    time.sleep(10)
    for i in range(6):
        info = json.loads(js(send, READ_DATA_JS))
        if info.get("rows"): break
        log(f"انتظار بيانات بعد البحث... ({i+1})"); time.sleep(5)

if not info.get("rows"):
    log("ERROR: لا توجد بيانات"); ws.close(); sys.exit(1)

total = info["total"]; pages = info["pages"]
log(f"بيانات: {total} سجل، {pages} صفحة")

# Collect all pages
all_rows = list(info["rows"])
page_num = 1
streak = 0
log(f"جمع: صفحة 1/{pages} ({len(all_rows)} صف)")

while page_num < pages:
    next_page = page_num + 1
    r = json.loads(js(send, next_page_js(next_page)))
    if "error" in r:
        streak += 1
        if streak > 5: log(f"توقف: 5 أخطاء"); break
        time.sleep(3); continue
    time.sleep(2)
    info = json.loads(js(send, READ_DATA_JS))
    rows = info.get("rows",[])
    if not rows:
        streak += 1
        if streak > 5: log(f"توقف: 5 صفحات فارغة"); break
    else:
        streak = 0; all_rows.extend(rows)
    page_num += 1
    if page_num % 50 == 0: log(f"صفحة {page_num}/{pages} ({len(all_rows)} صف)")

log(f"تم جمع {len(all_rows)} صف من {total}")

if len(all_rows) < 1:
    log(f"ERROR: لا توجد بيانات على الإطلاق"); sys.exit(1)

n_cols = len(all_rows[0])
df = pd.DataFrame(all_rows, columns=COLS[:n_cols])
log(f"DataFrame: {len(df)} صف، {len(df.columns)} عمود")

df.to_excel("data.xlsx", index=False, engine="openpyxl")
log(f"حفظ data.xlsx ({os.path.getsize('data.xlsx')//1024} KB)")

os.chdir(PROJECT_DIR)
subprocess.run(["git","add","-A"], check=True, capture_output=True)
r = subprocess.run(["git","commit","-m",f"update data {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
                    capture_output=True, text=True)
if r.returncode == 0:
    p = subprocess.run(["git","push","origin","main"], capture_output=True, text=True, timeout=60)
    if p.returncode == 0: log("تم الرفع لـ GitHub")
    else: log(f"خطأ الرفع: {p.stderr[:200]}")
else:
    log("لا توجد تغييرات")

ws.close()
log("=== انتهت العملية بنجاح ===")
