"""
Test all approaches to navigate from SSO home to BLS
"""
import ssl, os, urllib3, time, json, sys, subprocess
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
import websocket

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = r"C:\Users\anaf\ScraperProfile"
DEBUG_PORT = 9223

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
        f"--user-data-dir={PROFILE}",
        "https://app.alriyadh.gov.sa/SSO/loginApi"
    ])
    time.sleep(8)

def get_ws_url():
    import urllib.request
    try:
        data = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json").read())
        for t in data:
            if "alriyadh" in t.get("url", ""):
                return t["webSocketDebuggerUrl"]
        if data:
            return data[0]["webSocketDebuggerUrl"]
    except Exception as e:
        print(f"  get_ws_url error: {e}")
    return None

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
    if "value" in v:
        return v["value"]
    if v.get("subtype") == "error":
        return f"ERROR: {v.get('description', 'unknown')}"
    return v

print("=== BLS Navigation Test ===")
kill_chrome()
launch_chrome()
ws_url = get_ws_url()
if not ws_url:
    print("FATAL: Cannot connect")
    sys.exit(1)

ws, send = connect(ws_url)
print(f"Connected. Tab: {js(send, 'document.location.href')}")

# Wait for ADF
time.sleep(3)
print(f"Page: {js(send, 'document.title')}")
print(f"URL: {js(send, 'document.location.href')}")

# =========================================================
# APPROACH 1: CDP Target.createTarget to open BLS in new tab
# =========================================================
print("\n--- Approach 1: Target.createTarget (new tab) ---")
try:
    r = send("Target.createTarget", {"url": "https://app.alriyadh.gov.sa/BLS/faces/home"})
    target_id = r.get("targetId", "")
    print(f"  New tab target: {target_id}")
    time.sleep(5)
    
    # Get the new tab's websocket
    import urllib.request
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json").read())
    for t in tabs:
        print(f"  Tab: {t.get('url', '')[:80]}")
    
    # Check if any tab is on BLS with data
    for t in tabs:
        if "BLS" in t.get("url", "") and "login" not in t.get("url", ""):
            ws2_url = t["webSocketDebuggerUrl"]
            ws2, send2 = connect(ws2_url)
            page_url = js(send2, "document.location.href")
            rows = js(send2, "document.querySelectorAll('[id$=\\':table\\'] tr, table[id*=table] tr').length")
            print(f"  BLS tab URL: {page_url}, rows: {rows}")
            ws2.close()
except Exception as e:
    print(f"  Error: {e}")

# =========================================================
# APPROACH 2: Find and click the UBS CARD (visible element)
# =========================================================
print("\n--- Approach 2: CDP click on UBS card ---")
try:
    # Navigate back to home
    js(send, "window.location.href = 'https://app.alriyadh.gov.sa/SSO/faces/home'")
    time.sleep(5)
    
    # Find the card with UPS text
    card_info = js(send, """
    (function() {
        // Find all elements that contain "نظام الرخص" or "UPS" or "UBS"
        var els = document.querySelectorAll('*');
        var found = [];
        for (var i = 0; i < els.length; i++) {
            var el = els[i];
            var txt = el.textContent || '';
            if (txt.indexOf('نظام الرخص') >= 0 && el.children.length < 10) {
                var rect = el.getBoundingClientRect();
                found.push({
                    tag: el.tagName,
                    id: el.id || '',
                    cls: (el.className || '').toString().substring(0, 80),
                    x: rect.x, y: rect.y, w: rect.width, h: rect.height,
                    txt: txt.substring(0, 50)
                });
            }
        }
        return JSON.stringify(found.slice(-10));
    })()
    """)
    print(f"  Card elements: {card_info}")
    
    # Try clicking the first visible one
    if card_info and card_info != '[]' and 'ERROR' not in str(card_info):
        cards = json.loads(card_info) if isinstance(card_info, str) else card_info
        for card in cards:
            if card.get('w', 0) > 50 and card.get('h', 0) > 50:
                cx = card['x'] + card['w'] / 2
                cy = card['y'] + card['h'] / 2
                print(f"  Clicking card at ({cx}, {cy}) size {card['w']}x{card['h']}")
                
                # Mouse press + release
                send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": cx, "y": cy, "button": "left", "clickCount": 1})
                send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": cx, "y": cy, "button": "left", "clickCount": 1})
                time.sleep(5)
                
                new_url = js(send, "document.location.href")
                new_title = js(send, "document.title")
                print(f"  After click - URL: {new_url}")
                print(f"  After click - Title: {new_title}")
                
                if "BLS" in new_url and "login" not in new_url:
                    print("  SUCCESS! Reached BLS!")
                    break
except Exception as e:
    print(f"  Error: {e}")

# =========================================================
# APPROACH 3: window.open from within page
# =========================================================
print("\n--- Approach 3: window.open() ---")
try:
    js(send, "window.location.href = 'https://app.alriyadh.gov.sa/SSO/faces/home'")
    time.sleep(5)
    
    # Try window.open
    result = js(send, """
    (function() {
        var w = window.open('https://app.alriyadh.gov.sa/BLS/faces/home', '_blank');
        return w ? 'opened' : 'blocked';
    })()
    """)
    print(f"  window.open result: {result}")
    time.sleep(5)
    
    # Check all tabs
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json").read())
    for t in tabs:
        url = t.get("url", "")
        print(f"  Tab: {url[:100]}")
