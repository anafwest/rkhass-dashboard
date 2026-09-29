# -*- coding: utf-8 -*-
"""ups_loop.py — حلقة دائمة لتحديث UPS في الخلفية.

- كل UPS_INTERVAL_MIN دقيقة (افتراضي 30) يشغّل ups_sync_fast.main()
- ينظّف قفل عالق لو انقطع تشغيل سابق
- يتوقف فقط بإنشاء ملف ups_loop.stop: echo stop > ups_loop.stop
التشغيل: pythonw ups_loop.py   (بدون نافذة) أو  python ups_loop.py
"""
import os, sys, time
from datetime import datetime

PROJ = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJ)
INTERVAL_MIN = int(os.environ.get("UPS_INTERVAL_MIN", "30"))
STOP_FILE = os.path.join(PROJ, "ups_loop.stop")
LOCK_FILE = os.path.join(PROJ, "ups_sync.lock")

def log(msg):
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{t}] [loop] {msg}", flush=True)
    try:
        with open(os.path.join(PROJ, "ups_sync_log.txt"), "a", encoding="utf-8") as f:
            f.write(f"[{t}] [loop] {msg}\n")
    except Exception:
        pass

def stale_lock():
    """قفل أقدم من 20 دقيقة = عالق من تشغيل مقصوص."""
    try:
        return time.time() - os.path.getmtime(LOCK_FILE) > 20 * 60
    except Exception:
        return False

def main():
    import ups_sync_fast as U
    log(f"بدء حلقة UPS الدائمة (كل {INTERVAL_MIN} دقيقة) — pid={os.getpid()}")
    while True:
        if os.path.exists(STOP_FILE):
            log("تم إيقاف الحلقة (ups_loop.stop) — خروج")
            return
        if os.path.exists(LOCK_FILE) and stale_lock():
            try:
                os.remove(LOCK_FILE)
                log("إزالة قفل عالق")
            except Exception:
                pass
        try:
            code = U.main()
            log(f"دورة سحب: انتهت بالكود {code}")
        except Exception as e:
            log(f"خطأ في الدورة: {e!r}")
        log(f"انتظار {INTERVAL_MIN} دقيقة للدورة التالية...")
        time.sleep(INTERVAL_MIN * 60)

if __name__ == "__main__":
    main()