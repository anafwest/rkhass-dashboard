# -*- coding: utf-8 -*-
"""قراءة سريعة متوازية (حسّابان بتبويبين) + إصلاح تلقائي للكتل الناقصة تسلسلياً."""
import ssl, os, urllib3, time, sys, subprocess, threading
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

def _home_ready(send, timeout=60):
    t0 = time.time()
    while time.time()-t0 < timeout:
        url = S.js(send,"document.location.href") or ""
        if "login" in url.lower() and "faces" not in url.lower():
            S.js(send, f"window.location.href='{S.BLS_SSO_URL}'")
        if S.js(send,'typeof AdfPage!=="undefined"?"ok":"wait"')=="ok" and \
           S.js(send,"!!document.getElementById('myInput')"):
            return True
        time.sleep(2)
    return False

def _dates_are_real(send):
    if not S.has_form(send):
        return False
    for fid in (S.FROM_FIELD, S.TO_FIELD):
        v = S.js(send, "(function(){var e=document.getElementById('" + fid + "');"
                 "if(!e)return '__nf__';return e.value==null||e.value===undefined?'':(''+e.value);})()")
        if v == "__nf__" or v == "{}":
            return False
    return True

def open_tab_screen():
    for attempt in range(3):
        nb = S.open_tab()
        if not nb:
            return None, None
        ws, send = S.connect_ws(nb["webSocketDebuggerUrl"])
        S.js(send, f"window.location.href='{S.BLS_URL}'")
        if _home_ready(send):
            if S.myinput_open_8510(send) or S.ensure_8510(send):
                time.sleep(1.5)
                S.ensure_dates(send)
                if _dates_are_real(send):
                    return ws, send
                log(f"  شاشة 8510 ناقصة التواريخ — إعادة (محاولة {attempt+1}/3)")
            else:
                log(f"  فشل فتح 8510 (محاولة {attempt+1}/3)")
        else:
            log(f"  فشل تحميل الصفحة الرئيسية (محاولة {attempt+1}/3)")
        try: ws.close()
        except Exception: pass
    return None, None

def refresh_search(send):
    S.ensure_dates(send)
    S.click_search(send)
    info = S.wait_search(send, timeout=20)
    for i in range(6):
        r = S.rng_txt(send)
        if r != "nf" and "1-5" in r:
            time.sleep(0.5)
            if "1-5" in S.rng_txt(send):
                return info
        time.sleep(0.5)
    return info

def jump_confirmed(send, pg, pp, max_attempts=4):
    waits = [2, 4, 8, 12]
    for i in range(max_attempts):
        if S.jump_page(send, pg, pp):
            s = S.start_num(S.rng_txt(send))
            if s == (pg-1)*pp + 1:
                return True
        time.sleep(waits[min(i, len(waits)-1)])
    return False

def work_block(send, start_page, end_page, pp, all_rows, have, lock):
    cur = start_page
    if cur > 1 and not jump_confirmed(send, cur, pp):
        log(f"  القفز لصفحة {cur} فشل بعد 4 محاولات")
        return ("jump-fail", cur)
    streak = 0
    while cur <= end_page:
        info = S.read_info(send)
        rows = info.get("rows", [])
        if not rows:
            streak += 1
            if streak >= 3:
                return ("stall", cur)
            time.sleep(0.4)
            continue
        with lock:
            for r in rows:
                if len(r) >= 10 and str(r[0]) not in have:
                    have.add(str(r[0])); all_rows.append(r)
        if cur >= end_page:
            break
        S.click_next(send)
        time.sleep(0.1)
        info = S.read_info(send)
        n = S.start_num(S.rng_txt(send))
        if n > cur*pp:
            cur += 1; streak = 0
            continue
        info = S.wait_advance(send, cur*pp, timeout=5)
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
            return ("stall", cur)
        time.sleep(0.5)
    return ("ok", cur)

def save_checkpoint(all_rows, tag="data_partial.xlsx"):
    try:
        cols = S.COLS[:min(len(all_rows[0]), len(S.COLS))]
        pd.DataFrame(all_rows, columns=cols).to_excel(tag, index=False, engine="openpyxl")
    except Exception:
        pass

def worker_loop(worker, start_page, end_page, pp, all_rows, have, lock, out):
    ws, send = open_tab_screen()
    if not send:
        out[worker] = ("no-tab", start_page)
        return
    time.sleep(2.0 * worker)
    info = refresh_search(send)
    if not info.get("rows"):
        log(f"حسّاب {worker+1}: بحث فشل")
        out[worker] = ("no-search", start_page)
        try: ws.close()
        except Exception: pass
        return
    st, at = work_block(send, start_page, end_page, pp, all_rows, have, lock)
    log(f"حسّاب {worker+1}: كتلة {start_page}-{end_page} → {st} | المجموع {len(all_rows)}")
    out[worker] = (st, at)
    try: ws.close()
    except Exception: pass

def repair(ranges, pp, all_rows, have, lock):
    for label, s, e in ranges:
        ws, send = open_tab_screen()
        if not send:
            return False
        info = refresh_search(send)
        ok = info.get("rows") is not None or len(info.get("rows") or []) > 0
        if ok:
            st, at = work_block(send, s, e, pp, all_rows, have, lock)
            log(f"إصلاح كتلة {s}-{e}: {st}")
            ok = (st == "ok")
        else:
            log(f"إصلاح كتلة {s}-{e}: بحث فشل")
        try: ws.close()
        except Exception: pass
        if not ok:
            return False
    return True

def main():
    S.log = log
    LOCK = "run_fast.lock"
    if os.path.exists(LOCK):
        log("مثال آخر يعمل بالفعل — خروج بدون تشغيل")
        return 0
    open(LOCK, "w").close()
    try:
        return _main()
    finally:
        try: os.remove(LOCK)
        except Exception: pass

def _main():
    log("="*60)
    log("قراءة سريعة متوازية (حسّابان + إصلاح)")
    ws, send = open_tab_screen()
    if not send:
        log("FATAL: لا تبويب"); sys.exit(1)
    info = refresh_search(send)
    if not info.get("rows") or info.get("perPage",0) < 5:
        log(f"ERROR: بحث فشل {info}"); sys.exit(1)
    try: ws.close()
    except Exception: pass
    total = info["total"]; pp = info["perPage"]
    pages = (total + pp - 1)//pp
    log(f"بيانات: {total} سجل، {pages} صفحة ({pp} للصفحة)")

    all_rows = []; have = set(["","-"]); lock = threading.Lock()
    workers = 4 if pages > 500 else 2 if pages > 150 else 1
    chunk = (pages + workers - 1)//workers
    ranges = []
    s = 1
    while s <= pages:
        e = min(s + chunk - 1, pages)
        ranges.append((s, e)); s = e + 1
    t_start = time.time()
    out = [None]*workers
    threads = []
    for i in range(workers):
        rs, re = ranges[i]
        th = threading.Thread(target=worker_loop, args=(i, rs, re, pp, all_rows, have, lock, out))
        threads.append(th); th.start()
    for th in threads:
        th.join()

    broken = []
    for i in range(workers):
        rs, re = ranges[i]
        st, at = out[i] if out[i] else ("unknown", rs)
        if st != "ok":
            frm = at if isinstance(at, int) else rs
            broken.append((f"repair-{i}", frm, re))
    if broken:
        log(f"إصلاح {len(broken)} كتلة ناقصة تسلسلياً...")
        repair(broken, pp, all_rows, have, lock)

    elapsed = time.time()-t_start
    log(f"جمع {len(all_rows)} صف من {total} في {int(elapsed//60)}د {int(elapsed%60)}ث")

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