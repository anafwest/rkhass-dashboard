import json, urllib.request, websocket, time, sys
sys.stdout.reconfigure(encoding='utf-8')
PORT = 9222

data = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json').read())
ws_url = None
for t in data:
    if 'alriyadh' in t.get('url','') and t.get('type')=='page':
        ws_url = t['webSocketDebuggerUrl']; break
ws = websocket.create_connection(ws_url, timeout=30)
_id = [0]
def send(m,p=None):
    _id[0]+=1; msg={'id':_id[0],'method':m}
    if p: msg['params']=p
    ws.send(json.dumps(msg))
    while True:
        r=json.loads(ws.recv())
        if r.get('id')==_id[0]: return r.get('result',{})
def js(e,ap=False):
    r=send('Runtime.evaluate',{'expression':e,'returnByValue':True,'awaitPromise':ap})
    v=r.get('result',{})
    if 'value' in v: return v['value']
    if v.get('subtype')=='error': return 'ERR:'+v.get('description','')
    return v

def cdp_type(text):
    send("Input.insertText", {"text": text})

def cdp_key(key_code, key):
    send("Input.dispatchKeyEvent", {"type":"keyDown", "key":key, "code":key_code, "windowsVirtualKeyCode":key_code})
    send("Input.dispatchKeyEvent", {"type":"keyUp", "key":key, "code":key_code, "windowsVirtualKeyCode":key_code})

def cdp_clear_field():
    cdp_key(35, "End")
    time.sleep(0.1)
    for _ in range(20):
        cdp_key(8, "Backspace")
        time.sleep(0.02)

print(f"URL: {js('document.location.href')}")

# Step 1: Focus the From date field
print("\n--- Setting From date ---")
r = js("""(function(){
    var el = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content');
    if(!el) return 'not found';
    el.focus();
    el.removeAttribute('readonly');
    el.click();
    return 'focused, value=' + el.value;
})()""")
print(f"  Focus: {r}")

# Select all and clear
cdp_key(65, "a")  # Ctrl+A
time.sleep(0.2)
cdp_clear_field()
time.sleep(0.3)

# Type the date
cdp_type("1447/04/13")
time.sleep(0.5)

# Press Tab to move to next field
cdp_key(9, "Tab")
time.sleep(1)

# Check value
r = js("""(function(){
    var el = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content');
    return el ? 'value=' + el.value : 'not found';
})()""")
print(f"  From value after type: {r}")

# Step 2: Focus the To date field
print("\n--- Setting To date ---")
r = js("""(function(){
    var el = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Todate::content');
    if(!el) return 'not found';
    el.focus();
    el.removeAttribute('readonly');
    el.click();
    return 'focused, value=' + el.value;
})()""")
print(f"  Focus: {r}")

cdp_key(65, "a")
time.sleep(0.2)
cdp_clear_field()
time.sleep(0.3)
cdp_type("1448/12/29")
time.sleep(0.5)

r = js("""(function(){
    var el = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Todate::content');
    return el ? 'value=' + el.value : 'not found';
})()""")
print(f"  To value after type: {r}")

# Step 3: Click search
print("\n--- Clicking Search ---")
r = js("""(function(){
    var btn = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:search');
    if(!btn) return 'not found';
    btn.click();
    return 'clicked';
})()""")
print(f"  Search: {r}")

time.sleep(10)

# Check results
r = js("""(function(){
    var text = document.body.innerText;
    var m = text.match(/\\(([\\d,]+)-(\\d[\\d,]+)\\s+من\\s+(\\d[\\d,]+)/);
    return m ? m[0] : 'not found';
})()""")
print(f"  Results: {r}")

r = js("""(function(){
    var tables = document.querySelectorAll('table');
    var max = 0;
    tables.forEach(function(t){
        if(t.className && t.className.indexOf('af_table_data-table') >= 0 && t.rows.length > max) max = t.rows.length;
    });
    return 'data rows=' + max;
})()""")
print(f"  Table: {r}")

ws.close()
