import json, websocket, time

ws_url = 'ws://127.0.0.1:9222/devtools/page/F6A18B5176C3FBC4A0E9FC69E03C726A'
ws = websocket.create_connection(ws_url, timeout=10)

def js(expr):
    ws.send(json.dumps({'id':1,'method':'Runtime.evaluate','params':{'expression':expr,'returnByValue':True}}))
    r = json.loads(ws.recv())
    return r.get('result',{}).get('result',{}).get('value','')

# Check all table classes
tables = js("""(function(){
    var tables = document.querySelectorAll('table');
    var result = [];
    tables.forEach(function(t){
        result.push({
            id: t.id || '',
            cls: t.className || '',
            rows: t.rows ? t.rows.length : 0
        });
    });
    return JSON.stringify(result);
})()""")
items = json.loads(tables)
for t in items:
    if t['rows'] > 0:
        print(f"Table id={t['id'][:50]:50} cls={t['cls'][:40]:40} rows={t['rows']}")

# Check how READ_DATA_JS works with the existing table
# The data div is: pt1:cBodFDC:r1:0:masteraTable:t1::db
data_div = js("""(function(){
    var div = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::db');
    if(!div) return 'div not found';
    var table = div.querySelector('table');
    if(!table) return 'table in div not found';
    return 'found table with ' + table.rows.length + ' rows, class=' + (table.className||'none');
})()""")
print(f"\nData div: {data_div}")

# Check FROM and TO date values
from_date = js("document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Fromdate::content')?.value || 'EMPTY'")
to_date = js("document.getElementById('pt1:cBodFDC:r1:0:masteraTable:Todate::content')?.value || 'EMPTY'")
print(f"\nFrom date: {from_date}")
print(f"To date: {to_date}")

# Check total from the page
total_el = js("document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::nb_rng')?.innerText || 'not found'")
print(f"Total display: {total_el}")

# Test updated READ_DATA_JS that finds any data table
updated_read = js("""(function(){
    // Try original class
    var table = null;
    document.querySelectorAll('table').forEach(function(t){
        if(t.className && t.className.indexOf('af_table_data-table') >= 0){
            if(!table || t.rows.length > table.rows.length) table = t;
        }
    });
    if(!table){
        // Try finding table in data div
        var div = document.getElementById('pt1:cBodFDC:r1:0:masteraTable:t1::db');
        if(div) table = div.querySelector('table');
    }
    if(!table) return JSON.stringify({rows:[],total:0,pages:0});
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
    return JSON.stringify({rows:rows, rowCount: table.rows.length});
})()""")
info = json.loads(updated_read)
print(f"\nUpdated read: {len(info.get('rows',[]))} rows, table has {info.get('rowCount',0)} rows")

ws.close()
