# -*- coding: utf-8 -*-
"""إتمام سحب BLS8510 عبر زر التصدير (b11): انتظار اكتمال التنزيل، تحويل الـ HTML-xls
إلى data.xlsx بنفس أعمدة scraper.py، حفظ وحفظ git/رفع."""
import ssl, os, urllib3, time, json, sys, glob, re, html as html_mod, subprocess
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime
import pandas as pd

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)
DL = r"C:\Users\anaf\AppData\Local\Temp\opencode\bls_export"
COLS = ["طلب الخدمة","السنة","نوع الخدمة","وصف المرحلة","الجهة","تاريخ الطلب",
        "تاريخ الطلب ميلادي","رقم الرخصة","سنة الرخصة","نوع الهوية","المالك",
        "رقم الهوية","تاريخ المراجعة","تاريخ المراجعة ميلادي","رقم الطلب"]
EXPECTED_TOTAL = 12562

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("scraper_log.txt","a",encoding="utf-8") as f: f.write(f"[{ts}] {msg}\n")
    print(f"[{ts}] {msg}", flush=True)

def wait_download(timeout_s=2400):
    t0 = time.time(); last = None; last_chg = time.time()
    while time.time() - t0 < timeout_s:
        files = glob.glob(os.path.join(DL, "*"))
        done = [f for f in files if not f.endswith(".crdownload")]
        if done:
            return sorted(done)[0]
        crumbs = [f for f in files if f.endswith(".crdownload")]
        if crumbs:
            sz = os.path.getsize(crumbs[0])
            if sz != last:
                last = sz; last_chg = time.time()
                log(f"التنزيل جارٍ: {sz//1024} KB")
            elif time.time() - last_chg > 600:
                log("التنزيل متوقف 10 دقائق — إنهاء الانتظار")
                return sorted(crumbs)[0]
        time.sleep(45)
    logs = glob.glob(os.path.join(DL, "*"))
    if logs:
        return sorted(logs)[0]
    return None

def parse_xls(path):
    data = open(path, encoding="utf-8", errors="replace").read()
    trs = re.findall(r"<tr[^>]*>(.*?)</tr>", data, re.DOTALL)
    rows = []
    for tr in trs:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.DOTALL)
        if len(tds) != 15:
            continue
        cells = []
        for td in tds:
            txt = re.sub(r"<[^>]+>", "", td)
            txt = html_mod.unescape(txt)
            txt = re.sub(r"\s+", " ", txt).strip()
            cells.append(txt)
        if any(cells):
            rows.append(cells)
    return rows

def main():
    log("=== إتمام السحب عبر زر التصدير (b11) ===")
    f = wait_download()
    if not f:
        log("ERROR: لم يكتمل التنزيل"); sys.exit(1)
    log(f"ملف التنزيل: {os.path.basename(f)} ({os.path.getsize(f)//1024} KB)")
    rows = parse_xls(f)
    log(f"صفوف مُحلَّلة: {len(rows)} (متوقع ~{EXPECTED_TOTAL})")
    if len(rows) < EXPECTED_TOTAL - 5:
        log(f"WARN: عدد الصفوف {len(rows)} أقل من المتوقع بكثير ({EXPECTED_TOTAL})")
    seen = set(); dedup = []
    for r in rows:
        k = tuple(r)
        if k in seen:
            continue
        seen.add(k); dedup.append(r)
    log(f"بعد إزالة تكرار: {len(dedup)}")

    if not dedup:
        log("ERROR: لا صفوف"); sys.exit(1)

    n_cols = len(dedup[0])
    df = pd.DataFrame(dedup, columns=COLS[:n_cols])
    df.to_excel("data.xlsx", index=False, engine="openpyxl")
    log(f"حفظ data.xlsx ({os.path.getsize('data.xlsx')//1024} KB) — الصف {len(df)}")

    subprocess.run(["git","add","-A"], check=True, capture_output=True)
    r = subprocess.run(["git","commit","-m",f"update data {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        p = subprocess.run(["git","push","origin","main"], capture_output=True, text=True, timeout=120)
        if p.returncode == 0: log("تم الرفع لـ GitHub")
        else: log(f"خطأ الرفع: {p.stderr[:200]}")
    else:
        log("لا توجد تغييرات")
    log("=== انتهت العملية بنجاح ===")

if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        log(f"خطأ عام: {e}")
        sys.exit(1)