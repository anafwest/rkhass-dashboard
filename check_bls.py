import json, urllib.request, websocket, time, sys
sys.stdout.reconfigure(encoding='utf-8')

PORT = 9227

data = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json').read())
ws_url = None
for t in data:
    if 'alriyadh' in t.get('url','') and t.get('type')=='page':
        ws_url = t['webSocketDebuggerUrl']
        print(f"Connected to: {t['url']}")
        break

if not ws_url:
    print("FATAL: no alriyadh tab")
    sys.exit(1)

ws = websocket.create_connection(ws_url, timeout=30)
_mid = [0]
def send(m,p=None):
    _mid[0]+=1; msg={'id':_mid[0],'method':m}
    if p: msg['params']=p
    ws.send(json.dumps(msg))
    while True:
        r=json.loads(ws.recv())
        if r.get('id')==_mid[0]: return r.get('result',{})

def js(e,ap=False):
    r=send('Runtime.evaluate',{'expression':e,'returnByValue':True,'awaitPromise':ap})
    v=r.get('result',{})
    if 'value' in v: return v['value']
    if v.get('subtype')=='error': return 'ERR:'+v.get('description','')
    return v

print(f"URL: {js('document.location.href')}")
print(f"Title: {js('document.title')}")
print(f"Body length: {js('document.body ? document.body.innerHTML.length : 0')}")

# Check what's on this BLS home page
body_text = js("document.body ? document.body.innerText.substring(0,2000) : 'no body'")
print(f"\nBody text:\n{body_text}")

# Check if there's data table
tables = js("""(function(){
    var ts = document.querySelectorAll('table');
    var res = [];
    for(var i=0; i<ts.length; i++){
        var t = ts[i];
        res.push({id:t.id, rows:t.rows.length, cls:(t.className||'').substring(0,40)});
    }
    return JSON.stringify(res);
})()""")
print(f"\nTables: {tables}")

# Check for navigation links
links = js("""(function(){
    var links = document.querySelectorAll('a');
    var res = [];
    for(var i=0; i<links.length; i++){
        var l = links[i];
        var t = l.textContent.trim();
        if(t.length > 2 && t.length < 60){
            res.push({text:t, href:l.href||'', id:l.id||''});
        }
    }
    return JSON.stringify(res);
})()""")
if links and 'ERR' not in str(links):
    ls = json.loads(links)
    print(f"\nLinks: {len(ls)}")
    for l in ls[:30]:
        print(f"  '{l['text']}' href={l['href'][:80]} id={l['id']}")

# Check for any menu/nav items
menu = js("""(function(){
    var items = document.querySelectorAll('[class*=menu], [class*=nav], [role=menu], [role=navigation], li[class*=item]');
    var res = [];
    for(var i=0; i<Math.min(items.length,20); i++){
        var t = items[i].textContent.trim().replace(/\\s+/g,' ').substring(0,60);
        res.push(t);
    }
    return JSON.stringify(res);
})()""")
print(f"\nMenu/nav items: {menu}")

ws.close()
