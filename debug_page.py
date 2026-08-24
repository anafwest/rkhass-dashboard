import json, urllib.request, websocket, time, sys
sys.stdout.reconfigure(encoding='utf-8')

PORT = 9222
data = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json').read())
ws_url = None
for t in data:
    if 'alriyadh' in t.get('url','') and t.get('type')=='page':
        ws_url = t['webSocketDebuggerUrl']; break
if not ws_url: print("FATAL"); sys.exit(1)

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

print(f"URL: {js('document.location.href')}")
print(f"Title: {js('document.title')}")
print(f"Body len: {js('document.body ? document.body.innerHTML.length : 0')}")

# Check ADF
print(f"ADF: {js('typeof AdfPage !== \"undefined\" ? \"yes\" : \"no\"')}")

# Check tables
tables = js("""(function(){
    var ts = document.querySelectorAll('table');
    var res = [];
    for(var i=0;i<ts.length;i++){
        var t = ts[i];
        if(t.rows.length > 1) res.push({id:t.id.substring(0,50), rows:t.rows.length, cls:(t.className||'').substring(0,40)});
    }
    return JSON.stringify(res);
})()""")
print(f"Tables with data: {tables}")

# Check if we're on login
body = js("document.body ? document.body.innerText.substring(0,500) : ''")
print(f"Body: {body[:300]}")

# Try reload
print("\nReloading page...")
js("location.reload()")
time.sleep(15)

print(f"After reload URL: {js('document.location.href')}")
print(f"ADF: {js('typeof AdfPage !== \"undefined\" ? \"yes\" : \"no\"')}")

tables2 = js("""(function(){
    var ts = document.querySelectorAll('table');
    var res = [];
    for(var i=0;i<ts.length;i++){
        var t = ts[i];
        if(t.rows.length > 1) res.push({id:t.id.substring(0,50), rows:t.rows.length});
    }
    return JSON.stringify(res);
})()""")
print(f"Tables: {tables2}")

body2 = js("document.body ? document.body.innerText.substring(0,500) : ''")
print(f"Body: {body2[:300]}")

# Check the page info for record count
page_info = js("""(function(){
    var text = document.body.innerText;
    var m = text.match(/\\(([\\d,]+)-(\\d[\\d,]+)\\s+من\\s+(\\d[\\d,]+)/);
    return m ? m[0] : 'not found';
})()""")
print(f"Page info: {page_info}")

ws.close()