except Exception as e:
    print(f"  Error: {e}")

# =========================================================
# APPROACH 4: Navigate to BLS/faces/login (NOT /home)
# =========================================================
print("\n--- Approach 4: BLS/faces/login directly ---")
try:
    js(send, "document.location.href = 'https://app.alriyadh.gov.sa/BLS/faces/login'")
    time.sleep(5)
    
    page_url = js(send, "document.location.href")
    title = js(send, "document.title")
    has_table = js(send, "document.querySelectorAll('table').length")
    body_len = js(send, "document.body.innerHTML.length")
    print(f"  URL: {page_url}")
    print(f"  Title: {title}")
    print(f"  Tables: {has_table}")
    print(f"  Body length: {body_len}")
    
    # Check if there's a form on login page that auto-submits
    forms = js(send, """
    (function() {
        var forms = document.querySelectorAll('form');
        var result = [];
        for (var i = 0; i < forms.length; i++) {
            result.push({
                action: forms[i].action,
                method: forms[i].method,
                id: forms[i].id,
                inputs: forms[i].querySelectorAll('input').length
            });
        }
        return JSON.stringify(result);
    })()
    """)
    print(f"  Forms: {forms}")
    
    # Check for any scripts that might auto-redirect
    scripts = js(send, """
    (function() {
        var scripts = document.querySelectorAll('script');
        var content = '';
        for (var i = 0; i < scripts.length; i++) {
            content += scripts[i].textContent + '\\n';
        }
        return content.substring(0, 2000);
    })()
    """)
    print(f"  Scripts: {scripts[:500]}")
except Exception as e:
    print(f"  Error: {e}")

# =========================================================
# APPROACH 5: Try clicking the hidden button with CDP focus + enter
# =========================================================
print("\n--- Approach 5: Focus + Enter on hidden button ---")
try:
    js(send, "document.location.href = 'https://app.alriyadh.gov.sa/SSO/faces/home'")
    time.sleep(5)
    
    # Find the hidden UBS button and try to make it visible then click
    result = js(send, """
    (function() {
        var btn = document.getElementById('pt1:MenuButtonUBS');
        if (!btn) return 'button not found';
        // Try to make it visible
        btn.style.display = 'block';
        btn.style.visibility = 'visible';
        btn.style.opacity = '1';
        btn.style.position = 'relative';
        btn.style.width = '100px';
        btn.style.height = '30px';
        btn.style.zIndex = '99999';
        btn.style.pointerEvents = 'auto';
        
        // Also fix parent elements
        var p = btn.parentElement;
        while (p) {
            p.style.overflow = 'visible';
            p.style.display = 'block';
            p.style.visibility = 'visible';
            p.style.opacity = '1';
            p = p.parentElement;
        }
        
        return 'made visible, id=' + btn.id + ' outerHTML=' + btn.outerHTML.substring(0, 200);
    })()
    """)
    print(f"  Button: {result}")
    time.sleep(1)
    
    # Now get its position and click with CDP
    pos = js(send, """
    (function() {
        var btn = document.getElementById('pt1:MenuButtonUBS');
        if (!btn) return null;
        var rect = btn.getBoundingClientRect();
        return JSON.stringify({x: rect.x, y: rect.y, w: rect.width, h: rect.height});
    })()
    """)
    print(f"  Position after make-visible: {pos}")
    
    if pos and 'ERROR' not in str(pos) and pos != 'null':
        p = json.loads(pos) if isinstance(pos, str) else pos
        if p.get('w', 0) > 0 and p.get('h', 0) > 0:
            cx = p['x'] + p['w'] / 2
            cy = p['y'] + p['h'] / 2
            print(f"  Clicking at ({cx}, {cy})")
            send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": cx, "y": cy, "button": "left", "clickCount": 1})
            send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": cx, "y": cy, "button": "left", "clickCount": 1})
            time.sleep(5)
            new_url = js(send, "document.location.href")
            print(f"  After click URL: {new_url}")
except Exception as e:
    print(f"  Error: {e}")

