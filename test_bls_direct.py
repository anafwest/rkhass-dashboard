"""
Test: Navigate Chrome directly to BLS/loginApi for Windows SSO
Then navigate through: BLS home → BLS8510 → read data
"""
import ssl, os, urllib3, time, json, sys, subprocess
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
import websocket

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = r"C:\Users\anaf\ScraperProfile"
DEBUG_PORT = 9225

def kill_chrome():
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
    time.sleep(2)

def launch_chrome(url):
    subprocess.Popen([
        CHROME,
        f"--remote-debugging-port={DEBUG_PORT}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--disable-popup-blocking",
        f"--user-data-dir={PROFILE}",
        url
    ])
    time.sleep(10)

def get_ws_url():
    import urllib.request
    data = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json").read())
    for t in data:
        u = t.get("url", "")
        if "alriyadh" in u and "login" not in u.lower():
            return t["webSocketDebuggerUrl"]
    for t in data:
        if "alriyadh" in t.get("url", ""):
            return t["webSocketDebuggerUrl"]
    return data[0]["webSocketDebuggerUrl"] if data else None

def connect(ws_url):
    ws = websocket.create_connection(ws_url, timeout=15)
    _id = [0]
    def send(method, params=None):
        _id[0] += 1
        msg = {"id": _id[0], "method": method}
        if params: msg["params"] = params
        ws.send(json.dumps(msg))
        while True:
            resp = json.loads(ws.recv())
            if resp.get("id") == _id[0]:
                return resp.get("result", {})
    return ws, send

def js(send, expr, await_promise=False):
    r = send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": await_promise})
    v = r.get("result", {})
    if "value" in v: return v["value"]
    if v.get("subtype") == "error": return f"ERROR: {v.get('description', 'unknown')}"
    return v

# =============================================================
# TEST A: Open Chrome directly on BLS/loginApi
# =============================================================
print("=" * 60)
print("TEST A: Chrome → BLS/loginApi (direct)")
print("=" * 60)
kill_chrome()
launch_chrome("https://app.alriyadh.gov.sa/BLS/loginApi")
ws_url = get_ws_url()
if not ws_url:
    print("FATAL: Cannot connect")
    sys.exit(1)
ws, send = connect(ws_url)

url = js(send, "document.location.href")
title = js(send, "document.title")
print(f"URL: {url}")
print(f"Title: {title}")

# Wait for possible SSO redirect
for i in range(6):
    time.sleep(3)
    url = js(send, "document.location.href")
    title = js(send, "document.title")
    body_len = js(send, "document.body ? document.body.innerHTML.length : 0")
    print(f"  [{(i+1)*3}s] URL: {url}")
    print(f"           Title: {title}")
    print(f"           Body: {body_len} bytes")
    if "login" not in url.lower() and "BLS" in url:
        print("  >>> SUCCESS! Left login page!")
        break

# Check if we have data
data_check = js(send, """
(function() {
    var tables = document.querySelectorAll('table');
    var totalRows = 0;
    tables.forEach(function(t) { totalRows += t.rows.length; });
    var links = document.querySelectorAll('a');
    var linkTexts = [];
    links.forEach(function(l) { 
        if (l.textContent.trim().length > 0 && l.textContent.trim().length < 50) 
            linkTexts.push(l.textContent.trim()); 
    });
    return JSON.stringify({
        url: document.location.href,
        tables: tables.length,
        rows: totalRows,
        bodyLen: document.body.innerHTML.length,
        links: linkTexts.slice(0, 30)
    });
})()
""")
if data_check and 'ERROR' not in str(data_check):
    dc = json.loads(data_check) if isinstance(data_check, str) else data_check
    print(f"\n  Data check:")
    print(f"    Tables: {dc.get('tables')}")
    print(f"    Total rows: {dc.get('rows')}")
    print(f"    Body: {dc.get('bodyLen')} bytes")
    print(f"    Links: {dc.get('links', [])[:15]}")

# =============================================================
# TEST B: From the current page, try to navigate to BLS8510
# =============================================================
print("\n" + "=" * 60)
print("TEST B: Navigate to BLS8510 (data query)")
print("=" * 60)

