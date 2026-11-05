# -*- coding: utf-8 -*-
"""ups_sync_fast.py — سحب UPS موثّق عبر جلسة المتصفح (CDP).

المبادئ:
- لا تسجيل دخول آلي ولا OTP: يستخدم جلسة Chrome المسجّلة يدويًا على الجهاز.
- لا اعتماد إلا بتغطية 100% من الصفحات المتوقعة وثبات الإجمالي أثناء السحب.
- لا دمج تراكمي: اللقطة تمثل صفوف السحب الحالي فقط.
- كشف الصفحات المكررة/الفاشلة وتكرار أرقام الطلبات قبل أي حفظ.
- كتابة ذرّية + حالة موثقة (SHA-256 + عدد الصفوف) + نشر منفصل عن الحفظ.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime
from queue import Empty, Queue
from typing import Any

import pandas as pd
import websocket

import ups_core as core

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "ups_sync_log.txt")
STATE_FILE = os.path.join(BASE_DIR, "ups_sync_state.json")
ATTEMPT_FILE = os.path.join(BASE_DIR, "ups_sync_last_attempt.json")
PUBLISH_FILE = os.path.join(BASE_DIR, "ups_sync_publish.json")
DATA_FILE = os.path.join(BASE_DIR, "ups_requests.xlsx")
PREV_FILE = os.path.join(BASE_DIR, "ups_prev.xlsx")
LOCK_FILE = os.path.join(BASE_DIR, "ups_sync.lock")

COLS = core.COLS
KEY = core.KEY

PORT = int(os.environ.get("UPS_CDP_PORT", "9222"))
PAGE_URL = os.environ.get(
    "UPS_PAGE_URL",
    "https://ups-backoffice.alriyadh.gov.sa/ar/building-license-department?activeTab=requests",
)
WORKERS = max(1, int(os.environ.get("UPS_WORKERS", "5")))
RETRIES = max(1, int(os.environ.get("UPS_PAGE_RETRIES", "3")))
PAGE_TIMEOUT = float(os.environ.get("UPS_PAGE_TIMEOUT", "45"))
STAGGER = float(os.environ.get("UPS_STAGGER", "1.5"))
PUBLISH_BRANCH = os.environ.get("UPS_PUBLISH_BRANCH", "main")
PUBLISH_ENABLED = os.environ.get("UPS_PUBLISH", "1") not in {"0", "false", "no"}
ALLOW_FILTERS = os.environ.get("UPS_ALLOW_FILTERS", "0") in {"1", "true", "yes"}

EXIT_OK = 0
EXIT_FATAL = 1
EXIT_LOGIN = 2
EXIT_INCOMPLETE = 3
EXIT_PUBLISH = 4
EXIT_GIT = 5
EXIT_LOCKED = 75

ALLOWED_PUBLISH = {"ups_requests.xlsx", "ups_prev.xlsx", "ups_sync_state.json"}


def log(msg: str) -> None:
    line = f"[{core.iso_riyadh()}] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    try:
        if sys.stdout:
            print(line, flush=True)
    except Exception:
        pass


def write_attempt(payload: dict[str, Any]) -> None:
    try:
        core.write_state_atomic(payload, ATTEMPT_FILE)
    except Exception as e:
        log(f"تعذر كتابة {os.path.basename(ATTEMPT_FILE)}: {e}")


class LoginRequired(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# CDP
# ---------------------------------------------------------------------------
def cdp_http(path: str, method: str = "GET") -> Any:
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method)
    return json.loads(urllib.request.urlopen(req, timeout=15).read())


def cdp_alive() -> bool:
    try:
        return bool(cdp_http("/json/version"))
    except Exception:
        return False


def list_targets() -> list[dict[str, Any]]:
    try:
        return cdp_http("/json")
    except Exception:
        return []


def create_target(url: str) -> dict[str, Any] | None:
    try:
        return cdp_http("/json/new?" + urllib.parse.quote(url, safe=":/?=&%"), method="PUT")
    except Exception as e:
        log(f"تعذر إنشاء تبويب عبر /json/new: {e}")
    try:
        ver = cdp_http("/json/version")
        ws = websocket.create_connection(ver["webSocketDebuggerUrl"], timeout=20)
        try:
            ws.send(json.dumps({"id": 1, "method": "Target.createTarget",
                                "params": {"url": url}}))
            deadline = time.time() + 20
            while time.time() < deadline:
                r = json.loads(ws.recv())
                if r.get("id") == 1:
                    tid = (r.get("result") or {}).get("targetId")
                    if tid:
                        for t in list_targets():
                            if t.get("id") == tid:
                                return t
                    return {"id": tid, "webSocketDebuggerUrl": None}
        finally:
            try:
                ws.close()
            except Exception:
                pass
    except Exception as e:
        log(f"تعذر إنشاء تبويب عبر Target.createTarget: {e}")
    return None


def close_target(target: dict[str, Any] | None) -> None:
    if not target or not target.get("id"):
        return
    try:
        cdp_http(f"/json/close/{target['id']}")
    except Exception:
        pass


class CDP:
    def __init__(self, ws_url: str, timeout: float = 30):
        self.ws = websocket.create_connection(ws_url, timeout=timeout)
        self._id = 0
        self._lock = threading.Lock()

    def send(self, method: str, params: dict[str, Any] | None = None,
             timeout: float = 30) -> dict[str, Any]:
        with self._lock:
            self._id += 1
            mid = self._id
            self.ws.send(json.dumps({"id": mid, "method": method,
                                     "params": params or {}}))
            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    self.ws.settimeout(max(0.5, deadline - time.time()))
                    raw = self.ws.recv()
                except websocket.WebSocketTimeoutException:
                    break
                except Exception as e:
                    raise RuntimeError(f"انقطع اتصال CDP: {e}") from e
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if msg.get("id") != mid:
                    continue
                if "error" in msg:
                    raise RuntimeError(f"CDP {method}: {msg['error']}")
                return msg.get("result", {}) or {}
            raise TimeoutError(f"مهلة CDP في {method}")

    def eval(self, expr: str, timeout: float = 30) -> Any:
        r = self.send("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": True,
        }, timeout=timeout)
        res = r.get("result", {}) or {}
        if res.get("subtype") == "error":
            raise RuntimeError(f"JS error: {res.get('description', '')[:300]}")
        return res.get("value")

    def navigate(self, url: str) -> None:
        self.send("Page.navigate", {"url": url}, timeout=30)

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Chrome
# ---------------------------------------------------------------------------
def find_chrome() -> str | None:
    candidates = [
        os.environ.get("UPS_CHROME_PATH", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        shutil.which("chrome") or "",
        shutil.which("google-chrome") or "",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def chrome_profile() -> str:
    p = os.environ.get("UPS_PROFILE_DIR") or os.path.join(BASE_DIR, "chrome_profile")
    os.makedirs(p, exist_ok=True)
    return p


def start_chrome() -> bool:
    chrome = find_chrome()
    if not chrome:
        log("FATAL: لم يُعثر على chrome.exe")
        return False
    prof = chrome_profile()
    args = [
        chrome,
        f"--remote-debugging-port={PORT}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--disable-popup-blocking",
        f"--user-data-dir={prof}",
        '--host-resolver-rules=MAP ups-backoffice.alriyadh.gov.sa 10.111.111.75',
        "https://app.alriyadh.gov.sa/SSO/faces/login",
    ]
    log("تشغيل Chrome المخصص (بدون تسجيل دخول آلي)...")
    creation = 0x08000000 if os.name == "nt" else 0
    try:
        subprocess.Popen(args, creationflags=creation)
    except Exception as e:
        log(f"FATAL: تعذر تشغيل Chrome: {e}")
        return False
    for _ in range(40):
        time.sleep(1)
        if cdp_alive():
            return True
    return False


def ensure_chrome() -> bool:
    if cdp_alive():
        return True
    return start_chrome()


# ---------------------------------------------------------------------------
# قراءة الصفحة
# ---------------------------------------------------------------------------
READ_JS = r"""
(function(){
  var out = {
    url: location.href,
    title: document.title,
    login: false,
    page: null,
    total_pages: null,
    total_results_text: "",
    rows: [],
    headers: [],
    text: "",
    empty: false,
    filters: []
  };
  var txt = document.body ? document.body.innerText : "";
  out.text = txt.slice(0, 6000);
  out.login = !!document.getElementById('unameInputId') ||
               !!document.getElementById('pt1:unameInputId') ||
               /\/faces\/login/i.test(location.href);
  out.empty = /لا\s*توجد\s*(?:بيانات|نتائج|سجلات)|no\s+(?:data|records|results)/i.test(txt);

  var m = txt.match(/الصفحة\s*(\d+)\s*من\s*(\d+)/);
  if (!m) { m = txt.match(/Page\s*(\d+)\s*of\s*(\d+)/i); }
  if (m) {
    out.page = parseInt(m[1], 10);
    out.total_pages = parseInt(m[2], 10);
  }

  var best = null, bestCount = -1;
  var tables = document.querySelectorAll('table');
  for (var i = 0; i < tables.length; i++) {
    var c = tables[i].querySelectorAll('tbody tr').length;
    if (c > bestCount) { bestCount = c; best = tables[i]; }
  }
  if (best) {
    var ths = best.querySelectorAll('thead th');
    for (var j = 0; j < ths.length; j++) {
      var h = (ths[j].innerText || '').trim();
      if (h) { out.headers.push(h); }
    }
    var trs = best.querySelectorAll('tbody tr');
    for (var k = 0; k < trs.length; k++) {
      var tds = trs[k].querySelectorAll('td');
      if (!tds.length) { continue; }
      var row = [];
      for (var q = 0; q < tds.length; q++) {
        row.push((tds[q].innerText || '').replace(/\s+/g, ' ').trim());
      }
      out.rows.push(row);
    }
  }

  try {
    var sels = document.querySelectorAll('select');
    for (var s = 0; s < sels.length; s++) {
      var el = sels[s];
      if (el.value) {
        out.filters.push({type: 'select', name: el.name || el.id || '',
                          value: el.value,
                          label: (el.options[el.selectedIndex] || {}).text || ''});
      }
    }
    var ins = document.querySelectorAll('input[type=text], input[type=search]');
    for (var n = 0; n < ins.length; n++) {
      var inp = ins[n];
      if (inp.value && inp.offsetParent !== null) {
        out.filters.push({type: 'input', name: inp.name || inp.id || '',
                          value: inp.value});
      }
    }
  } catch (e) {}

  return JSON.stringify(out);
})()
"""


def read_page(cdp: CDP) -> dict[str, Any]:
    raw = cdp.eval(READ_JS, timeout=30)
    if not isinstance(raw, str):
        raise RuntimeError(f"استجابة غير متوقعة من الصفحة: {type(raw)}")
    try:
        return json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"تعذر تحليل محتوى الصفحة: {e}") from e


def parse_number(text: str) -> int | None:
    if text is None:
        return None
    digits = re.sub(r"[^\d]", "", str(text))
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def parse_total_results(text: str) -> int | None:
    if not text:
        return None
    t = re.sub(r"(?:الصفحة|Page)\s*\d+\s*(?:من|of)\s*\d+", " ", text, flags=re.I)
    patterns = [
        r"(?:إجمالي|مجموع)\s*(?:النتائج|الطلبات|السجلات|العناصر)?\s*[:：]?\s*([\d,٬\.]+)",
        r"(?:Total|Results|Records)\s*[:：]?\s*([\d,٬\.]+)",
        r"(?:عرض|Showing)[^\n]{0,80}?(?:من|of)\s*([\d,٬\.]+)",
        r"(?:من|of)\s*أصل\s*([\d,٬\.]+)",
    ]
    for pat in patterns:
        m = re.search(pat, t, flags=re.I)
        if m:
            n = parse_number(m.group(1))
            if n is not None:
                return n
    return None


def page_url(n: int) -> str:
    parts = urllib.parse.urlsplit(PAGE_URL)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
             if k.lower() != "page"]
    if n > 1:
        query.append(("page", str(n)))
    return urllib.parse.urlunsplit((
        parts.scheme, parts.netloc, parts.path,
        urllib.parse.urlencode(query), parts.fragment,
    ))


def wait_for_page(cdp: CDP, page_num: int, timeout: float = PAGE_TIMEOUT) -> dict[str, Any] | None:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            info = read_page(cdp)
        except LoginRequired:
            raise
        except Exception:
            time.sleep(0.75)
            continue
        if info.get("login"):
            raise LoginRequired("الصفحة الحالية هي شاشة دخول")
        last = info
        if page_num == 1:
            if info.get("rows") or info.get("empty") or info.get("total_results_text"):
                if info.get("page") in (None, 1):
                    return info
        else:
            if info.get("page") == page_num and info.get("rows"):
                return info
        time.sleep(0.75)
    return last


def click_page_number(cdp: CDP, page_num: int) -> bool:
    expr = r"""
    (function(){
      var n = %d;
      var els = document.querySelectorAll('a,button,li,span');
      for (var i = 0; i < els.length; i++) {
        var t = (els[i].innerText || '').trim();
        if (t === String(n) && els[i].offsetParent !== null) {
          els[i].click();
          return true;
        }
      }
      return false;
    })()
    """ % int(page_num)
    try:
        return bool(cdp.eval(expr))
    except Exception:
        return False


def fetch_page(cdp: CDP, page_num: int) -> dict[str, Any]:
    url = page_url(page_num)
    last_error = "غير معروف"
    for attempt in range(1, RETRIES + 1):
        try:
            try:
                cdp.navigate(url)
            except Exception:
                cdp.eval("location.href = %s" % json.dumps(url))
            info = wait_for_page(cdp, page_num, PAGE_TIMEOUT)
            if info and info.get("login"):
                raise LoginRequired("انتهت جلسة الدخول أثناء السحب")
            if info and (info.get("page") == page_num or page_num == 1):
                if info.get("rows") or info.get("empty"):
                    raw_rows = info.get("rows") or []
                    headers = info.get("headers") or []
                    mapped = map_rows(raw_rows, headers)
                    rows = [dict(zip(COLS, r)) for r in mapped]
                    return {
                        "rows": rows,
                        "reported_page": info.get("page"),
                        "total_pages": info.get("total_pages"),
                        "total_results": parse_total_results(info.get("text", "")),
                        "total_results_text": info.get("total_results_text", ""),
                        "url": info.get("url"),
                        "fingerprint": core.page_fingerprint(rows),
                        "row_count": len(rows),
                        "headers": headers,
                        "filters": info.get("filters") or [],
                        "empty": bool(info.get("empty")),
                        "error": None,
                        "attempts": attempt,
                    }
            last_error = f"الصفحة لم تُطابق المطلوب (المعروض {info.get('page') if info else None})"
        except LoginRequired:
            raise
        except Exception as e:
            last_error = str(e)[:200]
        # محاولة بديلة: إعادة تحميل ثم النقر على رقم الصفحة
        try:
            cdp.eval("location.reload()")
        except Exception:
            pass
        time.sleep(1.5)
        if attempt < RETRIES:
            click_page_number(cdp, page_num)
            time.sleep(1.0)
    return {
        "rows": [],
        "reported_page": None,
        "total_pages": None,
        "total_results": None,
        "url": url,
        "fingerprint": None,
        "row_count": 0,
        "headers": [],
        "filters": [],
        "empty": False,
        "error": last_error,
        "attempts": RETRIES,
    }


def map_rows(raw_rows: list[list[str]], headers: list[str]) -> list[list[str]]:
    """إعادة ترتيب الأعمدة حسب العناوين إن أمكن، وإلا بالترتيب الموضعي."""
    if not raw_rows:
        return []
    index: dict[str, int] = {}
    for i, h in enumerate(headers):
        hh = core.clean_cell(h)
        for c in COLS:
            if c in index:
                continue
            if hh == c or c in hh or hh in c:
                index[c] = i
    if all(c in index for c in COLS):
        order = [index[c] for c in COLS]
    else:
        order = list(range(len(COLS)))
    out = []
    for row in raw_rows:
        out.append([row[i] if i < len(row) else "" for i in order])
    return out


# ---------------------------------------------------------------------------
# النشر
# ---------------------------------------------------------------------------
def find_git() -> str | None:
    candidates = [
        shutil.which("git"),
        r"C:\Users\HPProBook440G9\AppData\Local\Programs\Git\bin\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\bin\git.exe",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def git_run(git: str, args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run([git, *args], cwd=BASE_DIR, capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, creationflags=0x08000000 if os.name == "nt" else 0)


def publish_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    """نشر صريح لملفات اللقطة فقط. لا force push ولا git add -A."""
    git = find_git()
    if not git:
        return {"status": "failed", "error": "git غير موجود"}
    try:
        branch = git_run(git, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
        if branch != PUBLISH_BRANCH:
            return {"status": "blocked",
                    "error": f"الفرع الحالي {branch} ليس فرع النشر {PUBLISH_BRANCH}"}

        # لا نتجاوز تغييرات الآخرين: نتحقق أن الفرع البعيد لم يتقدم
        git_run(git, ["fetch", "origin", PUBLISH_BRANCH], timeout=180)
        remote = git_run(git, ["rev-parse", f"origin/{PUBLISH_BRANCH}"])
        local = git_run(git, ["rev-parse", "HEAD"])
        if remote.returncode == 0 and local.returncode == 0:
            if remote.stdout.strip() != local.stdout.strip():
                return {"status": "blocked",
                        "error": "الفرع البعيد تغيّر — لم يتم الرفع (لا force push)"}

        # فحص الملفات المرحلية قبل أي commit
        add = git_run(git, ["add", "--", *sorted(ALLOWED_PUBLISH)])
        if add.returncode != 0:
            return {"status": "failed", "error": (add.stderr or "").strip()[:300]}
        staged = git_run(git, ["diff", "--cached", "--name-only"])
        files = [x for x in staged.stdout.splitlines() if x.strip()]
        if not files:
            return {"status": "no_changes", "branch": branch}
        unexpected = [f for f in files if f not in ALLOWED_PUBLISH]
        if unexpected:
            git_run(git, ["reset", "--", *unexpected])
            return {"status": "failed",
                    "error": f"ملفات غير مسموح بها في commit: {unexpected}"}

        msg = (f"data(ups): verified snapshot {state.get('sync_finished_at', '')} "
               f"[{state.get('rows')} rows / {state.get('pages_completed')}/"
               f"{state.get('pages_expected')} pages]")
        commit = git_run(git, ["commit", "-m", msg])
        if commit.returncode != 0:
            return {"status": "failed", "error": (commit.stderr or "").strip()[:300]}
        sha = git_run(git, ["rev-parse", "HEAD"]).stdout.strip()
        push = git_run(git, ["push", "origin", PUBLISH_BRANCH], timeout=180)
        if push.returncode != 0:
            return {"status": "failed", "commit": sha,
                    "error": (push.stderr or "").strip()[:300]}
        return {"status": "ok", "commit": sha, "branch": branch,
                "pushed_at": core.iso_riyadh(), "files": files}
    except Exception as e:
        return {"status": "failed", "error": str(e)[:300]}


def record_publish(result: dict[str, Any], state_path: str = STATE_FILE) -> None:
    try:
        core.write_state_atomic(result, PUBLISH_FILE)
    except Exception as e:
        log(f"تعذر كتابة {os.path.basename(PUBLISH_FILE)}: {e}")
    # تحديث الحالة المحلية بحالة النشر (لا يؤثر على بصمة اللقطة)
    try:
        state = core.load_state(state_path)
        if state:
            state["publish"] = result
            core.write_state_atomic(state, state_path)
    except Exception as e:
        log(f"تعذر تحديث حالة النشر: {e}")


# ---------------------------------------------------------------------------
# السحب
# ---------------------------------------------------------------------------
def worker(wid: int, q: Queue, out: dict[int, dict[str, Any]], lock: threading.Lock,
           abort: threading.Event) -> None:
    target = None
    cdp = None
    try:
        time.sleep(STAGGER * wid)
        target = create_target(PAGE_URL)
        if not target or not target.get("webSocketDebuggerUrl"):
            with lock:
                out[-wid] = {"rows": [], "error": "تعذر إنشاء تبويب عامل", "reported_page": None,
                             "total_pages": None, "total_results": None, "fingerprint": None}
            return
        cdp = CDP(target["webSocketDebuggerUrl"])
        while not abort.is_set():
            try:
                page = q.get_nowait()
            except Empty:
                break
            if page is None:
                break
            try:
                res = fetch_page(cdp, page)
            except LoginRequired as e:
                with lock:
                    out[page] = {"rows": [], "error": f"login: {e}", "reported_page": None,
                                 "total_pages": None, "total_results": None,
                                 "fingerprint": None, "row_count": 0}
                abort.set()
                break
            with lock:
                out[page] = res
            if res.get("error"):
                log(f"عامل {wid + 1}: صفحة {page} فشلت: {res['error']}")
    finally:
        if cdp:
            cdp.close()
        close_target(target)


def collect_pages(probe_cdp: CDP, probe_info: dict[str, Any], expected_pages: int,
                  workers: int) -> tuple[dict[int, dict[str, Any]], list[str]]:
    """يجمع الصفحات. يعيد (page_results, أخطاء)."""
    out: dict[int, dict[str, Any]] = {}
    lock = threading.Lock()
    abort = threading.Event()

    # الصفحة الأولى مقروءة مسبقًا من تبويب الفحص
    first_raw = probe_info.get("rows") or []
    first_headers = probe_info.get("headers") or []
    first_rows = [dict(zip(COLS, r)) for r in map_rows(first_raw, first_headers)]
    out[1] = {
        "rows": first_rows,
        "reported_page": probe_info.get("page"),
        "total_pages": probe_info.get("total_pages"),
        "total_results": parse_total_results(probe_info.get("text", "")),
        "url": probe_info.get("url"),
        "fingerprint": core.page_fingerprint(first_rows),
        "row_count": len(first_rows),
        "headers": first_headers,
        "filters": probe_info.get("filters") or [],
        "empty": bool(probe_info.get("empty")),
        "error": None,
        "attempts": 1,
    }

    q: Queue = Queue()
    for p in range(2, expected_pages + 1):
        q.put(p)

    threads = []
    for i in range(min(workers, max(1, expected_pages - 1))):
        t = threading.Thread(target=worker, args=(i, q, out, lock, abort), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    errors = []
    if abort.is_set():
        errors.append("انتهت جلسة الدخول أثناء السحب")
    for p, r in out.items():
        if p > 0 and r.get("error"):
            errors.append(f"صفحة {p}: {r['error']}")
        elif p < 0 and r.get("error"):
            errors.append(r["error"])
    return out, errors


def read_filters(probe_info: dict[str, Any]) -> dict[str, Any]:
    parts = urllib.parse.urlsplit(PAGE_URL)
    query = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
    allowed = {"activetab", "page", "lang"}
    unexpected_query = [k for k in query if k.lower() not in allowed]
    dom = probe_info.get("filters") or []
    meaningful = []
    for f in dom:
        v = core.clean_cell(f.get("value", ""))
        label = core.clean_cell(f.get("label", ""))
        if v and v.lower() not in {"all", "الكل", "0", "-1"} and label.lower() not in {"الكل", "all"}:
            meaningful.append(f)
    detected = bool(unexpected_query or meaningful)
    return {
        "page_url": PAGE_URL,
        "query": query,
        "unexpected_query_params": unexpected_query,
        "dom": dom,
        "meaningful": meaningful,
        "detected": detected,
        "allowed": ALLOW_FILTERS,
        "ok": (not detected) or ALLOW_FILTERS,
    }


def build_state(*, started: str, finished: str, expected_pages: int, completed_pages: int,
                coverage: float, reported_total: int | None, rows: int, stats: dict[str, Any],
                validation: dict[str, Any], diff: dict[str, Any] | None,
                filters: dict[str, Any], page_size: int | None,
                previous: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": core.STATE_SCHEMA,
        "data_origin": "live_sync",
        "bootstrap": False,
        "verified": True,
        "source": "ups_sync_fast.py (CDP)",
        "timezone": "Asia/Riyadh",
        "sync_started_at": started,
        "sync_finished_at": finished,
        "last_success": finished,
        "pages_expected": int(expected_pages),
        "pages_completed": int(completed_pages),
        "coverage": round(float(coverage), 6),
        "reported_total": reported_total,
        "page_size": page_size,
        "rows": int(rows),
        "unique_ids": int(rows),
        "duplicates": int(stats.get("exact_duplicates_dropped", 0)),
        "duplicate_page_groups": validation.get("duplicate_page_groups", []),
        "cross_page_duplicate_count": int(validation.get("cross_page_duplicate_count", 0)),
        "blank_ids": int(stats.get("blank_ids", 0)),
        "conflicting_duplicates": [],
        "added": None if diff is None else int(diff["added_count"]),
        "deleted": None if diff is None else int(diff["deleted_count"]),
        "modified": None if diff is None else int(diff["modified_count"]),
        "modified_by_field": None if diff is None else diff["modified_by_field"],
        "sample_added": [] if diff is None else diff["sample_added"],
        "sample_deleted": [] if diff is None else diff["sample_deleted"],
        "sample_modified": [] if diff is None else diff["sample_modified"],
        "previous": previous,
        "filters": filters,
        "scope": {
            "page_url": PAGE_URL,
            "query": filters.get("query", {}),
            "page_size": page_size,
            "pages_expected": int(expected_pages),
            "reported_total": reported_total,
            "total_pages_seen": validation.get("total_pages_seen", []),
            "total_results_seen": validation.get("totals_seen", []),
        },
        "publish": {"status": "pending", "branch": PUBLISH_BRANCH},
    }


def run(probe_only: bool = False, do_publish: bool = True) -> int:
    started_dt = core.now_riyadh()
    started = core.iso_riyadh(started_dt)
    attempt = {"started_at": started, "finished_at": None, "status": "running",
               "source": "ups_sync_fast.py"}
    log("=" * 60)
    log("بدء سحب UPS موثّق عبر جلسة المتصفح")

    lock = core.RunLock(LOCK_FILE)
    ok, msg = lock.acquire()
    if not ok:
        log(f"ممنوع التشغيل: {msg}")
        attempt.update({"status": "locked", "error": msg,
                        "finished_at": core.iso_riyadh()})
        write_attempt(attempt)
        return EXIT_LOCKED
    log(msg)

    probe_target = None
    probe_cdp = None
    try:
        if not ensure_chrome():
            raise RuntimeError("تعذر الوصول إلى Chrome/CDP — لم يتم تعديل أي بيانات")
        log(f"CDP متاح على 127.0.0.1:{PORT}")

        probe_target = create_target(PAGE_URL)
        if not probe_target or not probe_target.get("webSocketDebuggerUrl"):
            raise RuntimeError("تعذر إنشاء تبويب عمل — لم يتم تعديل أي بيانات")
        probe_cdp = CDP(probe_target["webSocketDebuggerUrl"])
        probe_cdp.navigate(PAGE_URL)
        info = wait_for_page(probe_cdp, 1, timeout=60)
        if not info or info.get("login"):
            raise LoginRequired("الجلسة غير مسجّلة — يلزم تسجيل الدخول يدويًا")
        if not info.get("rows") and not info.get("empty") and not info.get("total_results_text"):
            raise RuntimeError("لم تُقرأ قائمة الطلبات (صفحة فارغة أو بنية غير معروفة)")

        total_pages = info.get("total_pages")
        total_results = parse_total_results(info.get("text", ""))
        page_size = len(info.get("rows") or []) or None
        filters = read_filters(info)

        log(f"البوابة: الصفحة {info.get('page')} من {total_pages} | "
            f"إجمالي معلن: {total_results} | صفوف الصفحة الأولى: {page_size}")
        log(f"النطاق: {PAGE_URL}")
        if filters["detected"]:
            log(f"فلاتر غير متوقعة: query={filters['unexpected_query_params']} "
                f"dom={filters['meaningful']}")

        if probe_only:
            dump = {
                "info": {k: v for k, v in info.items() if k != "text"},
                "text": info.get("text", "")[:2000],
                "total_results": total_results,
                "filters": filters,
                "page_url": PAGE_URL,
            }
            print(json.dumps(dump, ensure_ascii=False, indent=2))
            attempt.update({"status": "probe_ok", "finished_at": core.iso_riyadh()})
            write_attempt(attempt)
            return EXIT_OK

        if not filters["ok"]:
            raise RuntimeError(
                "فلاتر غير مقصودة على البوابة — لن يتم اعتماد السحب. "
                "أزل الفلاتر أو اضبط UPS_ALLOW_FILTERS=1 بعد المراجعة."
            )

        explicit_zero = False
        if total_pages is None:
            if total_results == 0 and info.get("empty"):
                total_pages = 0
                explicit_zero = True
            elif total_results and page_size:
                total_pages = (total_results + page_size - 1) // page_size
                log(f"تحذير: لا يوجد عدّاد صفحات — اشتقاق {total_pages} صفحة من الإجمالي")
            else:
                raise RuntimeError("تعذر تحديد عدد الصفحات المتوقعة — لا يمكن إثبات التغطية")
        if total_pages == 0:
            if not (total_results == 0 or info.get("empty")):
                raise RuntimeError("البوابة لم تؤكد أن الإجمالي صفر")
            explicit_zero = True
        if total_pages < 0:
            raise RuntimeError(f"عدد صفحات غير صالح: {total_pages}")

        log(f"الصفحات المتوقعة: {total_pages} | تغطية مطلوبة: 100%")
        if total_pages > 0:
            page_results, errors = collect_pages(probe_cdp, info, total_pages, WORKERS)
            page_results = {p: r for p, r in page_results.items() if int(p) > 0}
            if errors:
                for e in errors[:10]:
                    log(f"خطأ سحب: {e}")
        else:
            page_results = {}

        validation = core.validate_sync_completion(
            page_results,
            expected_pages=total_pages,
            reported_total=total_results,
            page_size=page_size,
            explicit_zero=explicit_zero,
        )
        log(f"التحقق: ok={validation['ok']} | تغطية "
            f"{validation['pages_completed']}/{validation['pages_expected']} | "
            f"فريد {validation['unique_ids']}")
        for issue in validation["issues"]:
            log(f"  - {issue}")
        if not validation["ok"]:
            raise core.SnapshotError("السحب غير مكتمل/غير متطابق: " + " | ".join(validation["issues"][:5]))

        # تجميع الصفوف: كل صفوف السحب الحالي فقط
        all_rows: list[dict[str, str]] = []
        for p in sorted(page_results):
            if p < 1:
                continue
            all_rows.extend(page_results[p].get("rows") or [])
        new_df, stats = core.frame_from_rows(all_rows, COLS)
        if len(new_df) != validation["unique_ids"]:
            raise core.SnapshotError(
                f"عدد الصفوف بعد التطبيع {len(new_df)} لا يطابق الفريد {validation['unique_ids']}"
            )

        # الفرق مع اللقطة المعتمدة السابقة (كل الحقول)
        previous: dict[str, Any] = {"rows": None, "sha256": None, "readable": False}
        old_df = None
        if os.path.exists(DATA_FILE):
            try:
                old_df = core.read_snapshot(DATA_FILE, COLS)
                previous = {"rows": int(len(old_df)),
                            "sha256": core.file_sha256(DATA_FILE),
                            "readable": True}
            except Exception as e:
                previous = {"rows": None, "sha256": None, "readable": False,
                            "error": str(e)[:200]}
                log(f"تحذير: تعذر قراءة اللقطة السابقة للفرق: {e}")
        diff = core.diff_snapshots(old_df, new_df, COLS) if old_df is not None else None
        if diff:
            log(f"الفرق: مضاف {diff['added_count']} | محذوف {diff['deleted_count']} | "
                f"معدل {diff['modified_count']} | الحقول: {diff['modified_by_field']}")

        finished = core.iso_riyadh()
        state = build_state(
            started=started, finished=finished,
            expected_pages=total_pages,
            completed_pages=validation["pages_completed"],
            coverage=validation["coverage"],
            reported_total=total_results,
            rows=len(new_df), stats=stats, validation=validation,
            diff=diff, filters=filters, page_size=page_size, previous=previous,
        )

        result = core.commit_snapshot(
            new_df, DATA_FILE, PREV_FILE, STATE_FILE, state,
            COLS, require_verified=True,
        )
        log(f"حُفظت اللقطة محليًا: {result['rows']} صف | "
            f"SHA-256={result['sha256'][:16]}... | السابق={str(result.get('previous_sha256'))[:16]}...")

        check = core.verify_snapshot_state(core.load_state(STATE_FILE), DATA_FILE, COLS)
        if not check["ok"]:
            raise core.SnapshotError("فشل التحقق بعد الحفظ: " + " | ".join(check["issues"]))

        attempt.update({
            "status": "success",
            "finished_at": finished,
            "pages_expected": total_pages,
            "pages_completed": validation["pages_completed"],
            "coverage": validation["coverage"],
            "rows": len(new_df),
            "reported_total": total_results,
            "added": None if diff is None else diff["added_count"],
            "deleted": None if diff is None else diff["deleted_count"],
            "modified": None if diff is None else diff["modified_count"],
            "snapshot_sha256": result["sha256"],
        })
        write_attempt(attempt)

        if do_publish and PUBLISH_ENABLED:
            pub = publish_snapshot(core.load_state(STATE_FILE))
            record_publish(pub)
            if pub.get("status") == "ok":
                log(f"نُشر إلى GitHub: {pub.get('commit')} على {pub.get('branch')}")
            elif pub.get("status") == "no_changes":
                log("لا تغييرات في Git — لم يُنشأ commit")
            else:
                log(f"لم يُنشر: {pub.get('status')} — {pub.get('error')}")
                return EXIT_PUBLISH
        else:
            record_publish({"status": "skipped", "reason": "publish disabled"})
            log("تم تخطي النشر (publish disabled)")

        log("اكتمل السحب بنجاح (100% تغطية + لقطة/حالة متطابقتان)")
        return EXIT_OK

    except LoginRequired as e:
        log(f"FATAL: جلسة الدخول غير صالحة — {e}")
        log("سجّل الدخول يدويًا في نافذة Chrome المخصصة ثم أعد التشغيل.")
        attempt.update({"status": "login_required", "error": str(e),
                        "finished_at": core.iso_riyadh()})
        write_attempt(attempt)
        return EXIT_LOGIN
    except core.SnapshotError as e:
        log(f"FATAL: {e}")
        attempt.update({"status": "failed", "error": str(e)[:500],
                        "finished_at": core.iso_riyadh()})
        write_attempt(attempt)
        return EXIT_INCOMPLETE
    except Exception as e:
        log(f"FATAL: {e!r}")
        attempt.update({"status": "failed", "error": repr(e)[:500],
                        "finished_at": core.iso_riyadh()})
        write_attempt(attempt)
        return EXIT_FATAL
    finally:
        if probe_cdp:
            probe_cdp.close()
        close_target(probe_target)
        lock.release()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="سحب UPS موثّق عبر CDP")
    parser.add_argument("--probe", action="store_true", help="فحص الصفحة الأولى فقط دون حفظ")
    parser.add_argument("--no-publish", action="store_true", help="حفظ محلي فقط")
    args = parser.parse_args(argv)
    return run(probe_only=args.probe, do_publish=not args.no_publish)


if __name__ == "__main__":
    sys.exit(main())
