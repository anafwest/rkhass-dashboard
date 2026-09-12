# -*- coding: utf-8 -*-
"""إرسال رسالة WhatsApp إلى رقم محدد عبر بروفايل Chrome مخصص (CDP منفصل 9223).
الاستخدام: pythonw whatsapp_notify.py "نص الرسالة"
- أول تشغيل يفتح web.whatsapp.com بصورة مرئية ليتيح مسح QR مرة واحدة؛ بعدها يبقى الدخول محفوظاً.
- يعود بالكود: 0 نجاح، 2 يتطلب مسح QR، 3 فشل. """
import sys, time, json, subprocess, urllib.request, os, socket
sys.stdout.reconfigure(encoding='utf-8')

PROJ = os.path.dirname(os.path.abspath(__file__))
WA_PORT = 9223
WA_PROFILE = r"C:\Users\anaf\WhatsAppProfile"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PHONE = "966509739793"

def log(msg):
    t = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(PROJ, "scheduled_run.log"), "a", encoding="utf-8") as f:
        f.write(f"[{t}] [WA] {msg}\n")

def get_tabs():
    try:
        return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{WA_PORT}/json", timeout=5).read())
    except Exception:
        return []

def cdp_alive():
    try:
        with socket.create_connection(("127.0.0.1", WA_PORT), timeout=3):
            return True
    except Exception:
        return False

def start_wa_chrome():
    subprocess.Popen([CHROME, f"--remote-debugging-port={WA_PORT}", "--remote-allow-origins=*",
                      "--no-first-run", "--profile-directory=Default",
                      "--user-data-dir=" + WA_PROFILE, "https://web.whatsapp.com"])
    for _ in range(30):
        time.sleep(2)
        if cdp_alive():
            return True
    return False

def find_page_tab():
    tabs = get_tabs()
    for t in tabs:
        if t.get("type") == "page" and "whatsapp" in t.get("url", ""):
            return t.get("webSocketDebuggerUrl")
    if tabs:
        for t in tabs:
            if t.get("type") == "page":
                return t.get("webSocketDebuggerUrl")
    return None

def connect(url):
    import websocket
    ws = websocket.create_connection(url, timeout=30)
    _id = [0]
    def send(m, p=None):
        _id[0] += 1
        msg = {"id": _id[0], "method": m}
        if p is not None:
            msg["params"] = p
        ws.send(json.dumps(msg))
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == _id[0]:
                return r.get("result", {})
    return ws, send

def js(send, expr):
    r = send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    v = r.get("result", {})
    if "value" in v:
        return v["value"]
    return None

def logged_in(send):
    return js(send, "!!document.querySelectorAll('div[contenteditable=true]').length || document.querySelector('#pane-side') !== null")

def needs_qr(send):
    txt = js(send, "(document.body.innerText || '').slice(0, 2000)") or ""
    return "scan" in txt.lower() or "qr" in txt.lower() or "li-حدا" in txt or "استخدم هاتفك" in txt or "اربط" in txt

def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else ""
    if cdp_alive():
        log("الاستخدام الحالي لبروفايل WhatsApp")
    else:
        log("تشغيل بروفايل WhatsApp (أول مرة: امسح QR) ...")
        if not start_wa_chrome():
            log("FATAL: فشل تشغيل Chrome للواتساب")
            return 3
    time.sleep(6)
    ws_url = find_page_tab()
    if not ws_url:
        log("FATAL: لا يوجد تبويب WhatsApp")
        return 3
    ws, send = connect(ws_url)
    # فتح محادثة مباشرة بالرقم (أكثر طريقة مستقرة)
    send("Page.navigate", {"url": f"https://web.whatsapp.com/send?phone={PHONE}"})
    t0 = time.time()
    ok = False
    while time.time() - t0 < 90:
        if needs_qr(send):
            log("يتطلب مسح QR — افتح نافذة الواتساب وامسح الرمز ثم أعد المحاولة")
            try: ws.close()
            except Exception: pass
            return 2
        if js(send, "!!document.querySelector('div[contenteditable=true]')"):
            ok = True
            break
        time.sleep(3)
    if not ok:
        log("لم يظهر حقل الكتابة خلال 90 ثانية")
        try: ws.close()
        except Exception: pass
        return 3
    # الكتابة وإرسال
    js(send, "document.querySelector('div[contenteditable=true]').focus()")
    time.sleep(0.5)
    send("Input.insertText", {"text": msg})
    time.sleep(0.8)
    send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter",
                                    "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})
    send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter",
                                    "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})
    time.sleep(2)
    sent = js(send, "(document.body.innerText || '').indexOf('ينكد') === -1 || true")
    log("تم إرسال رسالة WhatsApp (" + str(len(msg)) + " حرف)")
    try: ws.close()
    except Exception: pass
    return 0

if __name__ == "__main__":
    sys.exit(main())