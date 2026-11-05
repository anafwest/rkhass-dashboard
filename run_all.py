# -*- coding: utf-8 -*-
# خط الإنتاج: مزامنة BLS التزايدية ثم سحب UPS الموثّق.
# النشر هنا مقيّد بملفات البيانات فقط (لا git add -A، ولا force push).
import json
import os
import subprocess
import sys
import time
from datetime import datetime

import ups_core as core

PROJ = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
HIST = os.path.join(PROJ, "monitor_history.jsonl")
LOG = os.path.join(PROJ, "monitor_log.txt")
PUBLISH_LOCK = os.path.join(PROJ, "publish.lock")

# الملفات المسموح بنشرها من خط الإنتاج (لا أسرار ولا جلسات ولا ملفات غير متعلقة)
ALLOWED_PUBLISH = {
    "ups_requests.xlsx",
    "ups_prev.xlsx",
    "ups_sync_state.json",
}
PUBLISH_BRANCH = os.environ.get("UPS_PUBLISH_BRANCH", "main")


def write_log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass
    print(msg)


def append(entry):
    try:
        with open(HIST, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def find_git():
    for c in (
        os.environ.get("GIT_EXE"),
        r"C:\Users\HPProBook440G9\AppData\Local\Programs\Git\bin\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\bin\git.exe",
        "git",
    ):
        if not c:
            continue
        if os.path.exists(c):
            return c
        try:
            r = subprocess.run([c, "--version"], capture_output=True, text=True)
            if r.returncode == 0:
                return c
        except Exception:
            continue
    return None


def run_script(name, label, retries, gap=60, ok_codes=(0,)):
    entry = {"ts": datetime.now().isoformat(), "label": label, "prog": name}
    for attempt in range(1, retries + 2):
        t0 = time.time()
        try:
            r = subprocess.run([PY, os.path.join(PROJ, name)], cwd=PROJ,
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=2700)
            tail = (r.stdout + r.stderr)[-300:]
            if r.returncode not in ok_codes:
                entry.update({"status": "FAIL", "attempt": attempt, "rc": r.returncode,
                              "secs": round(time.time() - t0), "tail": tail})
                append(entry)
                write_log(f"{label}: فشل في المحاولة {attempt} (رمز {r.returncode})")
            else:
                entry.update({"status": "OK", "attempt": attempt,
                              "secs": round(time.time() - t0)})
                append(entry)
                write_log(f"{label}: نجاح في المحاولة {attempt} ({entry['secs']} ثانية)")
                return True
        except subprocess.TimeoutExpired:
            entry.update({"status": "TIMEOUT", "attempt": attempt,
                          "secs": round(time.time() - t0)})
            append(entry)
            write_log(f"{label}: مهلة زمنية في المحاولة {attempt}")
        except Exception as e:
            entry.update({"status": "ERROR", "attempt": attempt, "err": str(e)[:150]})
            append(entry)
            write_log(f"{label}: خطأ تشغيل {e}")
        if attempt <= retries:
            write_log(f"{label}: إعادة المحاولة بعد {gap} ثانية...")
            time.sleep(gap)
    return False


def git_publish():
    """نشر مقيّد: ملفات بيانات محددة فقط + فحص المرحلي + رفض force push."""
    git = find_git()
    if not git:
        return "git غير موجود — حفظ محلي فقط"
    lock = core.RunLock(PUBLISH_LOCK)
    ok, msg = lock.acquire()
    if not ok:
        return f"قفل نشر مشغول: {msg}"
    try:
        branch = subprocess.run([git, "rev-parse", "--abbrev-ref", "HEAD"],
                                cwd=PROJ, capture_output=True, text=True).stdout.strip()
        if branch != PUBLISH_BRANCH:
            return f"الفرع الحالي {branch} ليس فرع النشر {PUBLISH_BRANCH}"
        subprocess.run([git, "fetch", "origin", PUBLISH_BRANCH], cwd=PROJ,
                       capture_output=True, text=True, timeout=180)
        remote = subprocess.run([git, "rev-parse", f"origin/{PUBLISH_BRANCH}"],
                                cwd=PROJ, capture_output=True, text=True)
        local = subprocess.run([git, "rev-parse", "HEAD"], cwd=PROJ,
                               capture_output=True, text=True)
        if remote.returncode == 0 and local.returncode == 0 and \
                remote.stdout.strip() != local.stdout.strip():
            return "الفرع البعيد تغيّر — لم يتم الرفع (لا force push)"

        tracked = set(subprocess.run([git, "ls-files"], cwd=PROJ, capture_output=True,
                                     text=True).stdout.splitlines())
        existing = [f for f in sorted(ALLOWED_PUBLISH)
                    if f in tracked and os.path.exists(os.path.join(PROJ, f))]
        if not existing:
            return "لا ملفات بيانات متتبعة للنشر"
        r = subprocess.run([git, "add", "--", *existing], cwd=PROJ,
                           capture_output=True, text=True)
        if r.returncode != 0:
            return "خطأ git add: " + (r.stderr or "").strip()[:150]
        staged = subprocess.run([git, "diff", "--cached", "--name-only"], cwd=PROJ,
                                capture_output=True, text=True).stdout.splitlines()
        files = [x.strip() for x in staged if x.strip()]
        if not files:
            return "لا توجد تغييرات"
        unexpected = [f for f in files if f not in ALLOWED_PUBLISH]
        if unexpected:
            subprocess.run([git, "reset", "--", *unexpected], cwd=PROJ,
                           capture_output=True, text=True)
            return "ملفات غير مسموح بها: " + ", ".join(unexpected[:5])
        r = subprocess.run([git, "commit", "-m",
                            f"update data {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
                           cwd=PROJ, capture_output=True, text=True)
        if r.returncode != 0:
            return "لا توجد تغييرات"
        p = subprocess.run([git, "push", "origin", PUBLISH_BRANCH], cwd=PROJ,
                           capture_output=True, text=True, timeout=120)
        if p.returncode == 0:
            sha = subprocess.run([git, "rev-parse", "HEAD"], cwd=PROJ,
                                 capture_output=True, text=True).stdout.strip()
            return f"تم الرفع ({sha[:12]})"
        return "خطأ: " + (p.stderr or "")[:150]
    except Exception as e:
        return "git error: " + str(e)[:150]
    finally:
        lock.release()


write_log("===== تشغيل خط الإنتاج التلقائي (مزامنة تزايدية) =====")
time.sleep(5)
bls = run_script("update_bls_delta.py", "BLS-delta", retries=2)
time.sleep(5)
ups = run_script("ups_sync_fast.py", "UPS-verified", retries=1, ok_codes=(0, 75))
push = git_publish()
entry = {"ts": datetime.now().isoformat(), "label": "pipeline",
         "bls": "OK" if bls else "FAIL", "ups": "OK" if ups else "FAIL", "push": push}
append(entry)
write_log(f"انتهى: BLS={'ok' if bls else 'fail'} | UPS={'ok' if ups else 'fail'} | رفع: {push}")

try:
    subprocess.run([PY, os.path.join(PROJ, "generate_report.py")], cwd=PROJ,
                   capture_output=True, timeout=120)
except Exception:
    pass
