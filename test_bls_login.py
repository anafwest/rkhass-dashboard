"""
Deep analysis of BLS login page + try to authenticate
"""
import ssl, os, urllib3, time, json, sys, subprocess
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
import websocket

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = r"C:\Users\anaf\ScraperProfile"
DEBUG_PORT = 9224

def kill_chrome():
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
    time.sleep(2)

def launch_chrome():
    subprocess.Popen([
        CHROME,
        f"--remote-debugging-port={DEBUG_PORT}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--disable-popup-blocking",
        "--auth-server-allowlist=*alriyadh.gov.sa",
        "--auth-negotiate-allowlist=*alriyadh.gov.sa",
        "--enable-features=NetworkServiceProcessHost",
        f"--user-data-dir={PROFILE}",
        "https://app.alriyadh.gov.sa/SSO/loginApi"
    ])
    time.sleep(10)

def get_ws_url():
    import urllib.request
    data = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json").read())
    for t in data:
        if "alriyadh" in t.get("url", ""):
            return t["webSocketDebuggerUrl"]
    return data[0]["webSocketDebuggerUrl"] if data else None

def connect(ws_url):
    ws = websocket.create_connection(ws_url, timeout=10)
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

kill_chrome()
launch_chrome()
ws_url = get_ws_url()
if not ws_url:
    print("FATAL")
    sys.exit(1)
ws, send = connect(ws_url)
print(f"Connected. URL: {js(send, 'document.location.href')}")

# =========================================================
# STEP 1: Wait for SSO to complete on home page
# =========================================================
print("\n=== Step 1: Verify we're on home ===")
time.sleep(3)
print(f"URL: {js(send, 'document.location.href')}")
print(f"Title: {js(send, 'document.title')}")

# =========================================================
# STEP 2: Navigate to BLS/faces/login and analyze the form
# =========================================================
print("\n=== Step 2: Navigate to BLS/faces/login ===")
js(send, "document.location.href = 'https://app.alriyadh.gov.sa/BLS/faces/login'")
time.sleep(8)

url = js(send, "document.location.href")
print(f"URL after nav: {url}")
print(f"Title: {js(send, 'document.title')}")

# Analyze the login form
form_analysis = js(send, """
(function() {
    var result = {};
    
    // Check all forms
    var forms = document.querySelectorAll('form');
    result.forms = [];
    forms.forEach(function(f, i) {
        var fd = {id: f.id, action: f.action, method: f.method, inputs: []};
        f.querySelectorAll('input').forEach(function(inp) {
            fd.inputs.push({
                name: inp.name,
                type: inp.type,
                value: inp.value ? inp.value.substring(0, 100) : '',
                id: inp.id
            });
        });
        result.forms.push(fd);
    });
    
    // Check for auto-submit scripts
    var allScripts = '';
    document.querySelectorAll('script').forEach(function(s) {
        allScripts += s.textContent + '\\n';
    });
    result.hasAutoSubmit = allScripts.indexOf('submit()') >= 0 || allScripts.indexOf('.submit') >= 0;
    result.hasRedirect = allScripts.indexOf('redirect') >= 0 || allScripts.indexOf('location') >= 0;
    result.scriptSnippet = allScripts.substring(0, 3000);
    
    // Check body content summary
    result.bodyText = document.body ? document.body.innerText.substring(0, 1000) : '';
    result.bodyLen = document.body ? document.body.innerHTML.length : 0;
    
    return JSON.stringify(result);
})()
""", await_promise=False)
if form_analysis and 'ERROR' not in str(form_analysis):
    fa = json.loads(form_analysis) if isinstance(form_analysis, str) else form_analysis
    print(f"\nForms found: {len(fa.get('forms', []))}")
    for i, f in enumerate(fa.get('forms', [])):
        print(f"\n  Form {i}: id={f['id']}, action={f['action'][:80]}, method={f['method']}")
        for inp in f.get('inputs', []):
            print(f"    {inp['name']}: type={inp['type']}, value={inp['value'][:50]}, id={inp['id']}")
    print(f"\nHas auto-submit: {fa.get('hasAutoSubmit')}")
    print(f"Has redirect: {fa.get('hasRedirect')}")
    print(f"Body length: {fa.get('bodyLen')}")
    print(f"Body text:\n{fa.get('bodyText', '')[:500]}")
    print(f"\nScripts:\n{fa.get('scriptSnippet', '')[:2000]}")
