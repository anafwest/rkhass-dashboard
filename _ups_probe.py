# -*- coding: utf-8 -*-
"""فحص بوابة UPS: ترتيب الصفحة، وجود فلاتر تاريخ أو بحث."""
import ssl, os, urllib3, time, json, sys, subprocess
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
import websocket, urllib.request

PORT = 9222
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE_DIR = r"C:\Users\anaf\ScraperProfile"
BASE_URL = "https://ups-backoffice.alriyadh.gov.sa/ar/building-license-department?activeTab=requests"

def get_tabs():
    try: return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json",timeout=5).read())
    except: return []

def connect_ws(url):
    ws = websocket.create_connection(url, timeout=30)
    _id=[0]
    def send(m,p=None):
        _id[0]+=1
        msg={"id":_id[0],"method":m}
        if p: msg["params"]=p
        ws.send(json.dumps(msg))
        while True:
            r=json.loads(ws.recv())
            if r.get("id")==_id[0]: return r.get("result",{})
    return ws,send

def js(send,expr):
    r=send("Runtime.evaluate",{"expression":expr,"returnByValue":True})
    v=r.get("result",{})
    if "value" in v: return v["value"]
    return "ERR:"+v.get("description","")

tabs=get_tabs()
ws_url=None
for t in tabs:
    if t.get("type")=="page" and "ups-backoffice" in t.get("url",""):
        ws_url=t.get("webSocketDebuggerUrl"); break
if not ws_url:
    import urllib.parse
    try:
        req=urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?{urllib.parse.quote(BASE_URL,safe='')}",method="PUT")
        nb=json.loads(urllib.request.urlopen(req,timeout=10).read())
        ws_url=nb.get("webSocketDebuggerUrl")
    except Exception as e:
        subprocess.Popen([CHROME_PATH,f"--remote-debugging-port={PORT}","--remote-allow-origins=*",
                          "--no-first-run","--start-minimized",f"--user-data-dir={PROFILE_DIR}",BASE_URL])
        for i in range(30):
            time.sleep(2)
            for t in get_tabs():
                if t.get("type")=="page" and "ups-backoffice" in t.get("url",""):
                    ws_url=t.get("webSocketDebuggerUrl"); break
            if ws_url: break
time.sleep(8)
ws,send=connect_ws(ws_url)
send("Page.navigate",{"url":BASE_URL})
time.sleep(6)
READ=(lambda e: json.loads(js(send,e)))
info=READ("(function(){var result={page:0,total:0,rows:[]};var txt=document.body.innerText;var m=txt.match(/الصفحة (\\d+) من (\\d+)/);if(m){result.page=parseInt(m[1]);result.total=parseInt(m[2]);}var trs=document.querySelectorAll('table tbody tr');trs.forEach(function(tr){var tds=tr.querySelectorAll('td');if(tds.length>=7){var row=[tds[0].innerText.trim(),tds[1].innerText.trim(),tds[2].innerText.trim(),tds[3].innerText.trim(),tds[4].innerText.trim(),tds[5].innerText.trim(),tds[6].innerText.trim()];if(row[0]&&row[0].length>3)result.rows.push(row);}});return JSON.stringify(result);})()")
print("PAGE",info["page"],"OF",info["total"],"rows",len(info["rows"]))
for r in info["rows"][:6]: print(r)
ctl=READ("(function(){var out=[];document.querySelectorAll('input,select').forEach(function(e){out.push(e.tagName+':'+(e.type||'')+':'+(e.id||'')+':'+(e.placeholder||'').slice(0,40)+':'+(e.name||''));});return JSON.stringify(out);})()")
print("CONTROLS:",ctl)
bs=READ("(function(){var out=[];document.querySelectorAll('button,a').forEach(function(e){var t=(e.innerText||'').trim();if(t&&t.length<30)out.push(t);});return JSON.stringify([...new Set(out)].slice(0,60));})()")
print("BUTTONS:",bs)
try: ws.close()
except: pass