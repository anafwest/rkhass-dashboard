# -*- coding: utf-8 -*-
"""ups_sync_fast.py — سحب UPS موازي سريع (التحقق من كل الحالات + إضافة الجديد).

البوابة تُظهر 10 صفوف فقط بالصفحة (154 صفحة) بلا فلتر ترقيم؛
نمر على الصفحات بالتوازي عبر عدة تبويبات (الافتراضي 5) فتنزل إلى ~دقيقتين.
يقرأ آخر حالة لكل طلب، يدمج (إضافة/تحديث) ثم يحفظ ويرفع لـ GitHub.
"""
import ssl, os, urllib3, time, json, sys, threading, subprocess, urllib.parse
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
import websocket, urllib.request, pandas as pd
from datetime import datetime

PORT = 9222
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE_DIR = r"C:\Users\anaf\ScraperProfile"
PAGE_URL = "https://ups-backoffice.alriyadh.gov.sa/ar/building-license-department?activeTab=requests"
COLS = ["رقم الطلب","رقم الرخصة","تاريخ الطلب","اسم المستفيد","الحي","حالة الطلب","نوع الخدمة"]
WORKERS = int(os.environ.get("UPS_WORKERS", "5"))
STAGGER = 3.0
LOG_FILE = "ups_sync_log.txt"

def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)

def get_tabs():
    try: return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=5).read())
    except: return []

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "daily-report-automation", ".env")

def read_creds():
    d = {}
    try:
        for ln in open(ENV_FILE, encoding="utf-8", errors="ignore").read().splitlines():
            if "=" in ln and not ln.strip().startswith("#"):
                k, v = ln.split("=", 1)
                d[k.strip()] = v.strip()
    except Exception:
        return None, None
    u = d.get("CRM_USERNAME") or d.get("SSO_USERNAME")
    pw = d.get("CRM_PASSWORD")
    return u, pw

def is_login(send):
    return bool(js(send, "!!document.getElementById('userNameInput')")) or \
           ("adfs" in (js(send, "document.location.href") or ""))

def do_login(send, u, pw):
    log("شاشة دخول UPS — إدخال بيانات ADFS تلقائياً...")
    for fid, val in (("userNameInput", u), ("passwordInput", pw)):
        expr = ("var e=document.getElementById('" + fid + "');if(!e)return false;"
                "var s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;"
                "s.call(e," + json.dumps(val) + ");"
                "e.dispatchEvent(new Event('input',{bubbles:true}));"
                "e.dispatchEvent(new Event('change',{bubbles:true}));true")
        js(send, expr)
    js(send, "(function(){var k=document.getElementById('kmsiInput');if(k&&k.checked===false)k.click();" \
             "var b=document.getElementById('submitButton');if(b){b.click();return true;}return false;})()")
    return True

def ensure_ready(send, timeout=70):
    """التأكد من الوصول لقائمة الطلبات (تسجيل دخول تلقائي عند الحاجة)."""
    send("Page.navigate", {"url": PAGE_URL})
    t0 = time.time()
    logged_once = False
    while time.time() - t0 < timeout:
        info = read_rows(send)
        if info.get("total") and info.get("page") >= 1 and info.get("rows"):
            return info
        if is_login(send) and not logged_once:
            u, pw = read_creds()
            if u and pw:
                do_login(send, u, pw)
                logged_once = True
            else:
                log("لا توجد بيانات ADFS في " + ENV_FILE)
                return None
        time.sleep(3)
    return read_rows(send)

def connect_ws(url):
    ws = websocket.create_connection(url, timeout=30)
    _id = [0]
    def send(m, p=None):
        _id[0] += 1
        ws.send(json.dumps({"id": _id[0], "method": m, "params": p or {}}))
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == _id[0]: return r.get("result", {})
    return ws, send

def js(send, expr):
    r = send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    v = r.get("result", {})
    if "value" in v: return v["value"]
    return "ERR:" + v.get("description", "")

def new_tab():
    try:
        req = urllib.request.Request("http://127.0.0.1:%d/json/new?%s" % (PORT, urllib.parse.quote(PAGE_URL, safe="")), method="PUT")
        nb = json.loads(urllib.request.urlopen(req, timeout=10).read())
        return nb
    except Exception:
        return None

READ_JS = """(function(){
    var result = {page:0, total:0, rows:[]};
    var txt = document.body.innerText;
    var m = txt.match(/الصفحة (\\d+) من (\\d+)/);
    if(m){ result.page = parseInt(m[1]); result.total = parseInt(m[2]); }
    var trs = document.querySelectorAll('table tbody tr');
    trs.forEach(function(tr){
        var tds = tr.querySelectorAll('td');
        if(tds.length >= 7){
            var row = [tds[0].innerText.trim(),tds[1].innerText.trim(),tds[2].innerText.trim(),
                       tds[3].innerText.trim(),tds[4].innerText.trim(),tds[5].innerText.trim(),
                       tds[6].innerText.trim()];
            if(row[0] && row[0].length > 3) result.rows.push(row);
        }
    });
    return JSON.stringify(result);
})()"""