else:
    print(f"Form analysis failed: {form_analysis}")

# =========================================================
# STEP 3: Wait longer - maybe Windows SSO auto-redirects
# =========================================================
print("\n=== Step 3: Wait for auto-redirect (15s) ===")
for i in range(5):
    time.sleep(3)
    url = js(send, "document.location.href")
    print(f"  [{i*3}s] URL: {url}")
    if "login" not in url.lower():
        print("  REDIRECTED!")
        break

# =========================================================
# STEP 4: Try submitting the login form
# =========================================================
print("\n=== Step 4: Submit login form ===")
submit_result = js(send, """
(function() {
    var form = document.getElementById('f1');
    if (!form) return 'form f1 not found';
    
    // Get all hidden inputs
    var hiddenInputs = {};
    form.querySelectorAll('input[type=hidden]').forEach(function(inp) {
        hiddenInputs[inp.name] = inp.value;
    });
    
    // Try direct submit
    try {
        form.submit();
        return 'form submitted. hiddenInputs: ' + JSON.stringify(Object.keys(hiddenInputs));
    } catch(e) {
        return 'submit error: ' + e.message;
    }
})()
""")
print(f"  Submit result: {submit_result}")
time.sleep(8)
print(f"  URL after submit: {js(send, 'document.location.href')}")
print(f"  Title: {js(send, 'document.title')}")

# Check if we got data
data_check = js(send, """
(function() {
    var tables = document.querySelectorAll('table');
    var totalRows = 0;
    tables.forEach(function(t) { totalRows += t.rows.length; });
    return 'tables=' + tables.length + ' totalRows=' + totalRows + ' bodyLen=' + document.body.innerHTML.length;
})()
""")
print(f"  Data check: {data_check}")

# =========================================================
# STEP 5: If still on login, try fetching BLS with cookies from SSO
# =========================================================
print("\n=== Step 5: Fetch BLS from within page context ===")
# First go back to home
js(send, "document.location.href = 'https://app.alriyadh.gov.sa/SSO/faces/home'")
time.sleep(5)
print(f"  Home URL: {js(send, 'document.location.href')}")

# Try fetch to BLS/faces/login and check response
fetch_result = js(send, """
(async function() {
    try {
        var resp = await fetch('https://app.alriyadh.gov.sa/BLS/faces/login', {
            credentials: 'include',
            redirect: 'follow'
        });
        var text = await resp.text();
        return JSON.stringify({
            url: resp.url,
            status: resp.status,
            redirected: resp.redirected,
            len: text.length,
            snippet: text.substring(0, 1500)
        });
    } catch(e) {
        return JSON.stringify({error: e.message});
    }
})()
""", await_promise=True)
if fetch_result and 'ERROR' not in str(fetch_result):
    fr = json.loads(fetch_result) if isinstance(fetch_result, str) else fetch_result
    print(f"  Fetched URL: {fr.get('url', '')[:100]}")
    print(f"  Status: {fr.get('status')}")
    print(f"  Redirected: {fr.get('redirected')}")
    print(f"  Body length: {fr.get('len')}")
    print(f"  Body snippet:\n{fr.get('snippet', '')[:1000]}")
else:
    print(f"  Fetch failed: {fetch_result}")

