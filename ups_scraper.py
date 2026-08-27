import ssl, os, urllib3, time, json, sys, re, subprocess
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
import websocket, urllib.request, pandas as pd

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)
PORT = 9222
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE_DIR = r"C:\Users\anaf\ScraperProfile"
BASE_URL = "https://ups-backoffice.alriyadh.gov.sa/ar/building-license-department?activeTab=requests"

COLS = ["رقم الطلب","رقم الرخصة","تاريخ الطلب","اسم المستفيد","الحي","حالة الطلب","نوع الخدمة"]

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with open("ups_scraper_log.txt","a",encoding="utf-8") as f: f.write(line+"\n")
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

READ_PAGE_JS = """(function(){
    var result = {page:0, total:0, rows:[]};
    var txt = document.body.innerText;
    var m = txt.match(/الصفحة (\\d+) من (\\d+)/);
    if(m){ result.page = parseInt(m[1]); result.total = parseInt(m[2]); }
    var trs = document.querySelectorAll('table tbody tr');
    trs.forEach(function(tr){
        var tds = tr.querySelectorAll('td');
        if(tds.length >= 7){
            var row = [
                (tds[0].innerText||'').trim(),
                (tds[1].innerText||'').trim(),
                (tds[2].innerText||'').trim(),
                (tds[3].innerText||'').trim(),
                (tds[4].innerText||'').trim(),
                (tds[5].innerText||'').trim(),
                (tds[6].innerText||'').trim()
            ];
            if(row[0] && row[0].length > 3) result.rows.push(row);
        }
    });
    return JSON.stringify(result);
})()"""

def go_to_page(send, page):
    js(send, f"window.location.href='/ar/building-license-department?activeTab=requests&page={page}'")

def wait_for_page(send, target):
    for i in range(14):
        info = json.loads(js(send, READ_PAGE_JS))
        cur = info.get("page", 0)
        if cur == target and info.get("rows"):
            return info
        if info.get("total") and info.get("page") != target:
            time.sleep(2)
        else:
            time.sleep(2)
    return info

# ============ MAIN ============
log("="*60)
log("بدء سحب UPS - طلبات رخص البناء")

tabs = get_tabs()
ws_url = None
u = ""
for t in tabs:
    u = t.get("url","")
    if t.get("type")=="page" and "ups-backoffice" in u:
        ws_url = t.get("webSocketDebuggerUrl"); break

if not ws_url:
    try:
        import urllib.parse
        req = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/json/new?{urllib.parse.quote(BASE_URL, safe='')}", method="PUT")
        nb = json.loads(urllib.request.urlopen(req, timeout=10).read())
        ws_url = nb.get("webSocketDebuggerUrl")
        log("أنشأتُ تبويباً جديداً لبوابة UPS")
    except Exception as e:
        log(f"تعذر إنشاء تبويب، تشغيل كروم جديد: {e}")
        subprocess.Popen([CHROME_PATH, f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
                          "--no-first-run", "--start-minimized", f"--user-data-dir={PROFILE_DIR}", BASE_URL])
        for i in range(20):
            time.sleep(2)
            for t in get_tabs():
                if t.get("type")=="page" and "ups-backoffice" in t.get("url",""):
                    ws_url = t.get("webSocketDebuggerUrl"); break
            if ws_url: break

if not ws_url:
    log("FATAL: لا يوجد تبويب للبوابة"); sys.exit(1)

ws, send = connect_ws(ws_url)

# Go to page 1 first
go_to_page(send, 1)
log("الانتقال لصفحة 1...")
info = wait_for_page(send, 1)
time.sleep(3)

total_pages = info.get("total", 0)
if not total_pages:
    info = json.loads(js(send, READ_PAGE_JS))
    total_pages = info.get("total", 0)
log(f"إجمالي الصفحات: {total_pages}")

all_rows = []
streak = 0
for page in range(1, total_pages + 1):
    if page > 1:
        go_to_page(send, page)
        info = wait_for_page(send, page)
    rows = info.get("rows", [])
    if rows:
        all_rows.extend(rows)
        streak = 0
    else:
        streak += 1
        if streak > 3:
            log(f"توقف: 3 صفحات فارغة عند صفحة {page}")
            break
    if page % 20 == 0 or page == total_pages:
        log(f"صفحة {page}/{total_pages} - إجمالي {len(all_rows)} صف")

log(f"تم جمع {len(all_rows)} صف")

if all_rows:
    df = pd.DataFrame(all_rows, columns=COLS)
    df.to_excel("ups_requests.xlsx", index=False, engine="openpyxl")
    log(f"حفظ ups_requests.xlsx ({os.path.getsize('ups_requests.xlsx')//1024} KB)")
else:
    log("ERROR: لا توجد بيانات")
    try: ws.close()
    except Exception: pass
    sys.exit(1)

ws.close()
log("=== انتهت عملية UPS ===")