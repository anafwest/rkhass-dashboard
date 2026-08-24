import json, urllib.request, websocket, time, sys
sys.stdout.reconfigure(encoding='utf-8')
data = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json',timeout=5).read())
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

print(f"URL: {js('document.location.href')}")

# Check all filters
r = js('(function(){var res=[];var inputs=document.querySelectorAll("input[type=text]");for(var i=0;i<inputs.length;i++){if(inputs[i].value)res.push({id:inputs[i].id.substring(0,60),val:inputs[i].value.substring(0,80)});}return JSON.stringify(res);})()')
print(f"Filters: {r}")

# Check page info
r = js('(function(){var t=document.body.innerText;var m=t.match(/\\(([\\d,]+)-(\\d[\\d,]+)\\s+من\\s+(\\d[\\d,]+)/);return m?m[0]:"not found";})()')
print(f"Page: {r}")

# Click reset to clear all filters
js('(function(){var b=document.getElementById("pt1:cBodFDC:r1:0:masteraTable:reset");if(b){b.click();return "clicked";}return "not found";})()')
time.sleep(8)

# Check after reset
r = js('(function(){var res=[];var inputs=document.querySelectorAll("input[type=text]");for(var i=0;i<inputs.length;i++){if(inputs[i].value)res.push({id:inputs[i].id.substring(0,60),val:inputs[i].value.substring(0,80)});}return JSON.stringify(res);})()')
print(f"After reset filters: {r}")

r = js('(function(){var t=document.body.innerText;var m=t.match(/\\(([\\d,]+)-(\\d[\\d,]+)\\s+من\\s+(\\d[\\d,]+)/);return m?m[0]:"not found";})()')
print(f"After reset page: {r}")

# Click search
js('(function(){var b=document.getElementById("pt1:cBodFDC:r1:0:masteraTable:search");if(b){b.click();return "clicked";}return "not found";})()')
time.sleep(10)

# Check after search
r = js('(function(){var res=[];var inputs=document.querySelectorAll("input[type=text]");for(var i=0;i<inputs.length;i++){if(inputs[i].value)res.push({id:inputs[i].id.substring(0,60),val:inputs[i].value.substring(0,80)});}return JSON.stringify(res);})()')
print(f"After search filters: {r}")

r = js('(function(){var t=document.body.innerText;var m=t.match(/\\(([\\d,]+)-(\\d[\\d,]+)\\s+من\\s+(\\d[\\d,]+)/);return m?m[0]:"not found";})()')
print(f"After search page: {r}")

# Count rows
r = js('(function(){var tables=document.querySelectorAll("table");var max=0;tables.forEach(function(t){if(t.className&&t.className.indexOf("af_table_data-table")>=0&&t.rows.length>max)max=t.rows.length;});return "maxRows="+max;})()')
print(f"Data table: {r}")

# Get body text snippet
r = js('document.body.innerText.substring(0,1500)')
print(f"Body: {r[:800]}")

ws.close()