def read_rows(send):
    try:
        return json.loads(js(send, READ_JS))
    except Exception:
        return {"page": 0, "total": 0, "rows": []}

def nav_page(send, page, limit=18):
    send("Page.navigate", {"url": PAGE_URL + (f"&page={page}" if page > 1 else "")})
    res = {"page": 0, "rows": []}
    for i in range(limit):
        res = read_rows(send)
        if res.get("page") == page and res.get("rows"):
            return res, True
        time.sleep(2)
    return res, False

def worker(wid, pages, out):
    time.sleep(STAGGER * wid)
    tab = new_tab()
    if not tab:
        log(f"عامل {wid+1}: تعذّر إنشاء تبويب")
        out[wid] = 0
        return
    ws, send = connect_ws(tab["webSocketDebuggerUrl"])
    time.sleep(5)
    got = 0
    for p in pages:
        ok = False
        for attempt in range(2):
            res, ok = nav_page(send, p)
            if ok:
                rows = res["rows"]
                got += len(rows)
                with out_lock:
                    for r in rows:
                        if len(r) >= 6 and str(r[0]):
                            current[str(r[0])] = r
                break
            time.sleep(2)
        if not ok and attempt:
            log(f"عامل {wid+1}: صفحة {p} فارغة مرتين")
    log(f"عامل {wid+1}: أنهى {len(pages)} صفحة ({got} صف)")
    out[wid] = got
    try: send("Page.close"); ws.close()
    except Exception: pass

def load_base():
    if not os.path.exists("ups_requests.xlsx"):
        return {}, set()
    df = pd.read_excel("ups_requests.xlsx", dtype=str).fillna("")
    base = {}
    for _, r in df.iterrows():
        k = str(r["رقم الطلب"])
        base[k] = r.to_dict()
    return base, set(base.keys())

def main():
    lockf = "ups_sync.lock"
    if os.path.exists(lockf):
        log("مثال آخر يعمل — خروج")
        return 0
    open(lockf, "w").close()
    t_all = time.time()
    try:
        log("=" * 60)
        log("سحب UPS موازي (فحص كل الحالات + الجديد)")

        base, base_keys = load_base()
        log(f"قاعدة: {len(base)} سجل")

        tabs = [t for t in get_tabs() if t.get("type") == "page" and "ups-backoffice" in t.get("url", "")]
        if not tabs:
            subprocess.Popen([CHROME_PATH, f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
                              "--no-first-run", "--start-minimized", f"--user-data-dir={PROFILE_DIR}", PAGE_URL])
            for _ in range(25):
                time.sleep(2)
                tabs = [t for t in get_tabs() if t.get("type") == "page" and "ups-backoffice" in t.get("url", "")]
                if tabs: break
        if not tabs:
            log("FATAL: لا وصول للبوابة (تسجيل دخول؟)")
            return 1

        # تحديد إجمالي الصفحات من تبويب موجود (مع دخول تلقائي عند الحاجة)
        ws, send = connect_ws(tabs[0]["webSocketDebuggerUrl"])
        info = ensure_ready(send)
        if not info or not info.get("total"):
            log("FATAL: لم نصل لقائمة الطلبات — يلزم دخول يدوي")
            return 2
        total_pages = info.get("total", 0) or 1
        log(f"إجمالي الصفحات: {total_pages}")
        try: ws.close()
        except Exception: pass

        pages = list(range(1, total_pages + 1))
        chunks = [[] for _ in range(WORKERS)]
        for i, p in enumerate(pages):
            chunks[i % WORKERS].append(p)

        global current, out_lock
        current = {}
        out_lock = threading.Lock()
        out = [0] * WORKERS
        t0 = time.time()
        threads = [threading.Thread(target=worker, args=(i, chunks[i], out)) for i in range(WORKERS)]
        for th in threads: th.start()
        for th in threads: th.join()
        log(f"المرور الموازي: {int((time.time()-t0)//60)}د {int((time.time()-t0)%60)}ث — {len(current)} صف")

        new_k = [k for k in current if k not in base_keys]
        upd_k = [k for k in current if k in base_keys and base[k].get("حالة الطلب") != current[k][5]]
        log(f"جديدة: {len(new_k)} | تحديث حالة: {len(upd_k)}")

        cols = COLS
        rows = [current[k] for k in sorted(current)]
        df = pd.DataFrame(rows, columns=cols)
        try:
            os.replace("ups_requests.xlsx", "ups_prev.xlsx")
        except Exception:
            pass
        df.to_excel("ups_requests.xlsx", index=False, engine="openpyxl")
        log(f"حفظ ups_requests.xlsx ({len(df)} صف) في {int((time.time()-t_all)//60)}د {int((time.time()-t_all)%60)}ث")

        subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
        r = subprocess.run(["git", "commit", "-m", f"update ups data {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
                           capture_output=True, text=True)
        p = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True, timeout=120)
        log("تم الرفع لـ GitHub" if p.returncode == 0 else f"خطأ الرفع: {p.stderr[:150]}")
    finally:
        try:
            os.remove(lockf)
        except Exception:
            pass

if __name__ == "__main__":
    sys.exit(main())