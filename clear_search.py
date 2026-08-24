import json, urllib.request, websocket, time, sys
sys.stdout.reconfigure(encoding='utf-8')

PORT = 9227
data = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json').read())
ws_url = None
for t in data:
    if 'alriyadh' in t.get('url','') and t.get('type')=='page':
        ws_url = t['webSocketDebuggerUrl']; break
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

# Step 1: Check current filter values
filters = js("""(function(){
    var inputs = document.querySelectorAll('input[type=text], select');
    var res = [];
    for(var i=0;i<inputs.length;i++){
        var inp = inputs[i];
        if(inp.value && inp.value.length > 0){
            res.push({id:inp.id, name:inp.name, value:inp.value, placeholder:inp.placeholder||''});
        }
    }
    return JSON.stringify(res);
})()""")
print(f"Active filters: {filters}")

# Step 2: Check total records info
records_info = js("""(function(){
    var text = document.body.innerText;
    var match = text.match(/(\\d+\\-\\d+) من (\\d+)/);
    var match2 = text.match(/(\\d+)\\s*(من العناصر|سجل|نتيجة)/);
    return JSON.stringify({match1: match?match[0]:null, match2: match2?match2[0]:null, pageText: text.substring(text.indexOf('الصفحة'), text.indexOf('الصفحة')+100)});
})()""")
print(f"Records: {records_info}")

# Step 3: Clear all filter inputs and click search
print("\n--- Clearing filters and searching ---")
clear_result = js("""(function(){
    // Find all input text fields in the filter area and clear them
    var filterInputs = document.querySelectorAll('input[type=text]');
    var cleared = [];
    for(var i=0;i<filterInputs.length;i++){
        var inp = filterInputs[i];
        if(inp.id && (inp.id.indexOf('it') >= 0 || inp.id.indexOf('Input') >= 0)){
            if(inp.value){
                cleared.push(inp.id + '=' + inp.value);
                inp.value = '';
            }
        }
    }
    return JSON.stringify({cleared: cleared});
})()""")
print(f"Cleared: {clear_result}")

# Click the search button
print("\n--- Clicking Search button ---")
search_click = js("""(function(){
    var btn = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:search');
    if(!btn) return 'search button not found';
    btn.click();
    return 'clicked search';
})()""")
print(f"Search: {search_click}")

# Wait for ADF AJAX
time.sleep(5)

# Check results
records_after = js("""(function(){
    var text = document.body.innerText;
    var idx = text.indexOf('من العناصر');
    if(idx < 0) idx = text.indexOf('العناصر');
    var snippet = idx >= 0 ? text.substring(Math.max(0,idx-50), idx+30) : 'not found';
    
    // Count data rows
    var dataRows = document.querySelectorAll('tr.af_table_data-row');
    
    // Also try the table directly
    var tables = document.querySelectorAll('table');
    var maxRows = 0;
    tables.forEach(function(t){if(t.rows.length>maxRows) maxRows=t.rows.length;});
    
    return JSON.stringify({snippet: snippet, dataRows: dataRows.length, maxTableRows: maxRows});
})()""")
print(f"After search: {records_after}")

ws.close()
