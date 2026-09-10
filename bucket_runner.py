# -*- coding: utf-8 -*-
"""قراءة موازية مجزأة: تقسيم فترة 1447/04/13..1448/12/29 على 4 نطاقات تواريخ مستقلة
أربعة تبويبات (استعلامات منفصلة لا تتداخل) ثم دمج وحفظ/رفع."""
import ssl, os, urllib3, time, sys, subprocess, threading
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime
import pandas as pd
import scraper as S

FROM_BASE = "1447/04/13"
TO_BASE = "1448/12/29"
CANDIDATES = ["1447/06/29","1447/09/29","1447/12/29","1448/03/29","1448/06/29","1448/09/29"]
N_BUCKETS = 4

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("scraper_log.txt","a",encoding="utf-8") as f: f.write(f"[{ts}] {msg}\n")
    print(f"[{ts}] {msg}", flush=True)

def setup_tab():
    """تبويب جديد نظيف، شاشة 8510 جاهزة."""
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

def search_total(send, fd, td):
    S.ensure_dates(send)
    # ضبط التاريخين بالنطاق الجديد
    for fid, val in (("pt1:cBodFDC:r1:0:masteraTable:Fromdate::content", fd),
                     ("pt1:cBodFDC:r1:0:masteraTable:Todate::content", td)):
        cur = S.js(send, "var e=document.getElementById('"+fid+"'); e?e.value:''")
        if str(cur).strip() != val:
            S.type_into(send, fid, val)
    S.click_search(send)
    info = S.wait_search(send, timeout=25)
    if not info.get("rows"):
        return 0, info
    return info["total"], info

def measure():
    ws, send = setup_tab()
    if not send:
        log("FATAL: لا يمكن قياس الحدود"); sys.exit(1)
    pts = {}
    for b in CANDIDATES:
        tot, _ = search_total(send, FROM_BASE, b)
        pts[b] = tot
        log(f"الحد {b}: {tot} سجل")
    tot_final, _ = search_total(send, FROM_BASE, TO_BASE)
    pts[TO_BASE] = tot_final
    log(f"الكل {TO_BASE}: {tot_final}")
    # اختيار 3 حدود أقرب للتوزيع المتساوي (25%، 50%، 75%)
    target = tot_final / N_BUCKETS
    need = [target, 2*target, 3*target]
    chosen = []
    items = sorted(pts.items(), key=lambda x: x[1])
    for t in need:
        best = min(items, key=lambda it: abs(it[1]-t))
        if best[0] not in chosen and best[0] != TO_BASE:
            chosen.append(best[0])
        else:
            alt = [d for d,c in items if d not in chosen+[TO_BASE]]
            if alt: chosen.append(alt[0])
    chosen = sorted(chosen)
    log(f"حدود مختارة: {chosen}")
    try:
        S.js(send,"window.close()") if False else send("Page.close")
        ws.close()
    except Exception:
        pass
    return chosen, tot_final

def collect_all(send, into):
    """قراءة كل الصفحات بترتيب (بلا قفز) في النطاق الحالي."""
    info = S.read_info(send)
    total = info.get("total", 0); pp = info.get("perPage", 5) or 5
    pages = (total + pp - 1)//pp if total else 0
    cur = 1; streak = 0; rows = []
    while cur <= pages:
        info = S.read_info(send)
        for r in info.get("rows", []):
            if len(r) >= 10:
                rows.append(r)
        if cur >= pages:
            break
        S.click_next(send)
        if S.wait_advance(send, cur*pp, timeout=8):
            cur += 1; streak = 0
        else:
            streak += 1
            log(f"  [نطاق] تعذّر تقدم الصفحة {cur} (streak {streak})")
            if streak >= 5:
                break
            time.sleep(1)
    into.extend(rows)
    return len(rows), total

def worker(k, fd, td, results):
    ws, send = setup_tab()
    if not send:
        results[k] = ([], "no-tab"); return
    try:
        S.ensure_dates(send)
        for fid, val in (("pt1:cBodFDC:r1:0:masteraTable:Fromdate::content", fd),
                         ("pt1:cBodFDC:r1:0:masteraTable:Todate::content", td)):
            if str(S.js(send,"var e=document.getElementById('"+fid+"'); e?e.value:''")).strip() != val:
                S.type_into(send, fid, val)
        S.click_search(send)
        info = S.wait_search(send, timeout=25)
        if not info.get("rows"):
            results[k] = ([], "no-search")
            return
        into = []
        n, tot = collect_all(send, into)
        log(f"عام {k}: {fd}..{td} جمع {n}/{tot} صف")
        results[k] = (into, "ok" if n >= tot-5 else "short")
    finally:
        try: send("Page.close"); ws.close()
        except Exception: pass

def main():
    S.log = log
    log("="*60)
    log("قراءة موازية: 4 نطاقات في تبويبات مستقلة")
    chosen, tot_final = measure()
    b = sorted(set(chosen + [TO_BASE]))
    start = FROM_BASE
    ranges = []
    for x in b:
        ranges.append((start, x)); start = x
    log(f"النطاقات: {ranges}")

    results = {}
    threads = []
    for k, (fd, td) in enumerate(ranges):
        th = threading.Thread(target=worker, args=(k, fd, td, results))
        th.daemon = True
        threads.append(th)
    # أطلق العمال متباعدين قليلاً
    for th in threads:
        th.start(); time.sleep(3)
    for th in threads:
        th.join()

    # إعادة محاولة النطاقات الفاشلة تسلسلياً
    for k, (fd, td) in enumerate(ranges):
        rows, st = results.get(k, ([], "missing"))
        if st != "ok":
            log(f"إعادة محاولة النطاق {fd}..{td} تسلسلياً...")
            ws, send = setup_tab()
            if send:
                for fid, val in (("pt1:cBodFDC:r1:0:masteraTable:Fromdate::content", fd),
                                 ("pt1:cBodFDC:r1:0:masteraTable:Todate::content", td)):
                    S.type_into(send, fid, val)
                S.click_search(send)
                info = S.wait_search(send, timeout=25)
                if info.get("rows"):
                    into = []
                    n, tot = collect_all(send, into)
                    results[k] = (into, "ok" if n >= tot-5 else "short")
                    log(f"إعادة نطاق {fd}..{td}: {n}/{tot}")
                try: send("Page.close"); ws.close()
                except Exception: pass

    all_rows = []
    per = {}
    for k, (fd, td) in enumerate(ranges):
        rows, st = results.get(k, ([], "missing"))
        per[fd] = len(rows)
        all_rows.extend(rows)
    log(f"المجموع: {len(all_rows)} ({per})")

    seen = set(); dedup = []
    for r in all_rows:
        kkey = tuple(r)
        if len(r) < 10 or kkey in seen: continue
        seen.add(kkey); dedup.append(r)
    all_rows = dedup
    log(f"بعد إزالة التكرار (تداخل حد اليوم): {len(all_rows)}")

    if len(all_rows) < tot_final - 5:
        cols = S.COLS[:min(len(all_rows[0]), len(S.COLS))]
        try:
            pd.DataFrame(all_rows, columns=cols).to_excel("data_partial.xlsx", index=False, engine="openpyxl")
        except Exception:
            pass
        log(f"حارس الحفظ: الجمع ناقص {len(all_rows)}/{tot_final} — لن أُعدّل data.xlsx")
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