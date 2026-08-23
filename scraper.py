import ssl, os, urllib3, time, json, sys, glob
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
import websocket
import urllib.request
import pandas as pd
import subprocess
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE_DIR = r"C:\Users\anaf\ScraperProfile"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with open("scraper_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)

def get_tabs():
    try:
        return json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read())
    except:
        return []

def ws_eval(ws, expr, cmd_id=1):
    msg = {"id": cmd_id, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}}
    ws.send(json.dumps(msg))
    while True:
        resp = json.loads(ws.recv())
        if resp.get("id") == cmd_id:
            val = resp.get("result", {}).get("result", {})
            return val.get("value", str(val))

def start_chrome():
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True)
    time.sleep(3)
    subprocess.Popen([
        CHROME_PATH, "--remote-debugging-port=9222", "--remote-allow-origins=*",
        "--user-data-dir=" + PROFILE_DIR, "--no-first-run",
        "https://app.alriyadh.gov.sa/SSO/loginApi"
    ])
    for i in range(20):
        time.sleep(2)
        if get_tabs():
            return True
    return False

def read_current_page(ws, cmd_id=100):
    result = ws_eval(ws, """
    (function() {
        var trs = document.querySelectorAll('tr');
        var rows = [];
        trs.forEach(function(tr) {
            var tds = tr.querySelectorAll('td');
            if (tds.length >= 10) {
                var rowData = [];
                var isEmpty = true;
                tds.forEach(function(td) {
                    var text = td.innerText?.trim() || '';
                    rowData.push(text);
                    if (text) isEmpty = false;
                });
                if (!isEmpty) rows.push(rowData);
            }
        });
        var tm = document.body.innerText.match(/\\(([\\d,]+)-(\\d[\\d,]*)\\s+من\\s+(\\d[\\d,]+)/);
        var totalElements = tm ? parseInt(tm[3].replace(/,/g, '')) : 0;
        var perPage = tm ? parseInt(tm[2].replace(/,/g, '')) - parseInt(tm[1].replace(/,/g, '')) + 1 : 5;
        var totalPages = totalElements > 0 ? Math.ceil(totalElements / perPage) : 0;
        return JSON.stringify({rows: rows, totalPages: totalPages, totalElements: totalElements, perPage: perPage});
    })()
    """, cmd_id)
    return json.loads(result)

def click_next_page(ws, cmd_id=200):
    result = ws_eval(ws, """
    (function() {
        var text = document.body.innerText;
        var m = text.match(/الصفحة\\s+([\\d,]+)\\s+من\\s+([\\d,]+)/);
        if (!m) return JSON.stringify({error: 'no page info'});
        var cur = parseInt(m[1].replace(/,/g, ''));
        var links = document.querySelectorAll('a');
        for (var link of links) {
            if (link.innerText?.trim() === String(cur + 1)) {
                link.click();
                return JSON.stringify({ok: true, nextPage: cur + 1});
            }
        }
        return JSON.stringify({error: 'link not found', currentPage: cur});
    })()
    """, cmd_id)
    return json.loads(result)

# ====================== MAIN ======================
log("=" * 60)
log("بدء السحب التلقائي الكامل")

tabs = get_tabs()
if not any("alriyadh" in t.get("url", "") for t in tabs):
    log("تشغيل Chrome...")
    if not start_chrome():
        log("ERROR: Chrome didn't start")
        os._exit(1)
    log("انتظار SSO...")
    time.sleep(25)

tabs = get_tabs()
ws_url = None
for t in tabs:
    if "alriyadh" in t.get("url", ""):
        ws_url = t.get("webSocketDebuggerUrl")
        break
if not ws_url:
    log("ERROR: لا يوجد تبويب بوابة")
    os._exit(1)

ws = websocket.create_connection(ws_url, timeout=60)
cmd = 1

url = ws_eval(ws, "document.location.href", cmd); cmd += 1
log(f"الرابط الحالي: {url[:150]}")

# Ensure we are on home page
if "home" not in url or "BLS" in url:
    log("الانتقال للرئيسية...")
    ws_eval(ws, "window.location.href = 'https://app.alriyadh.gov.sa/SSO/loginApi'", cmd); cmd += 1
    time.sleep(15)
    url = ws_eval(ws, "document.location.href", cmd); cmd += 1

if "home" not in url:
    time.sleep(10)
    url = ws_eval(ws, "document.location.href", cmd); cmd += 1

log(f"الرابط: {url[:150]}")

