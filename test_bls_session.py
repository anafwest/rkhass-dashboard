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
        resp = urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/version', timeout=5)
        print('Chrome connected'); break
    except:
        print(f'Waiting... ({i})')
else:
    print('Chrome failed!'); sys.exit(1)

resp = urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json')
pages = json.loads(resp.read())
page_ws = [p for p in pages if p.get('type') == 'page'][0]['webSocketDebuggerUrl']
ws = websocket.create_connection(page_ws, timeout=60)
msg_id = [0]

def js(expr, await_promise=False):
    msg_id[0] += 1
    params = {'expression': expr, 'returnByValue': True}
    if await_promise:
        params['awaitPromise'] = True
    ws.send(json.dumps({'id': msg_id[0], 'method': 'Runtime.evaluate', 'params': params}))
    while True:
        r = json.loads(ws.recv())
        if r.get('id') == msg_id[0]:
            return r.get('result', {}).get('result', {}).get('value', '')

# Wait for SSO
for i in range(15):
    url = js('document.location.href')
    if url and 'alriyadh' in str(url) and 'loginApi' not in str(url):
        break
    time.sleep(3)
print(f'SSO URL: {js("document.location.href")[:100]}')

# Navigate to BLS
print('\n--- Navigating to BLS loginApi ---')
js(f'window.location.href = "{BLS_URL}"')
for i in range(15):
    time.sleep(3)
    url = js('document.location.href')
    print(f'BLS check {i}: {str(url)[:100]}')
    if 'BLS' in str(url) and 'loginApi' not in str(url):
        break

url = js('document.location.href')
print(f'\nFinal BLS URL: {url[:100]}')
has_adf = js('typeof AdfPage !== "undefined" ? "yes" : "no"')
print(f'ADF: {has_adf}')

# Check for UBS button on SSO home or BLS home
ubs = js('var b = document.getElementById("pt1:MenuButtonUBS"); b ? "found" : "not found"')
print(f'UBS button: {ubs}')

# Now navigate to BLS8510
print('\n--- Navigating to BLS8510 ---')
js('''(function(){
    var b = document.getElementById("pt1:MenuButtonUBS");
    if(b) { b.click(); return "clicked UBS"; }
    return "no UBS button, trying direct nav";
})()''')
time.sleep(3)

# Try finding BLS8510 link
js('''(function(){
    var links = document.querySelectorAll('a, span, div');
    for(var i=0; i<links.length; i++){
        if(links[i].innerText && links[i].innerText.indexOf('BLS8510') >= 0){
            links[i].click();
            return "clicked BLS8510";
        }
    }
    return "no BLS8510 found";
})()''')
time.sleep(5)

url = js('document.location.href')
print(f'URL: {url[:100]}')

# Check for data table
read_js = '''(function(){
    var tbl = document.querySelector('[id*="masteraTable"], [id*="data_table"], table[role="grid"]');
    if(!tbl) return JSON.stringify({found: false, bodySnippet: document.body.innerText.substring(0, 300)});
    var rows = tbl.querySelectorAll('tr');
    return JSON.stringify({found: true, rows: rows.length, id: tbl.id});
})()'''
result = js(read_js)
print(f'Table check: {result[:300]}')

ws.close()
