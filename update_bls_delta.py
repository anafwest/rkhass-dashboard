# -*- coding: utf-8 -*-
"""update_bls_delta.py — مزامنة تزايدية لبيانات BLS8510.

الفكرة: أغلب البيانات موجودة في data.xlsx؛ لا نعيد سحب كل شيء.
  - نحدد آخر تاريخ مراجعة في الملف الحالي (max_rev).
  - نسحب فقط نافذة زمنية: [max_rev - تراكب يومي → نهاية النظام].
  - ندمج: مفاتيح جديدة تُضاف، مفاتيح موجودة تُحدَّث حالتها بآخر ما ورد في النظام.
  - نحفظ data.xlsx (مع نسخة احتياطية) ونرفع لـ GitHub.
"""
import ssl, os, urllib3, time, sys, threading, json
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime
import pandas as pd
import scraper as S
import update_bls_fast as F

WORKERS = int(os.environ.get("BLS_WORKERS", "6"))
OVERLAP_DAYS = int(os.environ.get("BLS_OVERLAP_DAYS", "0"))
WINDOW_END = os.environ.get("BLS_WINDOW_END", S.TO_DATE)
DONE_FILE = "delta_done.txt"
KEY_IDX = 0

def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    with open("delta_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)

def dec_day(date_str, days):
    """إنقاص أيام من تاريخ هجري yyyy/mm/dd (طرح رقمي بسيط)."""
    y, m, d = (int(x) for x in date_str.split("/"))
    while days > 0:
        if d > days:
            d -= days
            days = 0
        else:
            days -= d
            if m == 1:
                y -= 1
                m = 12
            else:
                m -= 1
            d = 29
    return f"{y}/{m:02d}/{d:02d}"

def add_month(y, m):
    m += 1
    if m > 12:
        m = 1
        y += 1
    return y, m

def month_tiles_from(start):
    """بلاطات شهرية من start حتى نهاية النطاق المحدد في scraper."""
    start_y, start_m = (int(x) for x in start.split("/")[:2])
    tiles = []
    y, m = start_y, start_m
    end_y, end_m = (int(x) for x in WINDOW_END.split("/")[:2])
    while (y, m) <= (end_y, end_m):
        frm = f"{y}/{m:02d}/01"
        if not tiles:
            frm = start
        tiles.append((frm, f"{y}/{m:02d}/29"))
        y, m = add_month(y, m)
    return tiles

def load_base():
    df = pd.read_excel("data.xlsx", dtype=str).fillna("")
    rows = df.values.tolist()
    base = {str(r[KEY_IDX]): r for r in rows if len(r) if str(r[KEY_IDX])}
    return rows, base

def max_rev_date(base):
    vals = [str(r[12]).strip() for r in base.values() if len(r) > 12]
    valid = sorted(v for v in vals if len(v) == 10 and v[4] == v[7] == "/")
    return valid[-1] if valid else S.FROM_DATE

def worker(wid, tiles, delta_rows, have, lock, done, out):
    time.sleep(F.STAGGER * wid)
    failed = []
    for frm, to in tiles:
        key = f"{frm}|{to}"
        if key in done:
            continue
        st = "fail"
        for attempt in range(3):
            ws, send = F.fresh_tab()
            if not send:
                log(f"عامل {wid+1}: لا تبويب لـ {frm} (محاولة {attempt+1})")
                time.sleep(3)
                continue
            try:
                st, _ = F.collect_range(send, frm, to, delta_rows, have, lock, persist=None)
            finally:
                F.close_tab(ws, send)
            log(f"عامل {wid+1}: {frm}→{to} → {st} ({attempt+1})")
            if st in ("ok", "ok-empty"):
                break
            time.sleep(2)
        if st in ("ok", "ok-empty"):
            with lock:
                done.add(key)
                try:
                    with open(DONE_FILE, "a", encoding="utf-8") as f:
                        f.write(key + "\n")
                except Exception:
                    pass
            log(f"اكتمال {frm}→{to} — دلتا الآن {len(delta_rows)} صفاً")
        else:
            failed.append((frm, to))
    out[wid] = failed

def repair(failed, delta_rows, have, lock, done):
    for frm, to in failed:
        st = "fail"
        for attempt in range(4):
            ws, send = F.fresh_tab()
            if not send:
                time.sleep(3)
                continue
            try:
                st, _ = F.collect_range(send, frm, to, delta_rows, have, lock, persist=None)
            finally:
                F.close_tab(ws, send)
            log(f"إصلاح {frm}→{to}: {st} ({attempt+1})")
            if st in ("ok", "ok-empty"):
                break
            time.sleep(2)
        if st in ("ok", "ok-empty"):
            done.add(f"{frm}|{to}")
            with open(DONE_FILE, "a", encoding="utf-8") as f:
                f.write(f"{frm}|{to}\n")
            log(f"إصلاح ناجح {frm}→{to} — دلتا {len(delta_rows)}")

def main():
    lockf = "update_bls.lock"
    if os.path.exists(lockf):
        log("مثال آخر يعمل — خروج")
        return 0
    open(lockf, "w").close()
    t_all = time.time()
    try:
        log("=" * 62)
        log("مزامنة تزايدية BLS8510 (إضافة + تحديث حالة)")

        base_rows, base = load_base()
        max_rev = max_rev_date(base)
        log(f"قاعدة حالية: {len(base)} سجل — آخر مراجعة: {max_rev}")

        if not S.get_tabs():
            if not S.start_chrome():
                log("FATAL: لم يبدأ Chrome")
                return 1

        start = dec_day(max_rev, OVERLAP_DAYS)
        tiles = month_tiles_from(start)
        log(f"النافذة: {tiles[0][0]} ← {tiles[-1][1]} ({len(tiles)} بلاطة)")

        delta_rows = []
        lock = threading.Lock()
        done = set()
        if os.path.exists(DONE_FILE):
            done = set(x.strip() for x in open(DONE_FILE, encoding="utf-8").read().splitlines() if x.strip())
        scope = [t for t in tiles if f"{t[0]}|{t[1]}" not in done]
        if not scope:
            log("النافذة منجزة سابقاً")
        else:
            n = min(WORKERS, len(scope))
            chunks = [[] for _ in range(n)]
            for i, item in enumerate(scope):
                chunks[i % n].append(item)
            out = [None] * n
            threads = [threading.Thread(target=worker, args=(i, chunks[i], delta_rows, set(), lock, done, out))
                       for i in range(n)]
            t0 = time.time()
            for th in threads:
                th.start()
            for th in threads:
                th.join()
            log(f"الشوط: {int((time.time()-t0)//60)}د {int((time.time()-t0)%60)}ث — دلتا {len(delta_rows)} صفاً")
            failed = [x for o in out for x in o]
            if failed:
                log(f"إصلاح تسلسلي... ({len(failed)})")
                repair(failed, delta_rows, have, lock, done)

        # دمج: تحديث الموجود + إضافة الجديد
        if delta_rows:
            req = sorted({str(r[5]) for r in delta_rows if len(r) > 5 and str(r[5]).strip()})
            rev = sorted({str(r[12]) for r in delta_rows if len(r) > 12 and str(r[12]).strip()})
            log(f"دلتا نطاق تاريخ الطلب: {req[0] if req else '-'}..{req[-1] if req else '-'} "
                f"| نطاق تاريخ المراجعة: {rev[0] if rev else '-'}..{rev[-1] if rev else '-'}")
        upd = 0
        add = 0
        merged = dict(base)
        newest = 0
        for r in delta_rows:
            if len(r) < 10:
                continue
            k = str(r[KEY_IDX])
            merged[k] = r
            newest += 1
        # عدّ: كم تحديثاً مقابل إضافة (بمقارنة وصف المرحلة)
        for k, r in merged.items():
            if k in base:
                if len(r) > 3 and len(base[k]) > 3 and r[3] != base[k][3]:
                    upd += 1
            else:
                add += 1
        log(f"تحديث حالة: {upd} | إضافة جديدة: {add} | إجمالي بعد الدمج: {len(merged)}")

        cols = S.COLS
        out_rows = [merged[k] for k in merged]
        try:
            os.replace("data.xlsx", "data_prev.xlsx")
        except Exception:
            pass
        pd.DataFrame(out_rows, columns=cols).to_excel("data.xlsx", index=False, engine="openpyxl")
        for f in ("data_partial.xlsx", DONE_FILE):
            try:
                os.remove(f)
            except Exception:
                pass
        log(f"تم الحفظ: data.xlsx ({len(out_rows)} صفاً) في {int((time.time()-t_all)//60)}د {int((time.time()-t_all)%60)}ث")
        F.commit_push()
    finally:
        try:
            os.remove(lockf)
        except Exception:
            pass

if __name__ == "__main__":
    sys.exit(main())