# Navigate to BLS: AJAX POST + document.write then navigate
log("فتح BLS عبر AJAX POST...")
ws_eval(ws, """
(function() {
    var form = document.getElementById('f1');
    if (!form) return 'no form';
    var params = new FormData(form);
    params.append('pt1:MenuButtonUBS', 'pt1:MenuButtonUBS');
    var xhr = new XMLHttpRequest();
    xhr.open('POST', form.action, false);
    xhr.send(params);
    if (xhr.status === 200) {
        document.open();
        document.write(xhr.responseText);
        document.close();
        return 'ok';
    }
    return 'error:' + xhr.status;
})()
""", cmd); cmd += 1

log("انتظار 3 ثوان ثم Navigate...")
time.sleep(3)

ws_eval(ws, "window.location.href = 'https://app.alriyadh.gov.sa/BLS/faces/home'", cmd); cmd += 1

log("انتظار تحميل BLS (20 ثانية)...")
time.sleep(20)

url = ws_eval(ws, "document.location.href", cmd); cmd += 1
log(f"الرابط: {url[:150]}")

# If we landed on login, try reload
if "login" in url.lower():
    log("وصلنا صفحة الدخول - إعادة تحميل...")
    ws_eval(ws, "location.reload()", cmd); cmd += 1
    time.sleep(15)
    url = ws_eval(ws, "document.location.href", cmd); cmd += 1
    log(f"الرابط بعد reload: {url[:150]}")

# Wait for data
log("انتظار تحميل البيانات...")
for attempt in range(5):
    info = read_current_page(ws, cmd)
    cmd += 10
    if info.get("rows"):
        break
    log(f"محاولة {attempt+1}: لا توجد بيانات بعد...")
    time.sleep(5)

if not info.get("rows"):
    log("ERROR: لا توجد بيانات بعد 5 محاولات")
    ws.close()
    os._exit(1)

total_elements = info.get("totalElements", 0)
per_page = info.get("perPage", 5)
total_pages = info.get("totalPages", 0)
log(f"إجمالي العناصر: {total_elements}, صفوف/صفحة: {per_page}, صفحات: {total_pages}")

# Collect all pages
all_rows = list(info.get("rows", []))
page_num = 1
empty_streak = 0

log(f"بدء جمع البيانات - صفحة 1/{total_pages} - {len(all_rows)} صف")

while page_num < total_pages:
    result = click_next_page(ws, cmd)
    cmd += 1

    if "error" in result:
        empty_streak += 1
        if empty_streak > 5:
            log(f"توقف: 5 أخطاء متتالية")
            break
        time.sleep(3)
        continue

    time.sleep(1.5)

    info = read_current_page(ws, cmd)
    cmd += 10

    rows = info.get("rows", [])
    if not rows:
        empty_streak += 1
        if empty_streak > 5:
            log(f"توقف: 5 صفحات فارغة")
            break
    else:
        empty_streak = 0
        all_rows.extend(rows)

    page_num += 1
    if page_num % 50 == 0:
        log(f"صفحة {page_num}/{total_pages} - {len(all_rows)} صف")
    elif page_num % 10 == 0:
        print(f"  {page_num}/{total_pages} ({len(all_rows)} rows)", end="\r")

log(f"\nتم جمع {len(all_rows)} صف من {total_elements} إجمالي")

# Process and push
if len(all_rows) > 100:
    columns = [
        "طلب الخدمة", "السنة", "نوع الخدمة", "وصف المرحلة", "الجهة",
        "تاريخ الطلب", "تاريخ الطلب ميلادي", "رقم الرخصة", "سنة الرخصة",
        "نوع الهوية", "المالك", "رقم الهوية", "تاريخ المراجعة",
        "تاريخ المراجعة ميلادي", "رقم الطلب"
    ]
    n_cols = len(all_rows[0])
    df = pd.DataFrame(all_rows, columns=columns[:n_cols])
    log(f"DataFrame: {len(df)} صف، {len(df.columns)} عمود")

    output = os.path.join(PROJECT_DIR, "data.xlsx")
    df.to_excel(output, index=False, engine='openpyxl')
    log(f"تم حفظ data.xlsx ({os.path.getsize(output) // 1024} KB)")

    os.chdir(PROJECT_DIR)
    subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
    commit_msg = f"تحديث البيانات - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    result = subprocess.run(["git", "commit", "-m", commit_msg], capture_output=True, text=True)
    if result.returncode == 0:
        push = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True, timeout=60)
        if push.returncode == 0:
            log("تم الرفع إلى GitHub بنجاح")
        else:
            log(f"خطأ الرفع: {push.stderr[:200]}")
    else:
        log("لا توجد تغييرات")
else:
    log(f"ERROR: بيانات غير كافية ({len(all_rows)} صف)")
    os._exit(1)

ws.close()
log("=== انتهت العملية بنجاح ===")
