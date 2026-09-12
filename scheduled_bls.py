# -*- coding: utf-8 -*-
"""الغلاف المُجدوَل لسحب BLS (تُستدعى من Task Scheduler يومياً 08:00/11:00/14:00).
- تشغيل Chrome نظيف على CDP 9222 دون قتل متصفح المستخدم العادي.
- تشغيل run_fast.py (المحرك الموثوق) مع إعادة محاولة.
- قفل لمنع تشغيل متزامن، وتسجيل مفصّل، وإبقاء الجهاز مستيقظاً أثناء العمل."""
import os, sys, subprocess, time, socket, signal, json, urllib.request

try:
    if sys.stdout:
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
CREATE_NO_WINDOW = 0x08000000
PROJ = r"C:\Users\anaf\OneDrive - Riyadh Municipality\المستندات\Default Project\rkhass-dashboard"
PY   = r"C:\Users\anaf\AppData\Local\Programs\Python\Python312\python.exe"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = r"C:\Users\anaf\ScraperProfile"
PORT = 9222
SSO = "https://app.alriyadh.gov.sa/BLS/loginApi"
LOG = os.path.join(PROJ, "scheduled_run.log")
LOCK = os.path.join(PROJ, "bls_sched.lock")
ENGINE = os.path.join(PROJ, "run_fast.py")
SCRA_LOG = os.path.join(PROJ, "scraper_log.txt")
CONFIG = os.path.join(PROJ, "notify_config.json")

def telegram_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
        if isinstance(cfg, dict) and cfg.get("telegram", {}).get("bot_token") and cfg.get("telegram", {}).get("chat_id"):
            return cfg["telegram"]["bot_token"].strip(), str(cfg["telegram"]["chat_id"]).strip()
    except Exception:
        pass
    return None, None

def telegram_send(msg):
    token, chat_id = telegram_config()
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": msg}).encode("utf-8")
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        ok = bool(resp.get("ok"))
        log("إشعار Telegram: " + ("تم الإرسال" if ok else f"فشل ({resp.get('description','')})"))
        return ok
    except Exception as e:
        log(f"Telegram خطأ: {e}")
        return False

def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    try:
        print(line, flush=True)
    except Exception:
        pass

def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False

def acquire_lock():
    try:
        if os.path.exists(LOCK):
            with open(LOCK) as f:
                old = int(f.read().strip() or "0")
            if old and pid_alive(old):
                log("توجد عملية سحب تعمل مسبقاً — تخطي هذه الجولة (قفل)")
                return False
        with open(LOCK, "w") as f:
            f.write(str(os.getpid()))
        return True
    except Exception:
        return True

def release_lock():
    try:
        if os.path.exists(LOCK):
            with open(LOCK) as f:
                me = f.read().strip()
            if str(os.getpid()) == me:
                os.remove(LOCK)
    except Exception:
        pass

def cdp_alive():
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=3):
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=3)
            return True
    except Exception:
        return False

def kill_profile_chrome():
    """قتل عمليات Chrome التي تستخدم بروفايل السحب فقط (لا يمس متصفح المستخدم)."""
    try:
        r = subprocess.run(
            ["powershell","-NoProfile","-Command",
             "Get-CimInstance Win32_Process -Filter \\\"Name='chrome.exe'\\\" | "
             "Where-Object { $_.CommandLine -like '*ScraperProfile*' } | "
             "ForEach-Object { $_.ProcessId }"],
            capture_output=True, text=True, timeout=30, creationflags=CREATE_NO_WINDOW)
        ids = [int(x) for x in r.stdout.split() if x.strip().isdigit()]
        for pid in ids:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, creationflags=CREATE_NO_WINDOW)
        if ids:
            time.sleep(3)
    except Exception:
        pass

def start_chrome():
    subprocess.Popen([CHROME, f"--remote-debugging-port={PORT}",
                      "--remote-allow-origins=*", "--no-first-run",
                      "--disable-popup-blocking", "--start-minimized",
                      f"--user-data-dir={PROFILE}", SSO])
    for _ in range(30):
        time.sleep(2)
        if cdp_alive():
            return True
    return False

def ensure_chrome():
    if cdp_alive():
        log("Chrome يعمل على 9222 — استخدام الحالي")
        return True
    kill_profile_chrome()
    log("تشغيل Chrome ببروفايل السحب...")
    return start_chrome()

