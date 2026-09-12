# -*- coding: utf-8 -*-
"""سحب بيانات BLS (شاشة 8510) ورفعها لـ GitHub.

إصدار مُعجَّل:
- التنقل لشاشة 8510 عبر البحث العام (myInput) مع حتمال النقر المباشر بالمعرفات.
- ضبط تواريخ حقيقي عبر كتابة CDP (وليس مجرد تعيين value).
- ترقيم سريع (استطلاع 0.3 ثانية + قفز مباشر بصفحة nb_in_pg).
- موازاة التجميع على عدة تبويبات Chrome (--tabs N، الافتراضي 4).
"""
import ssl, os, urllib3, time, json, sys, glob, re, threading, subprocess, urllib.parse as up
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
import websocket, urllib.request, pandas as pd
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE_DIR = r"C:\Users\anaf\ScraperProfile"
PORT = 9222
BLS_URL = "https://app.alriyadh.gov.sa/BLS/faces/home"
SSO_URL = "https://app.alriyadh.gov.sa/SSO/loginApi"
BLS_SSO_URL = "https://app.alriyadh.gov.sa/BLS/loginApi"
COLS = ["طلب الخدمة","السنة","نوع الخدمة","وصف المرحلة","الجهة","تاريخ الطلب",
        "تاريخ الطلب ميلادي","رقم الرخصة","سنة الرخصة","نوع الهوية","المالك",
        "رقم الهوية","تاريخ المراجعة","تاريخ المراجعة ميلادي","رقم الطلب"]
FROM_DATE = "1447/04/13"
TO_DATE = "1448/12/29"
TABS = int(os.environ.get("BLS_TABS", "4"))
MAX_WORK_PAGES = int(os.environ["BLS_MAX_WORK_PAGES"]) if os.environ.get("BLS_MAX_WORK_PAGES") else None
TEST_ONLY = bool(os.environ.get("BLS_TEST_ONLY"))

FROM_FIELD = "pt1:cBodFDC:r1:0:masteraTable:Fromdate::content"
TO_FIELD = "pt1:cBodFDC:r1:0:masteraTable:Todate::content"
SEARCH_BTN = "pt1:cBodFDC:r1:0:masteraTable:search"
RNG_ID = "pt1:cBodFDC:r1:0:masteraTable:t1::nb_rng"
NX_ID = "pt1:cBodFDC:r1:0:masteraTable:t1::nb_nx"
PAGE_INPUT = "pt1:cBodFDC:r1:0:masteraTable:t1::nb_in_pg"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with open("scraper_log.txt","a",encoding="utf-8") as f: f.write(line+"\n")
    print(line, flush=True)

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
        for attempt in range(3):
            try:
                ws.send(json.dumps(msg))
                while True:
                    r = json.loads(ws.recv())
                    if r.get("id") == _id[0]: return r.get("result",{})
            except Exception:
                time.sleep(1)
        return {}
    return ws, send

def js(send, expr, ap=False):
    r = send("Runtime.evaluate",{"expression":expr,"returnByValue":True,"awaitPromise":ap})
    v = r.get("result",{})
    if "value" in v: return v["value"]
    if v.get("subtype")=="error": return "ERR:"+v.get("description","")
    return v

def kill_chrome():
    """قتل عمليات Chrome الخاصة ببروفايل السحب فقط (لا يمس متصفح المستخدم العادي)."""
    try:
        r = subprocess.run(
            ["powershell","-NoProfile","-Command",
             "Get-CimInstance Win32_Process -Filter \\\"Name='chrome.exe'\\\" | "
             "Where-Object { $_.CommandLine -like '*ScraperProfile*' } | "
             "ForEach-Object { $_.ProcessId }"],
            capture_output=True, text=True, timeout=30)
        ids = [int(x) for x in r.stdout.split() if x.strip().isdigit()]
        for pid in ids:
            subprocess.run(["taskkill","/F","/PID",str(pid)], capture_output=True)
        time.sleep(3)
    except Exception:
        pass

