import ssl, os, urllib3, time, json, sys
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

def save(msg):
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

def ws_eval(ws, expr, cmd_id=1, timeout=30):
    msg = {"id": cmd_id, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}}
    ws.send(json.dumps(msg))
    start = time.time()
    while time.time() - start < timeout:
        ws.settimeout(max(5, timeout - (time.time() - start)))
        try:
            resp = json.loads(ws.recv())
            if resp.get("id") == cmd_id:
                val = resp.get("result", {}).get("result", {})
                return val.get("value", str(val))
        except:
            return "TIMEOUT"
    return "TIMEOUT"

def start_chrome():
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True)
    time.sleep(3)
    subprocess.Popen([
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "--remote-debugging-port=9222", "--remote-allow-origins=*",
        "--user-data-dir=C:\\Users\\anaf\\ScraperProfile", "--no-first-run",
        "https://app.alriyadh.gov.sa/SSO/loginApi"
    ])
    for i in range(20):
        time.sleep(2)
        if get_tabs():
            return True
    return False

save("=" * 60)
save("بدء السحب - fetch BLS من الصفحة الرئيسية (بدون تنقل)")

# Start Chrome fresh
tabs = get_tabs()
if not any("alriyadh" in t.get("url", "") for t in tabs):
    save("تشغيل Chrome...")
    if not start_chrome():
        save("ERROR: Chrome didn't start")
        os._exit(1)
    save("انتظار 45 ثانية للـ SSO الكامل...")
    time.sleep(45)

tabs = get_tabs()
ws_url = None
for t in tabs:
    if "alriyadh" in t.get("url", "") and "home" in t.get("url", ""):
        ws_url = t.get("webSocketDebuggerUrl")
        break
if not ws_url:
    for t in tabs:
        if "alriyadh" in t.get("url", ""):
            ws_url = t.get("webSocketDebuggerUrl")
            break
if not ws_url:
    save("ERROR: لا يوجد تبويب بوابة")
    os._exit(1)

ws = websocket.create_connection(ws_url, timeout=120)
cmd = 1

url = ws_eval(ws, "document.location.href", cmd, 10); cmd += 1
save(f"الرابط: {url[:150]}")

# Step 1: Fetch BLS page shell via fetch()
save("\n--- جلب صفحة BLS عبر fetch ---")
bls_html = ws_eval(ws, """
(async function() {
    try {
        var resp = await fetch('https://app.alriyadh.gov.sa/BLS/faces/home', {
            method: 'GET', credentials: 'same-origin'
        });
        var html = await resp.text();
        
        // Extract form action and hidden fields
        var parser = new DOMParser();
        var doc = parser.parseFromString(html, 'text/html');
        var form = doc.querySelector('form');
        var formAction = form ? form.action : 'no form';
        var formId = form ? form.id : '';
        
        // Extract all hidden inputs
        var hiddenInputs = {};
        if (form) {
            form.querySelectorAll('input').forEach(function(inp) {
                if (inp.name) hiddenInputs[inp.name] = inp.value || '';
            });
        }
        
        // Check for data
        var hasData = html.includes('من العناصر');
        var totalMatch = html.match(/(\\d[\\d,]*)\\s+من العناصر/);
        
        // Check for ADF scripts
        var hasAdf = html.includes('AdfPage');
        
        return JSON.stringify({
            status: resp.status,
            len: html.length,
            hasData: hasData,
            total: totalMatch ? totalMatch[1] : '0',
            formAction: formAction,
            formId: formId,
            hiddenInputCount: Object.keys(hiddenInputs).length,
            hiddenInputSample: Object.entries(hiddenInputs).slice(0, 10),
            hasAdf: hasAdf,
            hasLogin: html.includes('/login')
        });
    } catch(e) { return JSON.stringify({error: e.message}); }
})()
""", cmd, 30); cmd += 1
bls_data = json.loads(bls_html)
save(f"صفحة BLS: len={bls_data.get('len')}, hasData={bls_data.get('hasData')}, total={bls_data.get('total')}")
save(f"Login: {bls_data.get('hasLogin')}, ADF: {bls_data.get('hasAdf')}")
save(f"Form: id={bls_data.get('formId')}, action={bls_data.get('formAction','')[:100]}")
save(f"Hidden inputs: {bls_data.get('hiddenInputCount')}")
if bls_data.get('hiddenInputSample'):
    for k, v in bls_data.get('hiddenInputSample', []):
        save(f"  {k} = {v[:50]}")

# Step 2: If we have the form, try to POST to it to get data table
if bls_data.get('formId') or bls_data.get('hiddenInputCount', 0) > 0:
    save("\n--- محاولة POST لجلب بيانات الجدول ---")
    post_result = ws_eval(ws, """
    (async function() {
        try {
            // First GET to get form and session
            var resp1 = await fetch('https://app.alriyadh.gov.sa/BLS/faces/home', {
                method: 'GET', credentials: 'same-origin'
            });
            var html1 = await resp1.text();
            var parser = new DOMParser();
            var doc = parser.parseFromString(html1, 'text/html');
            var form = doc.querySelector('form');
            if (!form) return JSON.stringify({error: 'no form in BLS page'});
            
            // Build form data from the page's form
            var fd = new URLSearchParams();
            form.querySelectorAll('input, select, textarea').forEach(function(inp) {
                if (inp.name) fd.append(inp.name, inp.value || '');
            });
            
            // POST to the BLS form action
            var postUrl = 'https://app.alriyadh.gov.sa/BLS' + form.action.replace(/^.*BLS/, '');
            var resp2 = await fetch(postUrl, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: fd.toString()
            });
            var html2 = await resp2.text();
            var hasData = html2.includes('من العناصر');
            var totalMatch = html2.match(/(\\d[\\d,]*)\\s+من العناصر/);
            
            return JSON.stringify({
                status: resp2.status,
                url: resp2.url,
                len: html2.length,
                hasData: hasData,
                total: totalMatch ? totalMatch[1] : '0',
                hasTable: html2.includes('<table'),
                preview: html2.substring(0, 500)
            });
        } catch(e) { return JSON.stringify({error: e.message}); }
    })()
    """, cmd, 30); cmd += 1
    post_data = json.loads(post_result)
    save(f"POST result: len={post_data.get('len')}, hasData={post_data.get('hasData')}, total={post_data.get('total')}")
    save(f"URL: {post_data.get('url','')[:100]}")
    save(f"Has table: {post_data.get('hasTable')}")
    if post_data.get('hasData'):
        save("✓ البيانات موجودة في POST response!")

ws.close()
save("\n=== انتهى ===")
