# -*- coding: utf-8 -*-
"""التحديث اليومي التلقائي لسحب بيانات BLS ورفعها لـ GitHub.
يُستدعى يومياً بواسطة Task Scheduler. يضمن: تشغيل Chrome نظيف -> SSO صامت -> 
سحب مع إعادة محاولة تلقائية -> رفع ناجح.
"""
import os, sys, subprocess, time, json, urllib.request, socket

sys.stdout.reconfigure(encoding='utf-8')
PROJECT_DIR = r"C:\Users\anaf\OneDrive - Riyadh Municipality\المستندات\Default Project\rkhass-dashboard"  # تُعدَّل إن اختلف المسار الفعلي
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = r"C:\Users\anaf\ScraperProfile"
PORT = 9222
SSO = "https://app.alriyadh.gov.sa/BLS/loginApi"
LOG = os.path.join(PROJECT_DIR, "daily_run.log")

def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)

def chrome_alive():
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=3):
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=3)
            return True
    except Exception:
        return False

def ensure_chrome():
    # إغلاق أي كروم سابق ثم تشغيل نظيف على SSO
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"],
                   capture_output=True)
    time.sleep(3)
    subprocess.Popen([CHROME,
                      f"--remote-debugging-port={PORT}",
                      "--remote-allow-origins=*",
                      "--no-first-run", "--disable-popup-blocking",
                      "--start-minimized",
                      f"--user-data-dir={PROFILE}", SSO])
    for _ in range(30):
        time.sleep(2)
        try:
            tabs = json.loads(urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/json", timeout=4).read())
            pages = [t for t in tabs if t.get("type") == "page"]
            if pages:
                log(f"Chrome جاهز: {pages[0]['url']}")
                return True
        except Exception:
            pass
    log("FATAL: لم يبدأ Chrome خلال 60 ثانية")
    return False

def run_scraper_with_retry():
    os.chdir(PROJECT_DIR)
    max_attempts = 10
    for attempt in range(1, max_attempts + 1):
        log(f"--- محاولة السحب {attempt}/{max_attempts} ---")
        with open("_bls_stdout.txt", "w") as so, open("_bls_stderr.txt", "w") as se:
            p = subprocess.Popen([sys.executable, "scraper.py"],
                                 stdout=so, stderr=se)
        while p.poll() is None:
            time.sleep(30)
        tail = ""
        try:
            lines = open("scraper_log.txt", encoding="utf-8",
                         errors="replace").read().splitlines()
            tail = "\n".join(lines[-5:])
        except Exception:
            pass
        log(f"الخروج: {p.returncode}\n{tail}")
        if "انتهت العملية بنجاح" in tail or "تم الرفع لـ GitHub" in tail:
            log("*** نجح السحب والرفع ***")
            return True
        time.sleep(5)
    return False

def main():
    log("===== بدء التحديث اليومي =====")
    if not ensure_chrome():
        log("انتهى: فشل تشغيل Chrome"); return 1
    time.sleep(8)  # مهلة لاستقرار الجلسة
    ok = run_scraper_with_retry()
    log("===== نهاية التحديث اليومي =====\n")
    return 0 if ok else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"خطأ عام: {e}")
        sys.exit(1)