def scraper_finished():
    try:
        lines = open(SCRA_LOG, encoding="utf-8", errors="replace").read().splitlines()
        tail = "\n".join(lines[-6:])
        return "انتهت القراءة بنجاح" in tail or "تم الرفع لـ GitHub" in tail
    except Exception:
        return False

def login_blocked():
    """كشف حالات تتطلب تدخلاً يدوياً (رمز تحقق / تسجيل دخول) بدل التكرار الأعمى."""
    try:
        lines = open(SCRA_LOG, encoding="utf-8", errors="replace").read().splitlines()
        tail = "\n".join(lines[-40:]).lower()
        for kw in ("رمز التحقق", "رمز التحقق؟", "verification", "otp", "verify code",
                   "تسجيل الدخول", "log in", "sign in", "انتهت الجلسة", "انتهت صلاحية الجلسة",
                   "يجب إعادة تسجيل الدخول"):
            if kw.lower() in tail:
                return kw
    except Exception:
        pass
    return False

def page_text():
    """قراءة نص التبويب الحالي عبر CDP لاستخراج رمز التحقق الظاهر على الشاشة."""
    try:
        tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=5).read())
        ws_url = None
        for t in tabs:
            if t.get("type") == "page":
                ws_url = t.get("webSocketDebuggerUrl")
                break
        if not ws_url:
            return ""
        import websocket
        ws = websocket.create_connection(ws_url, timeout=15)
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                            "params": {"expression": "document.body ? document.body.innerText : ''",
                                       "returnByValue": True}}))
        r = json.loads(ws.recv())
        ws.close()
        return (r.get("result", {}).get("result", {}) or {}).get("value", "") or ""
    except Exception:
        return ""

def extract_otp():
    """استخراج رمز التحقق المعروض على الشاشة (إن وُجد) لعرضه للمستخدم."""
    import re
    txt = page_text() or ""
    if not txt:
        return ""
    patterns = (
        r"رمز\s*التحقق\s*[:：]?\s*(\d{4,6})",
        r"رمز\s*[:：]?\s*(\d{4,6})",
        r"كود\s*[:：]?\s*(\d{4,6})",
        r"(?:verification\s*code|code)\s*[:：]?\s*(\d{4,6})",
        r"التحقق\s*[:：]?\s*(\d{4,6})",
    )
    for pat in patterns:
        m = re.search(pat, txt)
        if m:
            return m.group(1)
    return ""

def notify(msg):
    """تنبيه فوري: فقاعة Windows + Telegram + WhatsApp (بقدر التهيئة)."""
    ps = ("Add-Type -AssemblyName System.Windows.Forms;"
          "Add-Type -AssemblyName System.Drawing;"
          "$n = New-Object System.Windows.Forms.NotifyIcon;"
          "$n.Icon = [System.Drawing.SystemIcons]::Warning;"
          "$n.Visible = $true;"
          "$n.ShowBalloonTip(15000, 'BLS Autoupdate', '$msg',"
          " [System.Windows.Forms.ToolTipIcon]::Warning);"
          "Start-Sleep 8; $n.Dispose()")
    subprocess.Popen(["powershell", "-NoProfile", "-Command", ps], creationflags=CREATE_NO_WINDOW)
    telegram_send(msg)
    try:
        subprocess.run([PY, os.path.join(PROJ, "whatsapp_notify.py"), msg],
                       capture_output=True, timeout=150, creationflags=CREATE_NO_WINDOW)
    except Exception:
        pass

def run_ups():
    """تحديث UPS بالتوازي مع الجدولة (أفضل جهد، لا يمنع نجاح الجولة الأساسية)."""
    log("بدء سحب UPS...")
    try:
        r = subprocess.run([PY, os.path.join(PROJ, "ups_scraper.py")], cwd=PROJ,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=3600, creationflags=CREATE_NO_WINDOW)
        tail = open(os.path.join(PROJ, "ups_scraper_log.txt"), encoding="utf-8",
                    errors="replace").read()
        ok = "انتهت عملية UPS" in tail and r.returncode == 0
        log(f"نتيجة UPS: {'نجاح' if ok else 'فشل'}")
        return ok
    except Exception as e:
        log(f"UPS خطأ: {e}")
        return False

