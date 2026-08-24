import json, urllib.request, websocket, time, sys
sys.stdout.reconfigure(encoding='utf-8')

PORT = 9226
data = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json').read())
ws_url = None
for t in data:
    if 'alriyadh' in t.get('url',''):
        ws_url = t['webSocketDebuggerUrl']; break
ws = websocket.create_connection(ws_url, timeout=15)
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

print('Waiting for ADF...')
time.sleep(10)
print(f'URL: {js("document.location.href")}')

r = js('typeof AdfPage !== "undefined" ? "ADF OK" : "NO ADF"')
print(f'ADF: {r}')

js('location.reload()')
time.sleep(12)
r = js('typeof AdfPage !== "undefined" ? "ADF OK" : "NO ADF"')
print(f'After reload ADF: {r}')
print(f'URL: {js("document.location.href")}')
print(f'Title: {js("document.title")}')

if 'OK' in str(r):
    btns = js('(function(){var bs=document.querySelectorAll("button[id*=MenuButton],button[id*=btn]");var res=[];for(var i=0;i<bs.length;i++){var rect=bs[i].getBoundingClientRect();res.push({id:bs[i].id,text:bs[i].textContent.trim().substring(0,40),x:Math.round(rect.x),y:Math.round(rect.y),w:Math.round(rect.width),h:Math.round(rect.height)});}return JSON.stringify(res);})()')
    if btns and 'ERR' not in str(btns):
        bs = json.loads(btns)
        print(f'\nButtons: {len(bs)}')
        for b in bs:
            vis = 'VIS' if b['w']>0 and b['h']>0 else 'hid'
            print(f'  [{vis}] {b["id"]}: "{b["text"]}" ({b["w"]}x{b["h"]})')

    pos = js('(function(){var b=document.getElementById("pt1:MenuButtonFORM_APP");if(!b)return "not found";var r=b.getBoundingClientRect();return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2),w:Math.round(r.width),h:Math.round(r.height)});})()')
    print(f'\nFORM_APP: {pos}')

ws.close()
