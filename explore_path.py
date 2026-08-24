import ssl, os, urllib3, time, json, sys, subprocess, urllib.request
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
import websocket

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = r"C:\Users\anaf\ScraperProfile"
PORT = 9226

subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
time.sleep(2)
subprocess.Popen([CHROME, f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
    "--no-first-run", "--disable-popup-blocking", f"--user-data-dir={PROFILE}",
    "https://app.alriyadh.gov.sa/SSO/loginApi"])
time.sleep(10)

data = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
ws_url = None
for t in data:
    if "alriyadh" in t.get("url",""):
        ws_url = t["webSocketDebuggerUrl"]; break
if not ws_url: ws_url = data[0]["webSocketDebuggerUrl"]

ws = websocket.create_connection(ws_url, timeout=15)
_mid = [0]
def send(m, p=None):
    _mid[0]+=1; msg={"id":_mid[0],"method":m}
    if p: msg["params"]=p
    ws.send(json.dumps(msg))
    while True:
        r=json.loads(ws.recv())
        if r.get("id")==_mid[0]: return r.get("result",{})

def js(e, ap=False):
    r=send("Runtime.evaluate",{"expression":e,"returnByValue":True,"awaitPromise":ap})
    v=r.get("result",{})
    if "value" in v: return v["value"]
    if v.get("subtype")=="error": return "ERR:"+v.get("description","")
    return v

time.sleep(5)
print(f"URL: {js('document.location.href')}")
print(f"Title: {js('document.title')}")

# List ALL cards/buttons with their visible text
info = js("""
(function(){
    var cards = document.querySelectorAll('[class*="card"], [class*="Card"], [class*="col"]');
    var result = [];
    for(var i=0; i<cards.length; i++){
        var c = cards[i];
        var txt = c.textContent.trim().replace(/\\s+/g,' ').substring(0,100);
        var btn = c.querySelector('button');
        var btnId = btn ? btn.id : 'none';
        if(txt.length > 3) result.push({card:i, text:txt.substring(0,60), btnId:btnId});
    }
    return JSON.stringify(result.slice(0,30));
})()
""")
cards = json.loads(info) if info and 'ERR' not in str(info) else []
print(f"\nCards on page: {len(cards)}")
for c in cards:
    print(f"  [{c['card']}] btn={c['btnId'][:30]} text={c['text'][:50]}")

# Find the FORM_APP card position
pos = js("""
(function(){
    var btn = document.getElementById('pt1:MenuButtonFORM_APP');
    if(!btn) return 'not found';
    var p = btn;
    for(var i=0;i<15;i++){
        p = p.parentElement;
        if(!p) break;
        var r = p.getBoundingClientRect();
        if(r.width>100 && r.height>100){
            return JSON.stringify({tag:p.tagName,cls:(p.className||'').toString().substring(0,60),
                x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2),
                w:Math.round(r.width), h:Math.round(r.height)});
        }
    }
    var r2 = btn.getBoundingClientRect();
    return JSON.stringify({tag:btn.tagName,x:Math.round(r2.x+r2.width/2),y:Math.round(r2.y+r2.height/2),w:Math.round(r2.width),h:Math.round(r2.height)});
})()
""")
print(f"\nFORM_APP card: {pos}")

# Try AdfActionEvent
print("\n--- Try AdfActionEvent ---")
r1 = js("""
(function(){
    try{
        var c = AdfPage.PAGE.findComponent('pt1:MenuButtonFORM_APP');
        if(!c) return 'not found';
        var expr = c.getActionExpression();
        var evt = new AdfActionEvent(c, expr);
        evt.queue();
        return 'queued expr=' + (expr||'null');
    }catch(e){return 'ERR:'+e.message;}
})()
""")
print(f"  Result: {r1}")
time.sleep(8)

# Check result
print(f"  URL: {js('document.location.href')}")
print(f"  Title: {js('document.title')}")

# Check all tabs
tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
print(f"\nAll tabs ({len(tabs)}):")
for t in tabs:
    u = t.get("url","")
    if "alriyadh" in u or ("chrome" not in u and u and u != "about:blank"):
        print(f"  {u[:120]}")

ws.close()