def start_chrome():
    kill_chrome()
    subprocess.Popen([CHROME_PATH,f"--remote-debugging-port={PORT}","--remote-allow-origins=*",
        "--no-first-run","--disable-popup-blocking",
        f"--user-data-dir={PROFILE_DIR}",BLS_SSO_URL])
    log("انتظار Chrome...")
    for i in range(20):
        time.sleep(2)
        if get_tabs(): return True
    return False

# ---------------- قراءة الجدول ----------------
READ_DATA_JS = """(function(){
    var table = null;
    var tables = document.querySelectorAll('table');
    tables.forEach(function(t){
        if(t.className && t.className.indexOf('af_table_data-table') >= 0){
            if(!table || t.rows.length > table.rows.length) table = t;
        }
    });
    if(!table) return JSON.stringify({rows:[],total:0,pages:0,page:0,perPage:0});
    var rows = [];
    var bodyRows = (table.tBodies && table.tBodies.length) ? table.tBodies[0].rows : table.rows;
    for(var r=0; r<bodyRows.length; r++){
        var tds = bodyRows[r].querySelectorAll('td');
        var row = [], hasData = false;
        tds.forEach(function(td){
            var txt = (td.innerText||'').trim();
            row.push(txt);
            if(txt.length > 0) hasData = true;
        });
        if(hasData && row.length >= 10) rows.push(row);
    }
    var rng = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_rng');
    var total = 0, perPage = rows.length, pages = 1, page = 1, start = 0;
    if(rng){
        var txt = rng.innerText;
        var m = txt.match(/\\(([\\d,]+)-(\\d[\\d,]+)\\s+من\\s+(\\d[\\d,]+)/);
        if(m){
            var start = parseInt(m[1].replace(/,/g,''));
            var end = parseInt(m[2].replace(/,/g,''));
            total = parseInt(m[3].replace(/,/g,''));
            perPage = end - start + 1;
            page = Math.floor(start / perPage) + 1;
            pages = Math.ceil(total / perPage);
        }
    }
    if(!total){
        var text = document.body.innerText;
        var m2 = text.match(/\\(([\\d,]+)-(\\d[\\d,]+)\\s+من\\s+(\\d[\\d,]+)/);
        var m3 = text.match(/العدد\\s*(\\d[\\d,]*)/);
        if(m2){
            total = parseInt(m2[3].replace(/,/g,''));
            var start = parseInt(m2[1].replace(/,/g,''));
            var end = parseInt(m2[2].replace(/,/g,''));
            perPage = end - start + 1;
            page = Math.floor(start / perPage) + 1;
            pages = Math.ceil(total / perPage);
        } else if(m3){
            total = parseInt(m3[1].replace(/,/g,''));
            pages = Math.ceil(total / perPage);
        }
    }
    if(!total) total = rows.length;
    return JSON.stringify({rows:rows,total:total,pages:pages,page:page,perPage:perPage,start:start});
})()"""

def read_info(send):
    try:
        return json.loads(js(send, READ_DATA_JS))
    except Exception:
        return {"rows":[],"total":0,"pages":0,"page":0,"perPage":0}

# ---------------- date / search ----------------
def type_into(send, fid, value):
    """كتابة حقيقية عبر CDP: حرق الحقل بمفاتيح Backspace (يكسر نموذج ADF)
    ثم Ctrl+A ثم كتابة القيمة — يضمن الاستبدال على حقل حي بدون إلصاق."""
    for attempt in range(3):
        js(send, "(function(){var e=document.getElementById('" + fid + "');if(e)e.focus();})()")
        time.sleep(0.1)
        for _ in range(16):
            send("Input.dispatchKeyEvent", {"type":"keyDown","key":"Backspace","code":"Backspace","windowsVirtualKeyCode":8})
            send("Input.dispatchKeyEvent", {"type":"keyUp","key":"Backspace","code":"Backspace","windowsVirtualKeyCode":8})
        time.sleep(0.15)
        send("Input.dispatchKeyEvent", {"type":"keyDown","modifiers":2,"key":"a","code":"KeyA","windowsVirtualKeyCode":65})
        send("Input.dispatchKeyEvent", {"type":"keyUp","modifiers":2,"key":"a","code":"KeyA","windowsVirtualKeyCode":65})
        time.sleep(0.1)
        send("Input.insertText", {"text": value})
        time.sleep(0.2)
        js(send, "(function(){var e=document.getElementById('" + fid + "');"
                 "e.dispatchEvent(new Event('change',{bubbles:true}));e.blur();})()")
        time.sleep(0.4)
        got = js(send, "var e=document.getElementById('" + fid + "'); e ? e.value : ''")
        if got == value:
            return True
        log(f"  إعادة محاولة ضبط {fid[-18:]} = {value}: القراءة الفعلية '{got}'")
    return False

