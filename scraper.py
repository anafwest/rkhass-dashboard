import ssl, os, urllib3, time, json, sys, glob, re
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
BLS_SSO_URL = "https://app.alriyadh.gov.sa/BLS/loginApi"
COLS = ["طلب الخدمة","السنة","نوع الخدمة","وصف المرحلة","الجهة","تاريخ الطلب",
        "تاريخ الطلب ميلادي","رقم الرخصة","سنة الرخصة","نوع الهوية","المالك",
        "رقم الهوية","تاريخ المراجعة","تاريخ المراجعة ميلادي","رقم الطلب"]
FROM_DATE = "1447/04/13"
TO_DATE = "1448/12/29"

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

def cdp_click(send, x, y):
    send("Input.dispatchMouseEvent", {"type":"mousePressed","x":x,"y":y,"button":"left","clickCount":1})
    time.sleep(0.05)
    send("Input.dispatchMouseEvent", {"type":"mouseReleased","x":x,"y":y,"button":"left","clickCount":1})

def cdp_triple_click(send, x, y):
    send("Input.dispatchMouseEvent", {"type":"mousePressed","x":x,"y":y,"button":"left","clickCount":3})
    time.sleep(0.05)
    send("Input.dispatchMouseEvent", {"type":"mouseReleased","x":x,"y":y,"button":"left","clickCount":3})

def start_chrome():
    kill_chrome()
    subprocess.Popen([CHROME_PATH,f"--remote-debugging-port={PORT}","--remote-allow-origins=*",
        "--no-first-run","--disable-popup-blocking","--start-minimized",
        f"--user-data-dir={PROFILE_DIR}",BLS_SSO_URL])
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

