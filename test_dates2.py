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

def cdp_click(x, y):
    send("Input.dispatchMouseEvent", {"type":"mousePressed", "x":x, "y":y, "button":"left", "clickCount":3})
    send("Input.dispatchMouseEvent", {"type":"mouseReleased", "x":x, "y":y, "button":"left", "clickCount":3})

print(f"URL: {js('document.location.href')}")

# First, let me check the current state of the date fields
r = js("""(function(){
    var fromEl = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content');
    var toEl = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Todate::content');
    return JSON.stringify({
        from: fromEl ? fromEl.value : 'not found',
        to: toEl ? toEl.value : 'not found',
        fromRect: fromEl ? JSON.stringify(fromEl.getBoundingClientRect()) : '',
        toRect: toEl ? JSON.stringify(toEl.getBoundingClientRect()) : ''
    });
})()""")
print(f"Current values: {r}")

# Clear From date by selecting all + typing
print("\n--- Clear and set From date ---")
r = js("""(function(){
    var el = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content');
    if(!el) return 'not found';
    el.focus();
    el.removeAttribute('readonly');
    var rect = el.getBoundingClientRect();
    return JSON.stringify({x: rect.x + rect.width/2, y: rect.y + rect.height/2, w: rect.width, h: rect.height});
})()""")
pos = json.loads(r)
print(f"  From pos: {pos}")

# Triple-click to select all text in field
cdp_click(pos['x'], pos['y'])
time.sleep(0.3)

# Delete selected text
send("Input.dispatchKeyEvent", {"type":"keyDown", "key":"Delete", "code":"Delete", "windowsVirtualKeyCode":46})
send("Input.dispatchKeyEvent", {"type":"keyUp", "key":"Delete", "code":"Delete", "windowsVirtualKeyCode":46})
time.sleep(0.2)

# Type new date
cdp_type("1447/04/13")
time.sleep(0.5)

# Click somewhere else to trigger blur
js("document.body.click()")
time.sleep(1)

# Check value
r = js("""document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content').value""")
print(f"  From value: {r}")

# Clear To date
print("\n--- Clear and set To date ---")
r = js("""(function(){
    var el = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Todate::content');
    if(!el) return 'not found';
    el.focus();
    el.removeAttribute('readonly');
    var rect = el.getBoundingClientRect();
    return JSON.stringify({x: rect.x + rect.width/2, y: rect.y + rect.height/2});
})()""")
pos2 = json.loads(r)
print(f"  To pos: {pos2}")

cdp_click(pos2['x'], pos2['y'])
time.sleep(0.3)
send("Input.dispatchKeyEvent", {"type":"keyDown", "key":"Delete", "code":"Delete", "windowsVirtualKeyCode":46})
send("Input.dispatchKeyEvent", {"type":"keyUp", "key":"Delete", "code":"Delete", "windowsVirtualKeyCode":46})
time.sleep(0.2)
cdp_type("1448/12/29")
time.sleep(0.5)
js("document.body.click()")
time.sleep(1)

r = js("""document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Todate::content').value""")
print(f"  To value: {r}")

# Also set via ADF
js("""(function(){
    try{
        AdfPage.PAGE.findComponent('pt1:cBodFDC:r1:0:masteraTable:Fromdate').setValue('1447/04/13');
        AdfPage.PAGE.findComponent('pt1:cBodFDC:r1:0:masteraTable:Todate').setValue('1448/12/29');
    }catch(e){}
})()""")
time.sleep(1)

# Click search
print("\n--- Search ---")
js("""document.getElementById('pt1:cBodFDC:r1:0:masteraTable:search').click()""")
time.sleep(10)

# Results
r = js("""(function(){
    var text = document.body.innerText;
    var m = text.match(/\\(([\\d,]+)-(\\d[\\d,]+)\\s+من\\s+(\\d[\\d,]+)/);
    var count = text.match(/العدد\\s*(\\d+)/);
    return JSON.stringify({pageInfo: m?m[0]:'not found', count: count?count[0]:'not found'});
})()""")
print(f"Results: {r}")

r = js("""(function(){
    var tables = document.querySelectorAll('table');
    var max = 0;
    tables.forEach(function(t){
        if(t.className && t.className.indexOf('af_table_data-table') >= 0 && t.rows.length > max) max = t.rows.length;
    });
    return 'rows=' + max;
})()""")
print(f"Table: {r}")

# Check the 4 rows content
r = js("""(function(){
    var tables = document.querySelectorAll('table');
    var table = null;
    tables.forEach(function(t){
        if(t.className && t.className.indexOf('af_table_data-table') >= 0) table = t;
    });
    if(!table) return 'no table';
    var res = [];
    for(var r=1; r<table.rows.length; r++){
        var tds = table.rows[r].querySelectorAll('td');
        var row = [];
        tds.forEach(function(td){ row.push(td.innerText.trim().substring(0,30)); });
        res.push(row.join(' | '));
    }
    return res.join('\\n');
})()""")
print(f"Data:\n{r}")

ws.close()
