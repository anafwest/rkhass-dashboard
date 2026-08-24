import json, time, websocket, subprocess, sys, os, urllib.request

CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
PORT = 9222
SSO_URL = 'https://app.alriyadh.gov.sa/SSO/loginApi'
BLS_URL = 'https://app.alriyadh.gov.sa/BLS/loginApi'

os.system('taskkill /F /IM chrome.exe >nul 2>&1')
time.sleep(3)

subprocess.Popen([CHROME, f'--remote-debugging-port={PORT}', '--remote-allow-origins=*',
                   '--user-data-dir=C:\\Users\\anaf\\ScraperProfile', '--no-first-run',
                   '--no-default-browser-check', '--disable-blink-features=AutomationControlled', SSO_URL],
                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

for i in range(20):
    time.sleep(2)
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/version', timeout=5)
        print('Chrome connected'); break
    except:
        pass
else:
    print('Chrome failed!'); sys.exit(1)

resp = urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json')
pages = json.loads(resp.read())
page_ws = [p for p in pages if p.get('type') == 'page'][0]['webSocketDebuggerUrl']
ws = websocket.create_connection(page_ws, timeout=60)
msg_id = [0]

def js(expr, ap=False):
    msg_id[0] += 1
    ws.send(json.dumps({'id': msg_id[0], 'method': 'Runtime.evaluate',
                         'params': {'expression': expr, 'returnByValue': True, 'awaitPromise': ap}}))
    while True:
        r = json.loads(ws.recv())
        if r.get('id') == msg_id[0]:
            return r.get('result', {}).get('result', {}).get('value', '')

# Wait for SSO
for i in range(15):
    url = js('document.location.href')
    if url and 'alriyadh' in str(url) and 'loginApi' not in str(url): break
    time.sleep(3)

# Navigate to BLS
js(f'window.location.href = "{BLS_URL}"')
time.sleep(15)
print(f'URL: {js("document.location.href")[:100]}')

# Set dates and search
def set_date(field_id, value):
    r = js(f'''(function(){{
        var el = document.getElementById("{field_id}");
        if(!el) return "not found";
        el.focus();
        el.removeAttribute("readonly");
        var rect = el.getBoundingClientRect();
        return JSON.stringify({{x:rect.x+rect.width/2, y:rect.y+rect.height/2}});
    }})()''')
    if r and r != 'not found':
        pos = json.loads(r)
        time.sleep(0.3)
        ws.send(json.dumps({'id': msg_id[0]+100, 'method': 'Input.dispatchMouseEvent',
                             'params': {'type':'mousePressed','x':pos['x'],'y':pos['y'],'button':'left','clickCount':3}}))
        ws.recv()
        ws.send(json.dumps({'id': msg_id[0]+101, 'method': 'Input.dispatchMouseEvent',
                             'params': {'type':'mouseReleased','x':pos['x'],'y':pos['y'],'button':'left','clickCount':3}}))
        ws.recv()
        msg_id[0] += 102
        time.sleep(0.2)
        ws.send(json.dumps({'id': msg_id[0], 'method': 'Input.insertText', 'params': {'text': value}}))
        ws.recv()
        msg_id[0] += 1
        time.sleep(0.5)
        js('document.body.click()')
        time.sleep(1)

set_date('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content', '1447/04/13')
set_date('pt1:cBodFDC:r1:0:masteraTable:Todate::content', '1448/12/29')

# Click search
js('''(function(){
    var btn = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:search');
    if(btn) btn.click();
    return 'ok';
})()''')
time.sleep(15)

# Read data
info = js('''(function(){
    var table = null;
    var tables = document.querySelectorAll('table');
    tables.forEach(function(t){
        if(t.className && t.className.indexOf('af_table_data-table') >= 0){
            if(!table || t.rows.length > table.rows.length) table = t;
        }
    });
    if(!table) return JSON.stringify({rows:[],total:0,pages:0,page:0});
    var rows = [];
    for(var r=1; r<table.rows.length; r++){
        var tds = table.rows[r].querySelectorAll('td');
        var row = [], hasData = false;
        tds.forEach(function(td){
            var txt = (td.innerText||'').trim();
            row.push(txt);
            if(txt.length > 0) hasData = true;
        });
        if(hasData && row.length >= 10) rows.push(row);
    }
    var text = document.body.innerText;
    var m = text.match(/\\(([\\d,]+)-(\\d[\\d,]+)\\s+من\\s+(\\d[\\d,]+)/);
    var m2 = text.match(/العدد\\s*(\\d[\\d,]*)/);
    var total = 0;
    if(m) total = parseInt(m[3].replace(/,/g,''));
    else if(m2) total = parseInt(m2[1].replace(/,/g,''));
    if(!total) total = rows.length;
    var page = m ? parseInt(m[1].replace(/,/g,'')) : 1;
    var perPage = m ? parseInt(m[2].replace(/,/g,'')) - parseInt(m[1].replace(/,/g,'')) + 1 : rows.length;
    var pages = total > 0 ? Math.ceil(total / perPage) : 1;
    return JSON.stringify({rows:rows,total:total,pages:pages,page:page,perPage:perPage});
})()''')
print(f'Data: {info[:500]}')

# Now investigate pagination
pag_info = js('''(function(){
    var text = document.body.innerText;
    // Search for pagination patterns
    var patterns = [];
    var m1 = text.match(/\\(([\\d,]+)-(\\d[\\d,]+)\\s+من\\s+(\\d[\\d,]+)/);
    if(m1) patterns.push({pat:'range', vals:[m1[1],m1[2],m1[3]]});
    
    var m2 = text.match(/العدد\\s*(\\d[\\d,]*)/);
    if(m2) patterns.push({pat:'count', val:m2[1]});
    
    // Find all anchor elements with numbers
    var anchors = document.querySelectorAll('a');
    var numAnchors = [];
    for(var i=0; i<anchors.length; i++){
        var t = anchors[i].innerText.trim();
        var id = anchors[i].id;
        if(/^\\d+$/.test(t) && parseInt(t) <= 3000){
            numAnchors.push({text:t, id:id.substring(0,80), href:(anchors[i].getAttribute('href')||'').substring(0,50)});
        }
    }
    
    // Find ADF navigation components
    var adfNav = document.querySelectorAll('[class*="af_table"], [class*="af_panel"], [class*="navigation"]');
    var navInfo = [];
    for(var i=0; i<adfNav.length; i++){
        var el = adfNav[i];
        if(el.id) navInfo.push({id:el.id.substring(0,80), cls:el.className.substring(0,60), tag:el.tagName});
    }
    
    // Find buttons near table
    var btns = document.querySelectorAll('button, [role="button"], input[type="submit"]');
    var btnInfo = [];
    for(var i=0; i<btns.length; i++){
        var t = btns[i].innerText ? btns[i].innerText.trim() : btns[i].value;
        if(t) btnInfo.push({text:t.substring(0,30), id:(btns[i].id||'').substring(0,80)});
    }
    
    return JSON.stringify({patterns:patterns, numAnchors:numAnchors.slice(0,20), navInfo:navInfo.slice(0,10), btnInfo:btnInfo.slice(0,10)});
})()''')
print(f'\nPagination: {pag_info[:3000]}')

ws.close()