def next_page_js(target):
    return f"""(function(){{
        var target = {target};
        var g = '٠١٢٣٤٥٦٧٨٩';
        var ar = target.toString().replace(/[0-9]/g, function(d){{ return g[+d]; }});
        var anchors = document.querySelectorAll('a');
        for(var i=0; i<anchors.length; i++){{
            var t = anchors[i].innerText.trim();
            if((t === String(target) || t === ar) && anchors[i].id && anchors[i].id.indexOf('nb_pg') >= 0){{
                anchors[i].click();
                return JSON.stringify({{ok:true, next:target}});
            }}
        }}
        var nextBtn = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_nx');
        if(nextBtn){{
            nextBtn.click();
            return JSON.stringify({{ok:true, next:target, method:'next_btn'}});
        }}
        for(var i=0; i<anchors.length; i++){{
            var t = anchors[i].innerText.trim();
            if((t === String(target) || t === ar) && anchors[i].href && anchors[i].href.indexOf('void') >= 0){{
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

FIRST_PAGE_JS = """(function(){
    var fr = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_fr');
    if(fr){ fr.click(); return JSON.stringify({ok:true, method:'fr'}); }
    var inp = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_in_pg');
    if(inp){
        inp.focus(); inp.value = '1';
        var ev = new Event('keydown', {bubbles:true, cancelable:true});
        ev.keyCode = 13; ev.key = 'Enter';
        inp.dispatchEvent(ev);
        return JSON.stringify({ok:true, method:'inp'});
    }
    return JSON.stringify({error:'first page control not found'});
})()"""

def set_date_field(send, fid, value):
    """ضبط حقل تاريخ مباشرة عبر تعيين قيمة العنصر DOM (لا يتراكم النص أبداً)."""
    for attempt in range(3):
        r = js(send, "(function(){var el=document.getElementById('" + fid + "');if(!el)return 'nf';"
                     "el.focus();el.removeAttribute('readonly');"
                     "var proto=Object.getPrototypeOf(el);"
                     "var setter=Object.getOwnPropertyDescriptor(proto,'value');"
                     "if(setter&&setter.set)setter.set.call(el,'" + value + "');else el.value='" + value + "';"
                     "el.dispatchEvent(new Event('input',{bubbles:true}));"
                     "el.dispatchEvent(new Event('change',{bubbles:true}));"
                     "el.blur();"
                     "return JSON.stringify({val:el.value});})()")
        if not r or r == 'nf':
            return False
        time.sleep(0.8)
        got = js(send, "var el=document.getElementById('" + fid + "'); el ? el.value : ''")
        if got == value:
            return True
        log(f"  إعادة محاولة ضبط {value}: القراءة الفعلية '{got}'")
    return False

def set_date_and_search(send, from_date, to_date):
    ok_f = set_date_field(send, 'pt1:cBodFDC:r1:0:masteraTable:Fromdate::content', from_date)
    ok_t = set_date_field(send, 'pt1:cBodFDC:r1:0:masteraTable:Todate::content', to_date)
    log(f"From date set ({from_date}): {ok_f} | To date set ({to_date}): {ok_t}")
    time.sleep(1)

    js(send, """(function(){
        var btn = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:search');
        if(btn) btn.click();
        return 'ok';
    })()""")
    time.sleep(6)
    return ok_f and ok_t

# ==================== MAIN ====================
log("="*60)
log("بدء السحب التلقائي")

tabs = get_tabs()
has_bls = any("BLS" in t.get("url","") and "login" not in t.get("url","").lower()
              for t in tabs if t.get("type")=="page")

if not has_bls:
    # لا نقتل Chrome حتى نُبقي جلسات التبويبات الأخرى (مثل UPS) حيّة —
    # نفتح تبويب BLS جديداً في نفس المتصفح بدلاً من ذلك.
    try:
        import urllib.parse as _up
        _nb = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{PORT}/json/new?{_up.quote('about:blank', safe='')}",
            method="PUT", timeout=8).read())
        log("فتح تبويب BLS جديد في نفس المتصفح")
    except Exception as e:
        log(f"تعذر فتح تبويب جديد، تشغيل Chrome: {e}")
        if not start_chrome():
            log("FATAL: Chrome didnt start"); sys.exit(1)
        log("انتظار Chrome+SSO..."); time.sleep(20)

for attempt in range(5):
    tabs = get_tabs()
    ws_url = None
    # نفضّل تبويب BLS حصراً (المسار BLS/faces) حتى لا نلتقط تبويب UPS
    for t in tabs:
        u = t.get("url","")
        if t.get("type")=="page" and "BLS/faces" in u:
            ws_url = t.get("webSocketDebuggerUrl"); break
    if not ws_url:
        # fallback: تبويب about:blank أنشأناه للتو على BLS — أو أي تبويب BLS
        for t in tabs:
            u = t.get("url","")
            if t.get("type")=="page" and "BLS" in u and u != "about:blank":
                ws_url = t.get("webSocketDebuggerUrl"); break
    if ws_url: break
    log(f"انتظار تبويب BLS... ({attempt+1})"); time.sleep(5)

if not ws_url:
    log("FATAL: no tab"); sys.exit(1)

ws, send = connect_ws(ws_url)
url = js(send, "document.location.href")

# التاريخ الهجري اليوم (تقويم أم القرى الرسمي) — نهاية الدورة تلقائية ومستمرة
try:
    hjs = ("(function(){var f=new Intl.DateTimeFormat('en-u-ca-islamic-umalqura',"
           "{year:'numeric',month:'2-digit',day:'2-digit',timeZone:'Asia/Riyadh'});"
           "var p={};f.formatToParts(new Date()).forEach(function(x){p[x.type]=x.value;});"
           "return p.year+'/'+p.month+'/'+p.day;})()")
    hijri_today = js(send, hjs)
    if hijri_today and re.match(r'^\d{4}/\d{2}/\d{2}$', str(hijri_today)):
        TO_DATE = str(hijri_today)
        log(f"نهاية الفترة = اليوم الواقعي: {TO_DATE}")
except Exception as e:
    log(f"تعذر حساب التاريخ الهجري اليوم ({e}) — سيبقى الثابت {TO_DATE}")
log(f"متصل: {url[:100]}")

for i in range(10):
    r = js(send, 'typeof AdfPage !== "undefined" ? "ok" : "wait"')
    if r == "ok": break
    log(f"انتظار ADF... ({i+1})"); time.sleep(3)

url = js(send, "document.location.href")
log(f"الرابط: {url[:100]}")

if "BLS" not in url:
    log("الانتقال لـ BLS...")
    js(send, f"window.location.href='{BLS_URL}'")
    time.sleep(15)
    url = js(send, "document.location.href")
    log(f"بعد الانتقال: {url[:100]}")

if "login" in url.lower():
    log("صفحة دخول - محاولة إعادة تأسيس الجلسة...")
    js(send, f"window.location.href='{BLS_SSO_URL}'")
    time.sleep(20)
    url = js(send, "document.location.href")
    log(f"BLS SSO retry: {url[:100]}")

if "login" in url.lower():
    log("ما نقدر نتجاوز صفحة الدخول"); ws.close(); sys.exit(1)

def find_clickable(send, pattern):
    # يرجع الإحداثيات (للسجل) وينقر العنصر مباشرة عبر element.click()
    # عناصر قوائم ADF تستجيب للنقر البرمجي المباشر أكثر موثوقية من محاكاة الماوس.

    # 1) نحاول النقر عبر .click() على عنصر مطابق قابل للرؤية
    r = js(send, "(function(){var cands=[];"
          "document.querySelectorAll('a,span,div,td,li,h4,h5').forEach(function(e){"
          "var t=(e.innerText||'').replace(/\\s+/g,' ').trim();var g=e.getBoundingClientRect();"
          "if(new RegExp('" + pattern + "','i').test(t)&&t.length<120&&g.width>0&&g.height>0&&g.x>=0&&g.y>=0){"
          "cands.push({e:e,w:g.width,h:g.height,x:g.x+g.width/2,y:g.y+g.height/2,t:t.slice(0,60)});}});"
          "if(!cands.length)return 'nf';"
          "cands.sort(function(a,b){return (a.w*a.h)-(b.w*b.h);});"
          "var pick=cands[0];"
          "if(pick.e.click){pick.e.click();}return JSON.stringify({x:pick.x,y:pick.y,t:pick.t});})()")
    if isinstance(r, str) and r == 'nf':
        return None
    try:
        return json.loads(r)
    except Exception:
        return None
    r = js(send, JS)
    if isinstance(r, str) and r != 'not found':
        try: return json.loads(r)
        except Exception: return None
    return None

def has_search_form_js(send):
    return js(send, "document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content') ? 'yes' : 'no'") == 'yes'

SCREEN_TITLES_JS = ("(function(){var o=[];document.querySelectorAll('h1,h2,h3,legend,strong,.af_panelWindow_title')"
                    ".forEach(function(e){var t=(e.innerText||'').trim();if(t&&t.length<80)o.push(t);});return o.join(' | ');})()")

def screen_is_8510(send):
    t = js(send, SCREEN_TITLES_JS) or ""
    return ("BLS8510" in t) and has_search_form_js(send)

def ensure_8510(send):
    """الوصول لشاشة BLS8510 مع التحقق من هويتها، مع إعادة محاولة بعد العودة للرئيسية."""
    for attempt in range(5):
        if screen_is_8510(send):
            log(f"شاشة BLS8510 مؤكدة (المحاولة {attempt+1})")
            return True
        if attempt > 0 or not has_search_form_js(send):
            url = js(send, "document.location.href") or ""
            if "home" not in url:
                js(send, f"window.location.href='{BLS_URL}'")
                time.sleep(8)
        steps = [
            ("BLS\\s*8000", "BLS8000"),
            ("BLS\\s*8500|الاستعلامات", "BLS8500"),
            ("BLS\\s*8510|استعلام عن بيانات الطلبات|استعلام", "BLS8510"),
        ]
        # نضغط كل مستوى وننتظر أطول (ADF يحتاج وقتاً لتوسيع القوائم الفرعية)
        for pat, desc in steps:
            if screen_is_8510(send):
                log("شاشة BLS8510 تحققت خلال التنقل"); return True
            pos = find_clickable(send, pat)
            if pos:
                log(f"نقر: {desc} -> {pos['t'][:40]}")
                time.sleep(4)
            else:
                log(f"عنصر غير موجود: {desc}")
        time.sleep(5)
        if screen_is_8510(send):
            log("شاشة BLS8510 مؤكدة بعد التنقل")
            return True
    log(f"النص الحالي: {(js(send, SCREEN_TITLES_JS) or '')[:100]}")
    return False

if not ensure_8510(send):
    log("ERROR: تعذر الوصول لشاشة BLS8510"); ws.close(); sys.exit(1)

log("ضبط التواريخ والبحث...")
ok_dates = set_date_and_search(send, FROM_DATE, TO_DATE)
if not ok_dates:
    log("WARN: لم يتأكد ضبط التواريخ — إعادة المحاولة مرة واحدة")
    time.sleep(3)
    ok_dates = set_date_and_search(send, FROM_DATE, TO_DATE)

for i in range(12):
    info = json.loads(js(send, READ_DATA_JS))
    if info.get("rows") and info.get("perPage", 0) >= 5:
        break
    log(f"انتظار اكتمال الجدول بعد البحث... ({i+1}, perPage={info.get('perPage')})"); time.sleep(5)

if not info.get("rows") or info.get("perPage", 0) < 5:
    log("ERROR: الجدول لم يكتمل (perPage<5)")
    # إعادة البحث لضمان قراءة سليمة
    set_date_and_search(send, FROM_DATE, TO_DATE)
    time.sleep(6)
    for i in range(8):
        info = json.loads(js(send, READ_DATA_JS))
        if info.get("rows") and info.get("perPage", 0) >= 5:
            break
        time.sleep(4)
    if not info.get("rows") or info.get("perPage", 0) < 5:
        log("ERROR: لا توجد بيانات كاملة بعد إعادة البحث"); ws.close(); sys.exit(1)

total = info["total"]; pages = info["pages"]
log(f"بيانات: {total} سجل، {pages} صفحة ({info['perPage']} لكل صفحة)")

# عدد الصفحات الحقيقي من شريط الترقيم (قد يختلف عن محسوب perPage)
try:
    cnt_txt = js(send, "(function(){var c=document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_cnt'); return c ? c.innerText : '';})()") or ""
    m = re.search(r'من\s+([0-9][0-9,]*)\b', cnt_txt.replace('\t', ' '))
    if m:
        pages_real = int(m.group(1).replace(',', ''))
        if pages_real != pages:
            log(f"تصحيح: عدد الصفحات الحقيقي {pages_real} بدلاً من {pages}")
            pages = pages_real
except Exception as e:
    log(f"تعذر قراءة عدد الصفحات الحقيقي: {e}")

# حارس: إذا فشل فلتر التواريخ وعادت كل الفترة (أكثر من المتوقع بكثير) نلغي التشغيل لإعادة المحاولة
if total > 20000:
    log(f"WARN: إجمالي {total} أكبر من المتوقع (~12000) — فلتر التواريخ لم يُطبق على الأرجح")
    ws.close(); sys.exit(2)

# التأكد من البدء من الصفحة الأولى (البحث قد يترك الجدول على آخر صفحة من جلسة سابقة)
for attempt_fp in range(4):
    r = json.loads(js(send, FIRST_PAGE_JS))
    time.sleep(0.8)
    chk = json.loads(js(send, READ_DATA_JS))
    if chk.get("page", 0) == 1:
        info = chk
        break
    log(f"  محاولة الوصول لصفحة 1 ({attempt_fp+1}): الصفحة الحالية {chk.get('page')}")
if info.get("page", 0) != 1:
    log("ERROR: تعذر الوصول للصفحة الأولى"); ws.close(); sys.exit(3)

all_rows = list(info["rows"])
page_num = info["page"]
last_start = info.get("start", 0)
streak = 0
log(f"جمع: صفحة {page_num}/{pages} ({len(all_rows)} صف)")

if os.environ.get("BLS_DIAG"):
    d = js(send, """(function(){
        var t = document.querySelector('table.af_table_data-table');
        var rng = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_rng');
        var cnt = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_cnt');
        var cols = (t && t.tHead && t.tHead.rows && t.tHead.rows[0]) ? t.tHead.rows[0].cells.length : -1;
        var body = (t && t.tBodies && t.tBodies[0]) ? t.tBodies[0].rows.length : -1;
        var out = {bodyRows: body, cols: cols,
                   rng: rng ? rng.innerText : '', cnt: cnt ? cnt.innerText : ''};
        var ls = [], pvv = [];
        document.querySelectorAll('*').forEach(function(e){
            if(e.id && e.id.indexOf('nb_ls')>=0) ls.push(e.id);
            if(e.id && e.id.indexOf('nb_pv')>=0) pvv.push(e.id);
        });
        out.lsIds = ls; out.pvIds = pvv;
        return JSON.stringify(out);
    })()""")
    log("DIAG: " + (d or "")[:1600])
    ws.close(); sys.exit(0)

while page_num < pages:
    next_page = page_num + 1
    r = json.loads(js(send, next_page_js(next_page)))
    if "error" in r:
        streak += 1
        if streak > 8: log(f"توقف: 8 أخطاء تنقل متتالية عند صفحة {next_page}"); break
        _curr = json.loads(js(send, READ_DATA_JS)).get("page", 0)
        if _curr > page_num:
            page_num = _curr - 1
            streak = 0
        time.sleep(3); continue
    # انتظار صبور لانتقال الجدول إلى الصفحة التالية (بدون إعادة النقر أثناء الانتقال)
    slow = 0
    time.sleep(0.8)
    info = json.loads(js(send, READ_DATA_JS))
    nxt_start = info.get("start", 0)
    while nxt_start <= last_start and slow < 15:
        time.sleep(1)
        info = json.loads(js(send, READ_DATA_JS))
        nxt_start = info.get("start", 0)
        slow += 1
    if nxt_start <= last_start:
        streak += 1
        if streak > 8:
            log(f"توقف: التقدم توقف عند صفحة {next_page} (بداية {nxt_start})")
            break
        _curr = json.loads(js(send, READ_DATA_JS)).get("page", 0)
        if _curr > page_num:
            page_num = _curr - 1
            streak = 0
        time.sleep(1)
        continue
    last_start = nxt_start
    rows = info.get("rows",[])
    if not rows:
        streak += 1
        if streak > 8: log(f"توقف: 8 صفحات فارغة"); break
    else:
        streak = 0; all_rows.extend(rows)
    page_num += 1
    if page_num % 500 == 0:
        log(f"صفحة {page_num}/{pages} ({len(all_rows)} صف) — حفظ نقطة تحقق")
        try:
            pd.DataFrame(all_rows, columns=COLS[:len(all_rows[0])]).to_excel("data.xlsx", index=False, engine="openpyxl")
        except Exception as e:
            log(f"فشل نقطة التحقق: {e}")

log(f"تم جمع {len(all_rows)} صف من {total}")

if total - len(all_rows) > 5:
    log(f"ERROR: الجمع ناقص {len(all_rows)} من أصل {total} — ستتم إعادة المحاولة")
    try: ws.close()
    except Exception: pass
    sys.exit(3)
else:
    log(f"اكتمل الجمع: {len(all_rows)} من {total} (فرق {total-len(all_rows)} صف ≈ صفحة، مقبول)")
    pages = page_num

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