def ensure_dates(send):
    ok = True
    for name, fid, val in (("من", FROM_FIELD, FROM_DATE), ("إلى", TO_FIELD, TO_DATE)):
        cur = js(send, "var e=document.getElementById('" + fid + "'); e ? e.value : ''")
        if str(cur).strip() == val:
            log(f"تاريخ {name} جاهز: {val}")
            continue
        ok = type_into(send, fid, val) and ok
        log(f"ضبط تاريخ {name} = {val}: {ok}")
    return ok

def js_true(send, expr):
    v = js(send, expr)
    return v is True or v == 1 or str(v).strip().lower() == "true"

def has_form(send):
    return js_true(send, "!!document.getElementById('" + FROM_FIELD + "')")

def click_search(send):
    js(send, "(function(){var b=document.getElementById('" + SEARCH_BTN + "');"
             "if(b){b.click();return 'ok';}return 'nf';})()")

# ---------------- navigation to BLS8510 ----------------
SHOW_CHAIN_JS = "(function(sel){var e=document.querySelector(sel);if(!e)return 'missing';" \
    "var n=e;for(var i=0;i<8&&n;i++){n.style.setProperty('display','block','important');" \
    "n.style.setProperty('visibility','visible','important');n.style.setProperty('opacity','1','important');" \
    "n.style.setProperty('max-height','none','important');n=n.parentElement;}return 'ok';})"

def myinput_open_8510(send):
    """فتح الشاشة عبر البحث العام في شاشات النظام (يعمل حتى لو كانت القائمة مطوية)."""
    if not js_true(send, "!!document.getElementById('myInput')"):
        return False
    js(send, "(function(){var e=document.getElementById('myInput');e.focus();})()")
    send("Input.dispatchKeyEvent", {"type":"keyDown","modifiers":2,"key":"a","code":"KeyA","windowsVirtualKeyCode":65})
    send("Input.dispatchKeyEvent", {"type":"keyUp","modifiers":2,"key":"a","code":"KeyA","windowsVirtualKeyCode":65})
    send("Input.insertText", {"text": "8510"})
    t0 = time.time()
    while time.time() - t0 < 8:
        if js_true(send, "(function(){var a=document.getElementById('pt1:SearchLi8510');" \
                         "return !!a&&a.offsetParent!==null;})()"):
            break
        time.sleep(0.5)
    js(send, SHOW_CHAIN_JS + "('#pt1:SearchLi8510')")
    js(send, "(function(){var a=document.getElementById('pt1:SearchLi8510');" \
             "if(a){a.click();return 'ok';}return 'nf';})()")
    return wait_form(send, 20)

def find_clickable(send, pattern):
    r = js(send, "(function(){var cands=[];"
          "document.querySelectorAll('a,span,div,td,li,h4,h5').forEach(function(e){"
          "var t=(e.innerText||'').replace(/\\s+/g,' ').trim();var g=e.getBoundingClientRect();"
          "if(new RegExp('" + pattern + "','i').test(t)&&t.length<120&&g.width>0&&g.height>0&&g.x>=0&&g.y>=0){"
          "cands.push({e:e,w:g.width,h:g.height,x:g.x+g.width/2,y:g.y+g.height/2,t:t.slice(0,60)});}});"
          "if(!cands.length)return 'nf';"
          "cands.sort(function(a,b){return (a.e.tagName=='A'?0:1)-(b.e.tagName=='A'?0:1);});"
          "var varAs=cands.filter(function(c){return c.e.tagName=='A';});"
          "var pick=varAs.length?varAs[varAs.length-1]:cands[cands.length-1];"
          "if(pick.e.click){pick.e.click();}return JSON.stringify({x:pick.x,y:pick.y,t:pick.t});})()")
    if isinstance(r, str) and r == 'nf':
        return None
    try:
        return json.loads(r)
    except Exception:
        return None

