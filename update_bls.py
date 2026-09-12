# -*- coding: utf-8 -*-
"""update_bls.py — سحب بيانات BLS8510 (تسلسلي كامل، جلسة واحدة).

الجلسة الواحدة المتسلسلة هي الأكثر موثوقية: الخادم يُجيد الجلسة الطويلة
ويُعامل الجلسات المتزامنة أحياناً باستجابات فارغة (توقفات). نمسح النطاق
كله دفعة واحدة بدون شقّ، مع كشف النهاية عبر العدّ وزر التالي المعطّل.
"""
import ssl, os, urllib3, time, sys, subprocess, threading
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime
import pandas as pd
import scraper as S

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
    for attempt in range(3):
        nb = S.open_tab()
        if not nb:
            time.sleep(2)
            continue
        ws, send = S.connect_ws(nb["webSocketDebuggerUrl"])
        try:
            send("Page.bringToFront")
        except Exception:
            pass
        S.js(send, f"window.location.href='{S.BLS_URL}'")
        if home_ready(send) and (S.myinput_open_8510(send) or S.ensure_8510(send)):
            time.sleep(1.0)
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
        return None, send
    S.click_search(send)
    info = S.wait_search(send, timeout=30)
    if not info.get("rows"):
        time.sleep(2)
        S.click_search(send)
        info = S.wait_search(send, timeout=40)
    return info, send

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
    info, send = run_query(send, frm, to)
    if not info or not info.get("rows"):
        return ("q-fail", start_got, send, 0)
    pp = info.get("perPage", 0) or len(info.get("rows") or []) or 5
    total = info.get("total", 0)
    log(f"  {frm}→{to}: {total} سجل | {info.get('perPage', 0)} بالصفحة")
    if not total:
        return ("ok-empty", start_got, send, 0)
    walked = start_got
    cur = 1
    stall = 0
    last_dump = walked
    if start_got >= pp:
        jump_page_idx = (start_got // pp) + 1
        if S.jump_page(send, jump_page_idx, pp):
            cur = jump_page_idx
        else:
            log(f"  فشل القفز لصفحة {jump_page_idx} — أعود من البداية")
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
                log(f"  حفظ جزئي: {len(all_rows)} صف عند صفحة {cur}")
            if walked >= total or next_disabled(send):
                break
            S.click_next(send)
            if S.wait_advance(send, walked, timeout=6):
                cur += 1
                continue
        stall += 1
        if stall >= 2:
            log(f"  {frm}→{to}: توقفت عند صفحة {cur} (بعد {walked} صف)")
            return ("stall", walked, send, total)
        time.sleep(2.0)
    return ("ok", walked, send, total)

def commit_push():
    subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
    r = subprocess.run(["git", "commit", "-m", f"update data {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        p = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True, timeout=120)
        log("تم الرفع لـ GitHub" if p.returncode == 0 else f"خطأ الرفع: {p.stderr[:200]}")
    else:
        log("لا توجد تغييرات")

def load_partial():
    all_rows, have = [], set(["", "-"])
    meta = 0
    if os.path.exists("data_partial.xlsx"):
        try:
            df = pd.read_excel("data_partial.xlsx", dtype=str)
            if len(df):
                all_rows = df.values.tolist()
                have.update(str(r[0]) for r in all_rows if len(r))
            meta = 0
            if os.path.exists("progress.meta"):
                try:
                    meta = int(open("progress.meta", "r").read().strip())
                except Exception:
                    meta = 0
            log(f"استئناف: {len(all_rows)} صف سابقة، صفحة ~{meta//5}")
        except Exception as e:
            log(f"تعذّر قراءة data_partial.xlsx: {e}")
    return all_rows, have, meta

def persist_rows(all_rows, walked, total):
    try:
        cols = S.COLS[:min(len(all_rows[0]), len(S.COLS))]
        pd.DataFrame(all_rows, columns=cols).to_excel("data_partial.xlsx", index=False, engine="openpyxl")
        with open("progress.meta", "w") as f:
            f.write(str(walked))
    except Exception as e:
        log(f"خطأ الحفظ الجزئي: {e}")

def main():
    lockf = "update_bls.lock"
    if os.path.exists(lockf):
        log("مثال آخر يعمل — خروج")
        return 0
    open(lockf, "w").close()
    t_all = time.time()
    try:
        log("=" * 62)
        log("سحب BLS8510 — تسلسلي كامل (قابل للاستئناف)")

        if not S.get_tabs():
            if not S.start_chrome():
                log("FATAL: لم يبدأ Chrome")
                return 1

        all_rows, have, start = load_partial()
        lock = threading.Lock()

        ws, send = fresh_tab()
        if not send:
            log("FATAL: تعذّر فتح 8510")
            return 2

        if start:
            log(f"استكمال من صف {start} — تبويب مفتوح")
        st, walked, _, total = collect_range(send, S.FROM_DATE, S.TO_DATE, all_rows, have, lock,
                                             start_got=start, persist=persist_rows)
        close_tab(ws, send)

        if st != "ok":
            log(f"توقف — محفوظ جزئياً: {len(all_rows)}/{total}")
            return 3

        hole = total - len(all_rows)
        if hole > 30:
            log(f"ناقص {hole} صف — تبقى data_partial.xlsx")
            return 3
        if hole > 0:
            log(f"فجوة صغيرة {hole} صف (بيانات حيّة تتغير) — مقبول")

        try:
            cols = S.COLS[:min(len(all_rows[0]), len(S.COLS))]
            pd.DataFrame(all_rows, columns=cols).to_excel("data.xlsx", index=False, engine="openpyxl")
        except Exception:
            pass
        for f in ("data_partial.xlsx", "progress.meta"):
            try:
                os.remove(f)
            except Exception:
                pass
        log(f"اكتمل: {len(all_rows)}/{total} صف في {int((time.time()-t_all)//60)}د {int((time.time()-t_all)%60)}ث")
        commit_push()
    finally:
        try:
            os.remove(lockf)
        except Exception:
            pass

if __name__ == "__main__":
    sys.exit(main())