def run_engine(attempt):
    log(f"--- محاولة السحب {attempt} ---")
    so = open(os.path.join(PROJ, "_sched_out.txt"), "w", encoding="utf-8")
    se = open(os.path.join(PROJ, "_sched_err.txt"), "w", encoding="utf-8")
    try:
        p = subprocess.Popen([PY, ENGINE], cwd=PROJ, stdout=so, stderr=se, creationflags=CREATE_NO_WINDOW)
    finally:
        so.close(); se.close()
    t0 = time.time()
    while p.poll() is None and time.time() - t0 < 5400:
        time.sleep(30)
    if p.poll() is None:
        log("انتهت مهلة 90 دقيقة — قتل العملية")
        p.kill()
        return False, False, False
    rc = p.returncode
    ok = scraper_finished()
    # نجاح صريح: كود 0 + علامة الاكتمال
    if rc == 0 and ok:
        log("نجاح السحب والرفع")
        return True, True, True
    log(f"الخروج برمز {rc}; اكتمل الملف: {ok}; منتهي: {scraper_finished()}")
    return True, ok, False

def main():
    if "--check" in sys.argv:
        ok = ensure_chrome()
        log(f"فحص Chrome: {'نجاح' if ok else 'فشل'}")
        return 0 if ok else 1
    log("===== جولة السحب المجدولة =====")
    if not acquire_lock():
        return 0
    orig_sleep = get_standby_ac_minutes()
    try:
        power_override("0")  # لا سكون على التيار أثناء السحب
        ok_any = False
        if ensure_chrome():
            time.sleep(8)
            for attempt in range(1, 4):
                _, finished, good = run_engine(attempt)
                if good:
                    ok_any = True
                    break
                block = login_blocked()
                if block:
                    code = extract_otp()
                    if code:
                        log(f"توقف: مطلوب رمز تحقق — الرمز الظاهر على الشاشة: {code}")
                        notify(f"رمز التحقق الظاهر على الشاشة: {code} — أكمل الإدخال في النافذة")
                    else:
                        log(f"توقف: مطلوب رمز تحقق ({block}) — يوصلك على الجوال؛ راسلني بالرمز لإدخاله أو أدخله أنت في النافذة المفتوحة")
                        notify("BLS يطلب رمز التحقق — يظهر الرمز على جوالك/الشاشة؛ أرسله لي أو أدخله في النافذة")
                    break
                if attempt < 3:
                    log("إعادة محاولة بعد 30 ثانية...")
                    time.sleep(30)
                    ensure_chrome()
ups_ok = run_ups()
            notify(f"{'✅ BLS نجحت' if ok_any else '⚠️ BLS: ' + ('تحتاج رمزاً' if login_blocked() else 'فشلت')} | "
                   f"{'✅ UPS نجحت' if ups_ok else '⚠️ UPS لم تُحدَّث'} | جولة {time.strftime('%d/%m %H:%M')}")
        else:
            log("FATAL: فشل تشغيل Chrome")
            notify("تعذر تشغيل Chrome لجولة BLS")
        log("===== نهاية الجولة =====\n")
    finally:
        power_override(str(orig_sleep))  # استعادة الوضع الأصلي (قيمة الجهاز الحقيقية)
        release_lock()
    return 0 if ok_any else 1

def get_standby_ac_minutes():
    """قراءة قيمة "النوم عند التيار" الحالية (بالدقائق) لاستعادتها لاحقاً."""
    import re as _re
    try:
        r = subprocess.run(["powercfg","/query","SCHEME_CURRENT","SUB_SLEEP","STANDBYIDLE"],
                           capture_output=True, text=True, timeout=20, creationflags=CREATE_NO_WINDOW)
        m = _re.search(r"AC Power Setting Index:\s*0x([0-9a-fA-F]+)", r.stdout)
        if m:
            return int(m.group(1), 16)
    except Exception:
        pass
    return 180

def power_override(minutes):
    """إبقاء الجهاز مستيقظاً أثناء الجولة ثم استعادته."""
    try:
        subprocess.run(["powercfg","/change","standby-timeout-ac",str(minutes)],
                       capture_output=True, timeout=20, creationflags=CREATE_NO_WINDOW)
    except Exception:
        pass

if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        log(f"خطأ عام: {e}")
        sys.exit(1)