def wait_form(send, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if has_form(send): return True
        time.sleep(0.5)
    return has_form(send)

def ensure_8510(send):
    """ضمان فتح شاشة 8510 (حقل استعلام جاهز) بأي وسيلة متاحة."""
    if wait_form(send, 5):
        log("شاشة BLS8510 مفتوحة مسبقاً")
        return True
    # البحث العام في شاشات النظام (يعمل حتى لو كانت القائمة مطوية)
    if myinput_open_8510(send):
        log("شاشة BLS8510 فُتحت عبر البحث العام")
        return True
    # إجبار إظهار القائمة ثم النقر المباشر
    for cid in ("pt1:SearchLi8510", "pt1:SearchLi8500", "pt1:j_idt19"):
        js(send, SHOW_CHAIN_JS + "('#" + cid + "')")
        js(send, "(function(){var e=document.getElementById('" + cid + "');"
                 "if(e){e.click();return 'ok';}return 'missing';})()")
        if wait_form(send, 15):
            log(f"شاشة BLS8510 فُتحت عبر القائمة ({cid})")
            return True
    # ملاذ أخير: التسلسل عبر القائمة الجانبية (أنماط مقيدة بالبداية)
    for pat, desc in (("^BLS\\s*8000\\b", "BLS8000"), ("^BLS\\s*8500\\b", "BLS8500"),
                      ("^BLS\\s*8510\\b", "BLS8510")):
        pos = find_clickable(send, pat)
        if pos:
            log(f"نقر: {desc}")
            if wait_form(send, 12): return True
    return wait_form(send, 15)

# ---------------- pagination ----------------
def rng_txt(send):
    return js(send, "(function(){var r=document.getElementById('" + RNG_ID + "');"
              "return r?r.innerText.replace(/\\s+/g,' ').trim():'nf';})()")

def start_num(s):
    try: return int(s.split('-')[0].strip().strip('('))
    except: return -1

def wait_search(send, timeout=15):
    t0 = time.time(); last = None
    while time.time() - t0 < timeout:
        info = read_info(send)
        last = info
        if info.get("rows") and info.get("perPage", 0) >= 5:
            return info
        time.sleep(0.5)
    return last

def jump_page(send, pg, perPage):
    for attempt in range(3):
        js(send, "(function(){var e=document.getElementById('" + PAGE_INPUT + "');"
                 "e.focus();e.value='" + str(pg) + "';"
                 "var ev=new KeyboardEvent('keydown',{bubbles:true,cancelable:true,keyCode:13,key:'Enter'});"
                 "e.dispatchEvent(ev);})()")
        t0 = time.time()
        while time.time() - t0 < 8:
            s = rng_txt(send)
            info = read_info(send)
            if info.get("page") == pg or start_num(s) == (pg - 1) * perPage + 1:
                return True
            time.sleep(0.3)
        log(f"  قفز صفحة {pg} لم يُؤكد (محاولة {attempt+1})")
    return False

def click_next(send):
    js(send, "(function(){var a=document.getElementById('" + NX_ID + "');"
             "if(a){a.click();return 'ok';}return 'nf';})()")

def wait_advance(send, from_start, timeout=8):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = rng_txt(send)
        n = start_num(s)
        if n > from_start:
            return read_info(send)
        time.sleep(0.25)
    return None

def collect_main(send, start_page, end_page, perPage):
    if end_page < start_page:
        return []
    rows_all = []
    if not jump_page(send, start_page, perPage):
        log(f"  تعذر القفز لبداية الشريحة {start_page}")
        return rows_all
    info = read_info(send)
    s0 = start_num(rng_txt(send))
    if s0 != (start_page - 1) * perPage + 1:
        log(f"  بداية الشريحة خاطئة: {s0} بدل {(start_page-1)*perPage+1}")
        return rows_all
    cur = start_page
    streak = 0
    while cur <= end_page:
        info = read_info(send)
        rows = info.get("rows", [])
        if rows:
            rows_all.extend(rows)
        if cur >= end_page:
            break
        click_next(send)
        info = wait_advance(send, cur * perPage, timeout=8)
        if not info:
            streak += 1
            log(f"  تقدم الصفحة {cur+1} لم يُؤكد ({streak})")
            if streak >= 4:
                log(f"  إلغاء الشريحة عند صفحة {cur}")
                return rows_all
            time.sleep(1)
            continue
        streak = 0
        cur += 1
        if MAX_WORK_PAGES and cur - start_page >= MAX_WORK_PAGES:
            break
    return rows_all

# ---------------- worker ----------------
def open_tab():
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?" + up.quote("about:blank", safe=''), method="PUT")
        return json.loads(urllib.request.urlopen(req, timeout=8).read())
    except Exception:
        return None

def worker(k, start_page, end_page, perPage, results):
    ws = None
    try:
        nb = open_tab()
        if not nb:
            log(f"عامل {k}: تعذر فتح تبويب")
            results[k] = ([], "no-tab"); return
        ws, send = connect_ws(nb["webSocketDebuggerUrl"])
        js(send, f"window.location.href='{BLS_URL}'")
        t0 = time.time()
        while time.time() - t0 < 25:
            if js(send, 'typeof AdfPage !== "undefined" ? "ok" : "wait"') == "ok":
                break
            time.sleep(2)
        # شاشة 8510 (جلسة ADF تحفظ الشاشة غالباً عبر النوافذ، مع بديل البحث العام)
        if not wait_form(send, 25):
            js(send, f"window.location.href='{BLS_SSO_URL}'")
            wait_form(send, 25)
        ensure_8510(send)
        if not has_form(send):
            log(f"عامل {k}: شاشة 8510 لم تُفتح")
            results[k] = ([], "8510-open"); return
        ensure_dates(send)
        click_search(send)
        info = wait_search(send, timeout=20)
        if not info.get("rows"):
            log(f"عامل {k}: البحث لم يُرجع بيانات")
            results[k] = ([], "search"); return
        pp = info.get("perPage", perPage) or perPage
        rows = collect_main(send, start_page, end_page, pp)
        log(f"عامل {k}: شريحة صفحات {start_page}-{end_page}: {len(rows)} صف")
        results[k] = (rows, "ok")
    except Exception as e:
        log(f"عامل {k}: خطأ {e}")
        results[k] = ([], str(e)[:120])
    finally:
        try: send("Page.close")
        except Exception: pass
        try: ws.close()
        except Exception: pass

# ---------------- main ----------------
def main():
    log("="*60)
    log("بدء السحب التلقائي (نسخة مُعجَّلة)")

    tabs = get_tabs()
    ws_url = None
    for t in tabs:
        u = t.get("url","")
        if t.get("type")=="page" and "BLS/faces" in u:
            ws_url = t.get("webSocketDebuggerUrl"); break
    if not ws_url:
        for t in tabs:
            u = t.get("url","")
            if t.get("type")=="page" and "BLS" in u and u != "about:blank":
                ws_url = t.get("webSocketDebuggerUrl"); break
    if not ws_url:
        log("لا يوجد تبويب BLS")
        if not start_chrome():
            log("FATAL: Chrome لم يبدأ"); sys.exit(1)
        time.sleep(20)
        tabs = get_tabs()
        for t in tabs:
            u = t.get("url","")
            if t.get("type")=="page" and "BLS" in u:
                ws_url = t.get("webSocketDebuggerUrl"); break
    if not ws_url:
        log("FATAL: لا تبويب BLS"); sys.exit(1)

    ws, send = connect_ws(ws_url)
    url = js(send, "document.location.href") or ""
    log(f"الرابط: {url[:80]}")
    if "login" in url.lower():
        js(send, f"window.location.href='{BLS_SSO_URL}'")
        time.sleep(15)
    t0 = time.time()
    while time.time() - t0 < 30:
        if js(send, 'typeof AdfPage !== "undefined" ? "ok" : "wait"') == "ok":
            break
        time.sleep(2)

    if not ensure_8510(send):
        log("ERROR: تعذر الوصول لشاشة BLS8510")
        try: ws.close()
        except Exception: pass
        sys.exit(1)

    ensure_dates(send)
    log("بحث...")
    click_search(send)
    info = wait_search(send, timeout=20)
    if not info.get("rows") or info.get("perPage", 0) < 5:
        log("ERROR: الجدول لم يكتمل بعد البحث")
        try: ws.close()
        except Exception: pass
        sys.exit(1)

    total = info["total"]; perPage = info["perPage"]
    pages = int(total / perPage) + (1 if total % perPage else 0)
    log(f"بيانات: {total} سجل، {pages} صفحة ({perPage} لكل صفحة)")
    if total > 20000:
        log(f"WARN: إجمالي {total} أكبر من المتوقع — فلتر التواريخ لم يُطبق على الأرجح")
        try: ws.close()
        except Exception: pass
        sys.exit(2)

    n_tabs = max(1, min(TABS, pages))
    # شرائح متساوية الحجم
    sizes = []
    base = pages // n_tabs; rem = pages % n_tabs
    start_p = 1
    for k in range(n_tabs):
        seg = base + (1 if k < rem else 0)
        sizes.append((start_p, start_p + seg - 1))
        start_p += seg

    results = {}
    threads = []
    log(f"توزيع {pages} صفحة على {n_tabs} عامل: {[(a,b) for a,b in sizes]}")
    for k, (a, b) in enumerate(sizes):
        if k == 0:
            # العامل الرئيسي: الشريحة الأولى مباشرة (البحث جاهز)
            th = threading.Thread(target=worker_main_slice, args=(k, a, b, perPage, ws, send, results))
        else:
            th = threading.Thread(target=worker, args=(k, a, b, perPage, results))
        th.daemon = True
        th.start()
        threads.append((k, th))
    for k, th in threads:
        th.join()

    # ترتيب وتجميع
    all_rows = []
    missing = []
    for k in range(n_tabs):
        rows, status = results.get(k, ([], "missing"))
        if rows:
            all_rows.extend(rows)
        if status != "ok":
            missing.append(k)

    # إعادة محاولة الشرائح الفاشلة تسلسلياً
    for k in missing:
        a, b = sizes[k]
        log(f"إعادة محاولة الشريحة {k} ({a}-{b}) تسلسلياً...")
        if not has_form(send): ensure_8510(send)
        ensure_dates(send); click_search(send)
        info = wait_search(send, timeout=20)
        if info.get("rows"):
            rows = collect_main(send, a, b, perPage)
            all_rows.extend(rows)
            log(f"استرجاع الشريحة {k}: {len(rows)} صف")

    # فحص الاكتمال الأساسي (عدم وجود تكرار مضاعف عبر الشرائح)
    seen = set()
    dedup = []
    for r in all_rows:
        key = tuple(r)
        if key in seen:
            continue
        seen.add(key); dedup.append(r)
    all_rows = dedup

    log(f"تم جمع {len(all_rows)} صف (متوقع ~{total})")
    if TEST_ONLY:
        log("=== وضع اختبار: بدون حفظ/رفع ===")
        try: ws.close()
        except Exception: pass
        return 0 if len(all_rows) > 0 else 1

    if len(all_rows) < total - 5:
        log(f"ERROR: الجمع ناقص {len(all_rows)} من أصل {total} — ستتم إعادة المحاولة")
        try: ws.close()
        except Exception: pass
        sys.exit(3)

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
        p = subprocess.run(["git","push","origin","main"], capture_output=True, text=True, timeout=120)
        if p.returncode == 0: log("تم الرفع لـ GitHub")
        else: log(f"خطأ الرفع: {p.stderr[:200]}")
    else:
        log("لا توجد تغييرات")

    ws.close()
    log("=== انتهت العملية بنجاح ===")
    return 0

def worker_main_slice(k, start_page, end_page, perPage, ws, send, results):
    try:
        rows = collect_main(send, start_page, end_page, perPage)
        log(f"عامل {k} (رئيسي): شريحة {start_page}-{end_page}: {len(rows)} صف")
        results[k] = (rows, "ok")
    except Exception as e:
        log(f"عامل {k} (رئيسي): خطأ {e}")
        results[k] = ([], str(e)[:120])

if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        log(f"خطأ عام: {e}")
        sys.exit(1)