# =========================================================
# STEP 6: Try BLS SSO login API (like portal loginApi)
# =========================================================
print("\n=== Step 6: Try BLS login API ===")
for path in ["/BLS/loginApi", "/BLS/faces/loginApi", "/BLS/sso/login"]:
    try:
        r = js(send, f"""
        (async function() {{
            try {{
                var resp = await fetch('https://app.alriyadh.gov.sa{path}', {{
                    credentials: 'include',
                    redirect: 'follow'
                }});
                var text = await resp.text();
                return JSON.stringify({{
                    path: '{path}',
                    url: resp.url,
                    status: resp.status,
                    redirected: resp.redirected,
                    len: text.length,
                    snippet: text.substring(0, 300)
                }});
            }} catch(e) {{
                return JSON.stringify({{path: '{path}', error: e.message}});
            }}
        }})()
        """, await_promise=True)
        if r and 'ERROR' not in str(r):
            ri = json.loads(r) if isinstance(r, str) else r
            print(f"  {path}: status={ri.get('status')}, redirected={ri.get('redirected')}, len={ri.get('len')}, url={ri.get('url', '')[:80]}")
            if ri.get('snippet'):
                print(f"    snippet: {ri['snippet'][:200]}")
    except Exception as e:
        print(f"  {path}: error {e}")

# =========================================================
# STEP 7: Check network requests to see what the UBS button actually sends
# =========================================================
print("\n=== Step 7: Enable network tracking, then click UBS button ===")
# Go back to home first
js(send, "document.location.href = 'https://app.alriyadh.gov.sa/SSO/faces/home'")
time.sleep(5)

# Enable network tracking
send("Network.enable", {})
time.sleep(1)

# Find the UBS button component and try to invoke its action
invoke_result = js(send, """
(function() {
    try {
        // Use AdfPage.PAGE.findComponent which we know works
        var comp = AdfPage.PAGE.findComponent('pt1:MenuButtonUBS');
        if (!comp) return 'component not found';
        
        var info = {
            id: comp.getId(),
            clientId: comp.getClientId(),
            type: comp.getClassDescription ? comp.getClassDescription() : 'unknown',
        };
        
        // Check available methods
        var methods = [];
        for (var k in comp) {
            if (typeof comp[k] === 'function' && k.indexOf('Action') >= 0) {
                methods.push(k);
            }
        }
        info.actionMethods = methods;
        
        // Try to get the component's peer (ADF component peer)
        if (comp.getPeer) {
            var peer = comp.getPeer();
            info.hasPeer = !!peer;
            if (peer) {
                var peerMethods = [];
                for (var k in peer) {
                    if (typeof peer[k] === 'function') peerMethods.push(k);
                }
                info.peerMethods = peerMethods.join(', ');
            }
        }
        
        // Try fireAction
        if (comp.fireAction) {
            info.canFireAction = true;
        }
        
        // Try to fire a DOM event on the component's element
        var elem = comp.getDomNode ? comp.getDomNode() : null;
        if (!elem) elem = document.getElementById(comp.getClientId());
        if (elem) {
            info.elemTag = elem.tagName;
            info.elemId = elem.id;
            
            // Try dispatching a click event via DOM
            var evt = new MouseEvent('click', {bubbles: true, cancelable: true, view: window});
            elem.dispatchEvent(evt);
            info.domClickDispatched = true;
        }
        
        return JSON.stringify(info);
    } catch(e) {
        return JSON.stringify({error: e.message, stack: e.stack ? e.stack.substring(0, 500) : ''});
    }
})()
""")
if invoke_result and 'ERROR' not in str(invoke_result):
    ir = json.loads(invoke_result) if isinstance(invoke_result, str) else invoke_result
    print(f"  Component info: {json.dumps(ir, indent=2, ensure_ascii=False)}")
else:
    print(f"  Invoke result: {invoke_result}")

time.sleep(5)

# Check network requests
print("\n  Checking if any BLS requests were made...")
bls_url = js(send, "document.location.href")
print(f"  Current URL: {bls_url}")

# Stop network tracking
send("Network.disable", {})

print("\n=== Done ===")
ws.close()
