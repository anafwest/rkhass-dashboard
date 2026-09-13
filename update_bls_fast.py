# -*- coding: utf-8 -*-
"""update_bls_fast.py — سحب BLS8510 بالتوازي مع استئناف ذاتي.

الخادم لا يُجيد >6 جلسات متزامنة (يرد فارغاً أحياناً). الإستراتيجية:
  - تقسيم النطاق على شهور هجرية، كل شهر استعلام جديد ضحل.
  - كل شهر في تبويب نظيف (حقول التاريخ تبدأ فارغة فلا تلتصق القيم).
  - عند أي توقف: يُعاد الشهر فوراً على تبويب جديد (حتى مرتين)؛
    ما يتبقى بعد ذلك يُصلح تسلسلياً (نادر).
  - تقدم محفوظ دائماً: data_partial.xlsx + done_ranges.txt للاستئناف.
"""
import ssl, os, urllib3, time, sys, subprocess, threading, json
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime
import pandas as pd
import scraper as S

WORKERS = int(os.environ.get("BLS_WORKERS", "6"))
STAGGER = 2.0
DONE_FILE = "done_ranges.txt"

def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    with open("update_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)

def home_ready(send, timeout=90):
    t0 = time.time()
    while time.time() - t0 < timeout:
        url = S.js(send, "document.location.href") or ""
        if url and "login" in url.lower() and "faces" not in url.lower():
            S.js(send, f"window.location.href='{S.BLS_SSO_URL}'")
        if S.js(send, 'typeof AdfPage!=="undefined"?"ok":"wait"') == "ok" and \
           S.js(send, "!!document.getElementById('myInput')"):
            return True
        time.sleep(3)
    return False

def close_tab(ws, send):
    try:
        send("Page.close")
    except Exception:
        pass
    try:
        ws.close()
    except Exception:
        pass

def fresh_tab():
    nb = S.open_tab()
    if not nb:
        return None, None
    ws, send = S.connect_ws(nb["webSocketDebuggerUrl"])
    try:
        send("Page.bringToFront")
    except Exception:
        pass
    S.js(send, f"window.location.href='{S.BLS_URL}'")
    if home_ready(send) and (S.myinput_open_8510(send) or S.ensure_8510(send)):
        time.sleep(0.8)
        return ws, send
    close_tab(ws, send)
    return None, None

def set_dates(send, frm, to):
    for fid, val in ((S.FROM_FIELD, frm), (S.TO_FIELD, to)):
        cur = S.js(send, "var e=document.getElementById('" + fid + "'); e?(''+e.value):''")
        if cur.strip() == val:
            continue
        if not S.type_into(send, fid, val):
            return False
    return True

def run_query(send, frm, to):
    if not set_dates(send, frm, to):
        log(f"  {frm}→{to}: فشل ضبط التواريخ")
        return None
    S.click_search(send)
    info = S.wait_search(send, timeout=30)
    if not info.get("rows"):
        time.sleep(2)
        S.click_search(send)
        info = S.wait_search(send, timeout=40)
    return info

def read_safe(send):
    try:
        return S.read_info(send)
    except Exception:
        return {"rows": []}

def next_disabled(send):
    return not S.js_true(send, "(function(){var a=document.getElementById('" + S.NX_ID + "');"
                               "return !!a&&a.offsetParent!==null&&"
                               "!a.getAttribute('disabled')&&a.getAttribute('aria-disabled')!=='true'"
                               "&&(a.className||'').indexOf('Disabled')<0;})()")

def collect_range(send, frm, to, all_rows, have, lock, start_got=0, persist=None):
    info = run_query(send, frm, to)
    if not info:
        return ("q-fail", start_got)
    total = info.get("total", 0)
    if not total:
        return ("ok-empty", start_got)
    if not info.get("rows"):
        return ("q-fail", start_got)
    pp = info.get("perPage", 0) or len(info.get("rows") or []) or 5
    log(f"  {frm}→{to}: {total} سجل | {info.get('perPage', 0)} بالصفحة")
    walked = start_got
    cur = 1
    stall = 0
    requeries = 0
    last_dump = walked
    if start_got >= pp:
        jp = (start_got // pp) + 1
        if S.jump_page(send, jp, pp):
            cur = jp
        else:
            log(f"  {frm}→{to}: فشل القفز {jp} — من البداية")
    while True:
        rows = read_safe(send).get("rows", [])
        if rows:
            newn = 0
            with lock:
                for r in rows:
                    if len(r) >= 10 and str(r[0]) not in have:
                        have.add(str(r[0]))
                        all_rows.append(r)
                        newn += 1
            walked += newn
            stall = 0
            if persist and walked - last_dump >= 400:
                last_dump = walked
                persist(all_rows, walked, total)
                log(f"  حفظ جزئي: {len(all_rows)} صف")
            if walked >= total or next_disabled(send):
                return ("ok", walked)
            S.click_next(send)
            if S.wait_advance(send, walked, timeout=8):
                cur += 1
                continue
        stall += 1
        if stall >= 2 and requeries < 2:
            requeries += 1
            log(f"  {frm}→{to}: استعادة بحث عند صفحة {cur} ({requeries})")
            info2 = run_query(send, frm, to)
            if info2 and info2.get("rows") and S.jump_page(send, cur, pp):
                stall = 0
                continue
        elif stall >= 4:
            log(f"  {frm}→{to}: توقف عند صفحة {cur} بعد {walked} صف")
            return ("stall", walked)
        time.sleep(1.5)
    return ("ok", walked)

def shards():
    y, m = 1447, 4
    stops = []
    while (y, m) <= (1448, 12):
        stops.append((f"{y}/{m:02d}/01", f"{y}/{m:02d}/29"))
        m += 1
        if m > 12:
            m = 1; y += 1
    stops[0] = (S.FROM_DATE, stops[0][1])
    return stops

def persist_rows(all_rows, walked, total):
    try:
        cols = S.COLS[:min(len(all_rows[0]), len(S.COLS))]
        pd.DataFrame(all_rows, columns=cols).to_excel("data_partial.xlsx", index=False, engine="openpyxl")
    except Exception as e:
        log(f"خطأ الحفظ الجزئي: {e}")

def load_state():
    all_rows, have = [], set(["", "-"])
    if os.path.exists("data_partial.xlsx"):
        try:
            df = pd.read_excel("data_partial.xlsx", dtype=str)
            if len(df):
                all_rows = df.values.tolist()
                have.update(str(r[0]) for r in all_rows if len(r))
                log(f"استئناف: {len(all_rows)} صف سابقة")
        except Exception as e:
            log(f"تعذّر قراءة data_partial.xlsx: {e}")
    done = set()
    if os.path.exists(DONE_FILE):
        try:
            done = set(x.strip() for x in open(DONE_FILE, encoding="utf-8").read().splitlines() if x.strip())
            log(f"شهور منجزة سابقاً: {len(done)}")
        except Exception:
            pass
    return all_rows, have, done

def worker(wid, ranges, all_rows, have, lock, done, out):
    time.sleep(STAGGER * wid)
    failed = []
    for frm, to in ranges:
        key = f"{frm}|{to}"
        if key in done:
            log(f"عامل {wid+1}: {frm}→{to} منجز سابقاً")
            continue
        st = "fail"
        for attempt in range(3):
            ws, send = fresh_tab()
            if not send:
                log(f"عامل {wid+1}: لا تبويب لـ {frm} (محاولة {attempt+1})")
                time.sleep(3)
                continue
            try:
                st, _ = collect_range(send, frm, to, all_rows, have, lock, persist=persist_rows)
            finally:
                close_tab(ws, send)
            log(f"عامل {wid+1}: {frm}→{to} → {st} (محاولة {attempt+1})")
            if st in ("ok", "ok-empty"):
                break
            time.sleep(2)
        if st not in ("ok", "ok-empty"):
            failed.append((frm, to))
        else:
            with lock:
                done.add(key)
                try:
                    with open(DONE_FILE, "a", encoding="utf-8") as f:
                        f.write(key + "\n")
                except Exception:
                    pass
            log(f"اكتمال {frm}→{to} — المجموع الكلي الآن {len(all_rows)}")
    out[wid] = failed
    log(f"عامل {wid+1} أنهى: {len(ranges)-len(failed)}/{len(ranges)} شهراً")

def repair(failed, all_rows, have, lock, done):
    for frm, to in failed:
        st = "fail"
        for attempt in range(4):
            ws, send = fresh_tab()
            if not send:
                time.sleep(3)
                continue
            try:
                st, _ = collect_range(send, frm, to, all_rows, have, lock, persist=persist_rows)
            finally:
                close_tab(ws, send)
            log(f"إصلاح {frm}→{to}: {st} (محاولة {attempt+1})")
            if st in ("ok", "ok-empty"):
                break
            time.sleep(2)
        if st in ("ok", "ok-empty"):
            done.add(f"{frm}|{to}")
            with open(DONE_FILE, "a", encoding="utf-8") as f:
                f.write(f"{frm}|{to}\n")
            log(f"إصلاح ناجح {frm}→{to} — المجموع {len(all_rows)}")

def commit_push():
    subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
    r = subprocess.run(["git", "commit", "-m", f"update data {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        p = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True, timeout=120)
        log("تم الرفع لـ GitHub" if p.returncode == 0 else f"خطأ الرفع: {p.stderr[:200]}")
    else:
        log("لا توجد تغييرات")

def main():
    lockf = "update_bls.lock"
    if os.path.exists(lockf):
        log("مثال آخر يعمل — خروج")
        return 0
    open(lockf, "w").close()
    t_all = time.time()
    try:
        log("=" * 62)
        log("سحب BLS8510 — متوازٍ (إعادة محاولة فورية + استئناف)")

        if not S.get_tabs():
            if not S.start_chrome():
                log("FATAL: لم يبدأ Chrome")
                return 1

        # قياس الإجمالي
        ws, send = fresh_tab()
        if not send:
            log("FATAL: تعذّر فتح 8510")
            return 2
        try:
            info = run_query_full_range(send)
            total = info.get("total") if info else 0
        finally:
            close_tab(ws, send)
        if not total:
            log("FATAL: لا بيانات في النطاق الكامل")
            return 2
        log(f"الإجمالي: {total} سجل")

        all_rows, have, done = load_state()
        scope = [s for s in shards() if f"{s[0]}|{s[1]}" not in done]
        if not scope:
            log("كل الشهور منجزة سابقاً — تخطي المسح")
        else:
            log(f"النطاق: {len(scope)} شهراً عبر {WORKERS} عامل")
            n = min(WORKERS, len(scope))
            chunks = [[] for _ in range(n)]
            for i, item in enumerate(scope):
                chunks[i % n].append(item)
            lock = threading.Lock()
            out = [None] * n
            threads = [threading.Thread(target=worker, args=(i, chunks[i], all_rows, have, lock, done, out))
                       for i in range(n)]
            t0 = time.time()
            for th in threads:
                th.start()
            for th in threads:
                th.join()
            log(f"الشوط المتوازي: {int((time.time()-t0)//60)}د {int((time.time()-t0)%60)}ث")
            failed = [x for o in out for x in o]
            if failed:
                log(f"إصلاح تسلسلي... ({len(failed)})")
                repair(failed, all_rows, have, lock, done)
            log(f"المجموع الكلي الآن: {len(all_rows)} صف")

        hole = total - len(all_rows)
        if hole > 30:
            log(f"ناقص {hole} صف — تبقى data_partial.xlsx")
            return 3
        if hole > 0:
            log(f"فجوة صغيرة {hole} صف (بيانات حية) — مقبول")
        try:
            cols = S.COLS[:min(len(all_rows[0]), len(S.COLS))]
            pd.DataFrame(all_rows, columns=cols).to_excel("data.xlsx", index=False, engine="openpyxl")
        except Exception:
            pass
        for f in ("data_partial.xlsx", DONE_FILE):
            try:
                os.remove(f)
            except Exception:
                pass
        log(f"اكتمل: {len(all_rows)}/{total} في {int((time.time()-t_all)//60)}د {int((time.time()-t_all)%60)}ث")
        commit_push()
    finally:
        try:
            os.remove(lockf)
        except Exception:
            pass

def run_query_full_range(send):
    if not set_dates(send, S.FROM_DATE, S.TO_DATE):
        return None
    S.click_search(send)
    return S.wait_search(send, timeout=40)

if __name__ == "__main__":
    sys.exit(main())