# Try various BLS URLs
for path in ["/BLS/faces/home", "/BLS/faces/BLS8510", "/BLS/BLS8510"]:
    js(send, f"document.location.href = 'https://app.alriyadh.gov.sa{path}'")
    time.sleep(3)
    url = js(send, "document.location.href")
    body_len = js(send, "document.body ? document.body.innerHTML.length : 0")
    print(f"  {path} → {url} ({body_len} bytes)")
    if "login" not in url.lower() and body_len > 10000:
        print("    >>> HAS DATA!")
        # Check tables
        tables_info = js(send, """
        (function() {
            var tables = document.querySelectorAll('table');
            var info = [];
            tables.forEach(function(t) {
                info.push({id: t.id, rows: t.rows.length, cols: t.rows[0] ? t.rows[0].cells.length : 0});
            });
            return JSON.stringify(info);
        })()
        """)
        print(f"    Tables: {tables_info}")

# =============================================================
# TEST C: If on BLS with data, read first page
# =============================================================
print("\n" + "=" * 60)
print("TEST C: Read data from BLS table")
print("=" * 60)

current_url = js(send, "document.location.href")
if "BLS" in current_url and "login" not in current_url.lower():
    page_data = js(send, """
    (function() {
        // Find data tables (tables with many rows)
        var tables = document.querySelectorAll('table');
        var bigTable = null;
        tables.forEach(function(t) {
            if (t.rows.length > 3) {
                if (!bigTable || t.rows.length > bigTable.rows.length) bigTable = t;
            }
        });
        
        if (!bigTable) return JSON.stringify({error: 'no data table found'});
        
        var result = {id: bigTable.id, rows: bigTable.rows.length, data: []};
        for (var r = 0; r < Math.min(bigTable.rows.length, 10); r++) {
            var row = [];
            for (var c = 0; c < bigTable.rows[r].cells.length; c++) {
                row.push(bigTable.rows[r].cells[c].textContent.trim().substring(0, 50));
            }
            result.data.push(row);
        }
        
        // Check for pagination links
        var pageLinks = document.querySelectorAll('a[id*="page"], a[id*=" Page"], td[id*="page"]');
        result.pageLinksCount = pageLinks.length;
        
        // Check total record count
        var allText = document.body.innerText;
        var recordMatch = allText.match(/(\d[\d,]*)\s*(سجل|نتيجة|record)/);
        result.recordCount = recordMatch ? recordMatch[1] : 'not found';
        
        return JSON.stringify(result);
    })()
    """)
    print(f"  Table data: {page_data}")
else:
    print(f"  Not on BLS page: {current_url}")

# =============================================================
# TEST D: From SSO home, navigate using ADF click on card
# =============================================================
print("\n" + "=" * 60)
print("TEST D: ADF peer.HandleComponentClick on UBS button")
print("=" * 60)

# Go to SSO home first
js(send, "document.location.href = 'https://app.alriyadh.gov.sa/SSO/loginApi'")
time.sleep(5)
js(send, "document.location.href = 'https://app.alriyadh.gov.sa/SSO/faces/home'")
time.sleep(5)
print(f"  Home URL: {js(send, 'document.location.href')}")

click_result = js(send, """
(function() {
    try {
        var comp = AdfPage.PAGE.findComponent('pt1:MenuButtonUBS');
        if (!comp) return JSON.stringify({error: 'component not found'});
        
        var peer = comp.getPeer();
        if (!peer) return JSON.stringify({error: 'no peer'});
        
        // Try HandleComponentClick
        if (typeof peer.HandleComponentClick === 'function') {
            peer.HandleComponentClick(comp);
            return JSON.stringify({method: 'HandleComponentClick', success: true});
        }
        
        // Try CreateComponentEvent + dispatch
        if (typeof peer.CreateComponentEvent === 'function') {
            var evt = peer.CreateComponentEvent(comp, 'action', true, true);
            if (evt) {
                comp.dispatchEvent(evt);
                return JSON.stringify({method: 'CreateComponentEvent+dispatch', success: true});
            }
        }
        
        return JSON.stringify({error: 'no suitable method found'});
    } catch(e) {
        return JSON.stringify({error: e.message, stack: e.stack ? e.stack.substring(0, 300) : ''});
    }
})()
""")
print(f"  Click result: {click_result}")
time.sleep(5)
url = js(send, "document.location.href")
print(f"  URL after ADF click: {url}")

print("\n=== DONE ===")
ws.close()