# =========================================================
# APPROACH 6: Check ADF js objects more carefully
# =========================================================
print("\n--- Approach 6: ADF JavaScript API deep check ---")
try:
    js(send, "document.location.href = 'https://app.alriyadh.gov.sa/SSO/faces/home'")
    time.sleep(5)
    
    result = js(send, """
    (function() {
        var info = {};
        info.hasAdfPage = typeof AdfPage !== 'undefined';
        if (info.hasAdfPage) {
            info.hasPAGE = typeof AdfPage.PAGE !== 'undefined';
            if (AdfPage.PAGE) {
                var page = AdfPage.PAGE;
                info.pageKeys = Object.keys(page).filter(k => typeof page[k] === 'function').join(', ');
                info.hasGetComponent = typeof page.getComponent === 'function';
                info.hasFindComponent = typeof page.findComponent === 'function';
                info.hasAddPartialTarget = typeof page.addPartialTarget === 'function';
                // Try to find the form
                if (typeof AdfUIPage !== 'undefined') {
                    info.hasAdfUIPage = true;
                }
            }
        }
        info.hasAdfActionEvent = typeof AdfActionEvent !== 'undefined';
        info.hasAdfEventQueue = typeof AdfEventQueue !== 'undefined';
        
        // Try to find components by clientId
        try {
            var comp = AdfPage.PAGE.getComponent('pt1:MenuButtonUBS');
            info.ubsComponent = comp ? 'found' : 'null';
        } catch(e) {
            info.ubsComponentError = e.message;
        }
        
        // Try findComponent
        try {
            var comp2 = AdfPage.PAGE.findComponent('pt1:MenuButtonUBS');
            info.ubsFindComponent = comp2 ? 'found' : 'null';
        } catch(e) {
            info.ubsFindComponentError = e.message;
        }
        
        // Check if there's a navigation service
        try {
            info.hasNavigate = typeof AdfNavigationService !== 'undefined';
        } catch(e) {}
        
        // Check _clientIdToComponentMap
        try {
            var map = page._clientIdToComponentMap;
            info.mapKeys = map ? Object.keys(map).join(', ') : 'null';
            info.mapSize = map ? Object.keys(map).length : 0;
        } catch(e) {
            info.mapError = e.message;
        }
        
        return JSON.stringify(info);
    })()
    """)
    print(f"  ADF Info: {result}")
except Exception as e:
    print(f"  Error: {e}")

# =========================================================
# APPROACH 7: Use ADF internal form submission
# =========================================================
print("\n--- Approach 7: ADF internal form submit ---")
try:
    result = js(send, """
    (function() {
        try {
            // Find the form
            var form = document.getElementById('pt1');
            if (!form) return 'form pt1 not found';
            
            // Find the submit button
            var btn = document.getElementById('pt1:MenuButtonUBS');
            if (!btn) return 'button not found';
            
            // Set the javax.faces.source to the button
            var sourceInput = form.querySelector('input[name="javax.faces.source"]');
            if (!sourceInput) {
                sourceInput = document.createElement('input');
                sourceInput.type = 'hidden';
                sourceInput.name = 'javax.faces.source';
                form.appendChild(sourceInput);
            }
            sourceInput.value = btn.id;
            
            // Set javax.faces.partial.event
            var eventInput = form.querySelector('input[name="javax.faces.partial.event"]');
            if (!eventInput) {
                eventInput = document.createElement('input');
                eventInput.type = 'hidden';
                eventInput.name = 'javax.faces.partial.event';
                form.appendChild(eventInput);
            }
            eventInput.value = 'action';
            
            // Set javax.faces.partial.ajax
            var ajaxInput = form.querySelector('input[name="javax.faces.partial.ajax"]');
            if (!ajaxInput) {
                ajaxInput = document.createElement('input');
                ajaxInput.type = 'hidden';
                ajaxInput.name = 'javax.faces.partial.ajax';
                form.appendChild(ajaxInput);
            }
            ajaxInput.value = 'true';
            
            // Set javax.faces.partial.execute
            var execInput = form.querySelector('input[name="javax.faces.partial.execute"]');
            if (!execInput) {
                execInput = document.createElement('input');
                execInput.type = 'hidden';
                execInput.name = 'javax.faces.partial.execute';
                form.appendChild(execInput);
            }
            execInput.value = btn.id + ' @all';
            
            // Set javax.faces.partial.render
            var renderInput = form.querySelector('input[name="javax.faces.partial.render"]');
            if (!renderInput) {
                renderInput = document.createElement('input');
                renderInput.type = 'hidden';
                renderInput.name = 'javax.faces.partial.render';
                form.appendChild(renderInput);
            }
            renderInput.value = '@all';
            
            // Now submit via XMLHttpRequest (ADF style)
            var fd = new FormData(form);
            var xhr = new XMLHttpRequest();
            xhr.open('POST', form.action, false);
            xhr.send(fd);
            
            return 'submitted, status=' + xhr.status + ' len=' + xhr.responseText.length + ' url=' + xhr.responseURL;
        } catch(e) {
            return 'error: ' + e.message;
        }
    })()
    """)
    print(f"  Result: {result}")
except Exception as e:
    print(f"  Error: {e}")

# =========================================================
# APPROACH 8: Check what cookies exist for BLS path
# =========================================================
print("\n--- Approach 8: Check BLS cookies ---")
try:
    cookies = js(send, "document.cookie")
    print(f"  Cookies: {cookies[:500]}")
    
    # Try to set a fake BLS session cookie and navigate
    result = js(send, """
    (function() {
        // Check if there are any cookies for the BLS path
        return document.cookie;
    })()
    """)
    print(f"  All cookies: {result[:500]}")
except Exception as e:
    print(f"  Error: {e}")

print("\n=== Done ===")
ws.close()
