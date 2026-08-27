# -*- coding: utf-8 -*-
# تنفيذ السحب التلقائي الكامل: BLS ثم UPS مع إعادة محاولة وتسجيل ورَفع git
import subprocess, sys, os, json, time
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8')

PROJ = r"C:\Users\anaf\OneDrive - Riyadh Municipality\المستندات\Default Project\rkhass-dashboard"
PY   = r"C:\Users\anaf\AppData\Local\Programs\Python\Python312\python.exe"
HIST = os.path.join(PROJ, "monitor_history.jsonl")
LOG  = os.path.join(PROJ, "monitor_log.txt")

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

def run_script(name, label, retries, gap=90):
    entry = {"ts": datetime.now().isoformat(), "label": label, "prog": name}
    for attempt in range(1, retries + 2):
        t0 = time.time()
        try:
            r = subprocess.run([PY, os.path.join(PROJ, name)], cwd=PROJ,
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=5400)
            tail = (r.stdout + r.stderr)[-300:]
            entry.update({"status": "OK", "attempt": attempt, "secs": round(time.time() - t0)})
            append(entry)
            write_log(f"{label}: نجاح في المحاولة {attempt} ({entry['secs']} ثانية)")
            return True
        except subprocess.TimeoutExpired:
            entry.update({"status": "TIMEOUT", "attempt": attempt, "secs": round(time.time() - t0)})
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

def git_push_if_changed():
    try:
        subprocess.run(["git", "add", "-A"], cwd=PROJ, check=True, capture_output=True)
        r = subprocess.run(["git", "commit", "-m",
                            f"update data {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
                           cwd=PROJ, capture_output=True, text=True)
        if r.returncode != 0:
            return "لا توجد تغييرات"
        p = subprocess.run(["git", "push", "origin", "main"], cwd=PROJ,
                           capture_output=True, text=True, timeout=90)
        return "تم الرفع" if p.returncode == 0 else "خطأ: " + (p.stderr or "")[:150]
    except Exception as e:
        return "git error: " + str(e)[:150]

write_log("===== تشغيل خط الإنتاج التلقائي =====")
bls = run_script("scraper.py", "BLS", retries=2)
time.sleep(5)
ups = run_script("ups_scraper.py", "UPS", retries=1)
push = git_push_if_changed()
entry = {"ts": datetime.now().isoformat(), "label": "pipeline",
         "bls": "OK" if bls else "FAIL", "ups": "OK" if ups else "FAIL", "push": push}
append(entry)
write_log(f"انتهى: BLS={'ok' if bls else 'fail'} | UPS={'ok' if ups else 'fail'} | رفع: {push}")

# تحديث التقرير اليومي (يتضمن تذكير نهاية فترة الـ10 أيام)
try:
    subprocess.run([PY, os.path.join(PROJ, "generate_report.py")], cwd=PROJ,
                   capture_output=True, timeout=120)
except Exception:
    pass