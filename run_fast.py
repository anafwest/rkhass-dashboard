# -*- coding: utf-8 -*-
"""قراءة سريعة بتبويب واحد: كتل 250 صفحة + إنعاش بحث + قفز مُعتمد بعد تثبيت الجدول.
بلا تحميل ملفات، بلا تبويبات متوازية."""
import ssl, os, urllib3, time, sys, subprocess
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime
import pandas as pd
import scraper as S

REFRESH_EVERY = 250

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("scraper_log.txt","a",encoding="utf-8") as f: f.write(f"[{ts}] {msg}\n")
    print(f"[{ts}] {msg}", flush=True)

def open_tab_screen():
    nb = S.open_tab()
    if not nb:
        return None, None
    ws, send = S.connect_ws(nb["webSocketDebuggerUrl"])
    S.js(send, f"window.location.href='{S.BLS_URL}'")
    t0 = time.time()
    while time.time()-t0 < 60:
        url = S.js(send,"document.location.href") or ""
        if "login" in url.lower() and "faces" not in url.lower():
            S.js(send, f"window.location.href='{S.BLS_SSO_URL}'")
        if S.js(send,'typeof AdfPage!=="undefined"?"ok":"wait"')=="ok" and \
           S.js(send,"!!document.getElementById('myInput')"):
            break
        time.sleep(2)
    if not S.myinput_open_8510(send):
        S.ensure_8510(send)
    return ws, send

def refresh_search(send):
    S.ensure_dates(send)
    S.click_search(send)
    info = S.wait_search(send, timeout=25)
    # تثبيت الجدول قبل القفز
    for i in range(6):
        r = S.rng_txt(send)
        if r != "nf" and "1-5" in r:
            time.sleep(1.0)
            if "1-5" in S.rng_txt(send):
                return info
        time.sleep(1.0)
    return info

def jump_confirmed(send, pg, pp, max_attempts=4):
    waits = [3, 6, 10, 15]
    for i in range(max_attempts):
        if S.jump_page(send, pg, pp):
            s = S.start_num(S.rng_txt(send))
            if s == (pg-1)*pp + 1:
                return True
        time.sleep(waits[min(i, len(waits)-1)])
    return False

def work_block(send, start_page, end_page, pp, all_rows, have):
    cur = start_page
    if cur > 1:
        if not jump_confirmed(send, cur, pp):
            log(f"  القفز لصفحة {cur} فشل بعد 4 محاولات")
            return "jump-fail"
    streak = 0
    while cur <= end_page:
        info = S.read_info(send)
        rows = info.get("rows", [])
        if not rows:
            streak += 1
            if streak >= 3:
                return "stall"
            time.sleep(1)
            continue
        for r in rows:
            if len(r) >= 10 and str(r[0]) not in have:
                have.add(str(r[0])); all_rows.append(r)
        if cur >= end_page:
            break
        S.click_next(send)
        time.sleep(0.25)
        info = S.read_info(send)
        n = S.start_num(S.rng_txt(send))
        if n > cur*pp:
            cur += 1; streak = 0
            continue
        info = S.wait_advance(send, cur*pp, timeout=8)
        if info:
            cur += 1; streak = 0
            continue
        streak += 1
        log(f"  تقدم صفحة {cur+1} لم يُؤكد (streak {streak})")
        if streak >= 2:
            info = refresh_search(send)
            if info.get("rows") and jump_confirmed(send, cur+1, pp, 2):
                cur += 1; streak = 0
                continue
        if streak >= 4:
            return "stall"
        time.sleep(1)
    return "ok"

def save_checkpoint(all_rows, tag="data_partial.xlsx"):
    try:
        cols = S.COLS[:min(len(all_rows[0]), len(S.COLS))]
        pd.DataFrame(all_rows, columns=cols).to_excel(tag, index=False, engine="openpyxl")
    except Exception:
        pass

def main():
    S.log = log
    log("="*60)
    log("قراءة سريعة بتبويب واحد (كتل 250 + إنعاش + قفز مؤكد)")
    ws, send = open_tab_screen()
    if not send:
        log("FATAL: لا تبويب"); sys.exit(1)
    info = refresh_search(send)
    if not info.get("rows") or info.get("perPage",0) < 5:
        log(f"ERROR: بحث فشل {info}"); sys.exit(1)
    total = info["total"]; pp = info["perPage"]
    pages = (total + pp - 1)//pp
    log(f"بيانات: {total} سجل، {pages} صفحة ({pp} للصفحة)")

    all_rows = []; have = set(["","-"])
    cur = 1; t_start = time.time(); stalls = 0
    while cur <= pages:
        end = min(cur + REFRESH_EVERY - 1, pages)
        status = work_block(send, cur, end, pp, all_rows, have)
        save_checkpoint(all_rows)
        log(f"الكتلة {cur}-{end}: {status} | المجموع {len(all_rows)}")
        if status != "ok":
            stalls += 1
            if stalls >= 3:
                log("حد الركود — توقف")
                break
            # تبويب جديد نظيف من نفس الصفحة
            log(f"ركود — تبويب جديد من صفحة {cur}...")
            try: send("Page.close"); ws.close()
            except Exception: pass
            ws, send = open_tab_screen()
            if not send:
                break
            info = refresh_search(send)
            if not info.get("rows"):
                break
            continue
        if end >= pages:
            break
        info = refresh_search(send)
        if not info.get("rows"):
            log("ERROR: الإنعاش فشل"); break
        cur = end + 1
    elapsed = time.time()-t_start
    log(f"جمع {len(all_rows)} صف من {total} في {int(elapsed//60)}د {int(elapsed%60)}ث")
    try: ws.close()
    except Exception: pass

    seen = set(); dedup = []
    for r in all_rows:
        kkey = tuple(r)
        if len(r) < 10 or kkey in seen: continue
        seen.add(kkey); dedup.append(r)
    all_rows = dedup
    log(f"بعد إزالة التكرار: {len(all_rows)}")

    if len(all_rows) < total - 5:
        save_checkpoint(all_rows)
        log(f"حارس الحفظ: ناقص {len(all_rows)}/{total} — لن أُعدّل data.xlsx")
        sys.exit(3)

    cols = S.COLS[:min(len(all_rows[0]), len(S.COLS))]
    df = pd.DataFrame(all_rows, columns=cols)
    df.to_excel("data.xlsx", index=False, engine="openpyxl")
    log(f"حفظ data.xlsx ({os.path.getsize('data.xlsx')//1024} KB) — {len(df)} صف")
    if os.path.exists("data_partial.xlsx"):
        os.remove("data_partial.xlsx")

    subprocess.run(["git","add","-A"], check=True, capture_output=True)
    r = subprocess.run(["git","commit","-m",f"update data {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        p = subprocess.run(["git","push","origin","main"], capture_output=True, text=True, timeout=120)
        log("تم الرفع لـ GitHub" if p.returncode==0 else f"خطأ الرفع: {p.stderr[:200]}")
    else:
        log("لا توجد تغييرات")
    log("=== انتهت القراءة بنجاح ===")

if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        log(f"خطأ عام: {e}")
        sys.exit(1)