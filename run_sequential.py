# -*- coding: utf-8 -*-
"""قراءة متسلسلة سريعة لجدول BLS8510 على تبويب واحد نظيف ADF
مع إنعاش الجلسة كل كتلة، وإعادة فتح تبويب جديد عند الركود، وحارس حفظ آمن."""
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

def open_fresh():
    """تبويب جديد بحالة ADF نظيفة، شاشة 8510، بحث جاهز."""
    nb = S.open_tab()
    if not nb:
        log("FATAL: تعذر فتح تبويب جديد")
        return None, None, None
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
        if not S.ensure_8510(send):
            log("FATAL: شاشة 8510 لم تُفتح في التبويب الجديد")
            return ws, send, None
    return ws, send, refresh_search(send)

def refresh_search(send):
    S.ensure_dates(send)
    S.click_search(send)
    return S.wait_search(send, timeout=25)

def work_slice(send, start_page, end_page, pp, all_rows, have):
    cur = start_page
    if cur > 1:
        if not S.jump_page(send, cur, pp):
            info = refresh_search(send)
            if info.get("rows") and S.jump_page(send, cur, pp):
                pass
            else:
                log(f"  تعذر القفز لبداية الشريحة {cur}")
                return "jump-fail"
    streak = 0
    while cur <= end_page:
        info = S.read_info(send)
        rows = info.get("rows", [])
        if not rows:
            streak += 1
            log(f"  صفحة {cur} رجعت بلا صفوف (streak {streak})")
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
        info2 = S.wait_advance(send, cur*pp, timeout=8)
        if info2:
            cur += 1; streak = 0
            continue
        streak += 1
        log(f"  تقدم الصفحة {cur+1} لم يُؤكد (streak {streak})")
        if streak >= 2:
            log(f"  تعثر عند صفحة {cur} — إعادة بحث متجددة")
            info = refresh_search(send)
            if info.get("rows") and S.jump_page(send, cur+1, pp):
                cur += 1; streak = 0
                continue
        if streak >= 5:
            return "stall"
    return "ok"

def main():
    S.log = log
    log("=== قراءة سريعة بتبويب نظيف + حارس حفظ ===")
    ws, send, info = open_fresh()
    if not send:
        sys.exit(1)
    if not info or not info.get("rows"):
        log("FATAL: البحث الأول فشل")
        try: ws.close()
        except Exception: pass
        sys.exit(1)
    total = info["total"]; pp = info["perPage"]
    pages = (total + pp - 1)//pp
    log(f"بيانات: {total} سجل، {pages} صفحة ({pp} للصفحة)")

    all_rows = []; have = set(["","-"])
    cur = 1; stalls = 0
    t_start = time.time()
    while cur <= pages:
        end = min(cur + REFRESH_EVERY - 1, pages)
        status = work_slice(send, cur, end, pp, all_rows, have)
        log(f"الشريحة {cur}-{end}: {status} | المجموع {len(all_rows)}")
        if status != "ok":
            stalls += 1
            if stalls >= 3:
                log("حد أقصى من الركود — توقف")
                break
            log(f"ركود — فتح تبويب نظيف من صفحة {cur}...")
            try: send("Page.close"); ws.close()
            except Exception: pass
            ws, send, info2 = open_fresh()
            if not send:
                break
            if info2 and info2.get("rows"):
                if not S.jump_page(send, cur, pp):
                    info = refresh_search(send)
                    if not info.get("rows") or not S.jump_page(send, cur, pp):
                        continue
                continue  # أعد الشريحة نفسها في التبويب الجديد
            else:
                break
        if end >= pages:
            break
        info = refresh_search(send)
        if not info.get("rows"):
            log("ERROR: البحث المتجدد فشل")
            break
        cur = end + 1
    elapsed = time.time()-t_start
    log(f"جمع {len(all_rows)} صف من أصل {total} في {int(elapsed//60)}د {int(elapsed%60)}ث")

    # تعويض النقص (كِتل مع بحث متجدد)
    if len(all_rows) < total - 5:
        log("بدء تعويض النقص...")
        try:
            pass
        except Exception:
            pass
        cur2 = 1
        while cur2 <= pages:
            info = refresh_search(send)
            if not info.get("rows"):
                break
            if not S.jump_page(send, cur2, pp):
                cur2 += REFRESH_EVERY
                continue
            end = min(cur2 + REFRESH_EVERY - 1, pages)
            while cur2 <= end:
                info = S.read_info(send)
                for r in info.get("rows", []):
                    if len(r) >= 10 and str(r[0]) not in have:
                        have.add(str(r[0])); all_rows.append(r)
                if cur2 >= end:
                    break
                S.click_next(send); S.wait_advance(send, cur2*pp, timeout=8)
                cur2 += 1
            log(f"تعويض حتى صفحة {cur2}: {len(all_rows)} صف")
            cur2 += 1
    try: ws.close()
    except Exception: pass

    # إزالة تكرار نهائي
    seen = set(); dedup = []
    for r in all_rows:
        k = tuple(r)
        if len(r) < 10 or k in seen: continue
        seen.add(k); dedup.append(r)
    all_rows = dedup
    log(f"بعد إزالة التكرار: {len(all_rows)}")

    ok = len(all_rows) >= total - 5
    if not ok:
        cols = S.COLS[:min(len(all_rows[0]), len(S.COLS))]
        try:
            pd.DataFrame(all_rows, columns=cols).to_excel("data_partial.xlsx", index=False, engine="openpyxl")
        except Exception:
            pass
        log(f"حارس الحفظ: الجمع ناقص {len(all_rows)}/{total} — لن أُعدّل data.xlsx")
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