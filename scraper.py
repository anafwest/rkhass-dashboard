import ssl, os, urllib3
urllib3.disable_warnings()
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["PYTHONHTTPSVERIFY"] = "0"
ssl._create_default_https_context = ssl._create_unverified_context

import pandas as pd
import time, json, glob, shutil, subprocess, smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CHROME_PROFILE_DIR = os.path.join(PROJECT_DIR, "chrome_profile")
os.chdir(PROJECT_DIR)

ALERT_EMAIL = "anaf@alriyadh.gov.sa"

def save(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with open("scraper_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)

def send_alert(subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"] = ALERT_EMAIL
        msg["To"] = ALERT_EMAIL
        msg["Subject"] = f"[مؤشر أداء رخص البناء] {subject}"
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP("localhost", 25) as server:
            server.sendmail(ALERT_EMAIL, ALERT_EMAIL, msg.as_string())
        save(f"تم إرسال تنبيه إلى {ALERT_EMAIL}")
    except Exception as e:
        save(f"تعذر إرسال الإيميل: {e}")

save("=" * 60)
save("بدء عملية سحب البيانات - تشغيل تلقائي")

PORTAL_URL = "https://app.alriyadh.gov.sa/SSO/faces/home"
MAX_WAIT = 120
success = False

try:
    opts = Options()
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--ignore-certificate-errors")
    opts.add_argument("--ignore-ssl-errors")
    main_chrome = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data")
    if os.path.exists(main_chrome):
        opts.add_argument(f"--user-data-dir={main_chrome}")
        opts.add_argument("--profile-directory=Default")
        save("استخدام ملف Chrome الرئيسي للحفاظ على الجلسة")
    else:
        opts.add_argument(f"--user-data-dir={CHROME_PROFILE_DIR}")
        opts.add_argument("--profile-directory=Default")
        save("استخدام ملف Chrome الخاص بالمشروع")
    opts.add_experimental_option("prefs", {
        "download.default_directory": PROJECT_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
    })
    driver = webdriver.Chrome(options=opts)
except Exception as e:
    save(f"FATAL: {e}")
    send_alert("فشل تشغيل Chrome", f"لم يتم تشغيل المتصفح:\n{e}")
    os._exit(1)

try:
    save("فتح البوابة...")
    driver.get(PORTAL_URL)
    time.sleep(5)

    save(f"الرابط الحالي: {driver.current_url[:200]}")
    save(f"العنوان: {driver.title[:200]}")

    current = driver.current_url.lower()
    on_login = "sso" in current or "login" in current or "auth" in current

    if on_login:
        save("على صفحة تسجيل الدخول. انتظار تسجيل الدخول التلقائي (جلسة محفوظة)...")
        for i in range(MAX_WAIT // 2):
            time.sleep(2)
            current = driver.current_url.lower()
            if "sso" not in current and "login" not in current and "auth" not in current:
                save(f"تم تسجيل الدخول تلقائياً: {driver.current_url[:150]}")
                break
        else:
            save("انتهت مهلة انتظار تسجيل الدخول.")
            send_alert("فشل تسجيل الدخول", "انتهت مهلة 120 ثانية ولم يتم تسجيل الدخول تلقائياً.\nيجب تجديد جلسة Chrome بتسجيل الدخول يدوياً.")
            driver.save_screenshot("login_timeout.png")
            driver.quit()
            os._exit(1)

    time.sleep(3)
    save(f"الرابط النهائي: {driver.current_url[:200]}")
    save(f"العنوان النهائي: {driver.title[:200]}")

    driver.save_screenshot("page_screenshot.png")
    save("تم حفظ Screenshot")

    with open("page_source.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    save("تم حفظ HTML")

    elements_info = []
    keywords = ["بحث", "تاريخ", "تصدير", "اكسل", "date", "export", "excel", "all", "تحميل", "download"]

    for tag in ["input", "select", "button", "a", "span"]:
        try:
            elems = driver.find_elements(By.TAG_NAME, tag)
        except Exception:
            continue
        for elem in elems:
            try:
                html = (elem.get_attribute("outerHTML") or "")[:500]
                text = (elem.text.strip() or elem.get_attribute("value") or "")[:100]
                if text or any(k in html.lower() for k in keywords):
                    elements_info.append({
                        "tag": tag,
                        "id": elem.get_attribute("id") or "",
                        "name": elem.get_attribute("name") or "",
                        "text": text,
                        "type": elem.get_attribute("type") or "",
                        "class": (elem.get_attribute("class") or "")[:100],
                        "visible": elem.is_displayed(),
                        "enabled": elem.is_enabled(),
                    })
            except Exception:
                pass

    with open("elements.json", "w", encoding="utf-8") as f:
        json.dump(elements_info, f, ensure_ascii=False, indent=2)

    save(f"تم العثور على {len(elements_info)} عنصر")
    for e in elements_info:
        vis = "O" if e["visible"] else "-"
        save(f"  {vis} <{e['tag']}> id={e['id'][:30]} text={e['text'][:50]}")

    save("=== محاولة التصدير التلقائي ===")
    export_keywords = ["تصدير", "export", "اكسل", "excel", "تحميل", "download", "csv", "xls", "html"]

    found_export = False
    for e in elements_info:
        if not (e["visible"] and e["enabled"]):
            continue
        comb = (e["text"] + " " + e["id"] + " " + e["name"] + " " + e["class"]).lower()
        for k in export_keywords:
            if k in comb:
                try:
                    if e["id"]:
                        elem = driver.find_element(By.ID, e["id"])
                    elif e["name"]:
                        elem = driver.find_element(By.NAME, e["name"])
                    elif e["text"]:
                        xpath = f"//*[contains(text(), '{e['text'][:25]}')]"
                        elem = driver.find_element(By.XPATH, xpath)
                    else:
                        continue
                    if elem.is_displayed() and elem.is_enabled():
                        elem.click()
                        save(f"تم الضغط على: <{e['tag']}> text={e['text'][:30]}")
                        time.sleep(8)
                        found_export = True
                        break
                except Exception:
                    pass
        if found_export:
            break

    if not found_export:
        save("لم يتم إيجاد زر التصدير مباشرة. محاولة بحث ثانية...")
        for e in elements_info:
            if not (e["visible"] and e["enabled"]):
                continue
            if e["tag"] in ("button", "a"):
                text_lower = e["text"].lower()
                if any(k in text_lower for k in ["search", "بحث", "تصدير", "export"]):
                    try:
                        xpath = f"//*[contains(text(), '{e['text'][:25]}')]"
                        btn = driver.find_element(By.XPATH, xpath)
                        if btn.is_displayed() and btn.is_enabled():
                            btn.click()
                            save(f"تم الضغط على: {e['text'][:30]}")
                            time.sleep(5)
                            found_export = True
                            break
                    except Exception:
                        pass

    if found_export:
        save("في انتظار تحميل الملف...")
        for i in range(60):
            all_xls = glob.glob(os.path.join(PROJECT_DIR, "*.xls")) + glob.glob(os.path.join(PROJECT_DIR, "*.xlsx"))
            all_cr = glob.glob(os.path.join(PROJECT_DIR, "*.crdownload"))
            if all_xls and not all_cr:
                latest = max(all_xls, key=os.path.getctime)
                save(f"تم تحميل: {latest}")
                backup_dir = os.path.join(PROJECT_DIR, "backups")
                os.makedirs(backup_dir, exist_ok=True)
                shutil.copy2(latest, os.path.join(backup_dir, f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.path.basename(latest)}"))
                if latest.endswith(".xlsx"):
                    shutil.copy2(latest, os.path.join(PROJECT_DIR, "data.xlsx"))
                    save("تم حفظ data.xlsx")
                else:
                    shutil.copy2(latest, os.path.join(PROJECT_DIR, "data.xls"))
                    save("تم حفظ data.xls")

                save("=== رفع البيانات تلقائياً إلى GitHub ===")
                try:
                    os.chdir(PROJECT_DIR)
                    subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
                    commit_msg = f"تحديث البيانات التلقائي - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    result = subprocess.run(["git", "commit", "-m", commit_msg], capture_output=True, text=True)
                    if result.returncode == 0:
                        save("تم حفظ التغييرات في Git")
                        push_result = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True, timeout=60)
                        if push_result.returncode == 0:
                            save("تم رفع البيانات إلى GitHub بنجاح - Streamlit Cloud سيتحدث تلقائياً")
                            success = True
                        else:
                            save(f"خطأ في الرفع: {push_result.stderr[:200]}")
                            send_alert("فشل رفع البيانات", f"تم سحب البيانات لكن فشل الرفع إلى GitHub:\n{push_result.stderr[:300]}")
                    else:
                        save("لا توجد تغييرات جديدة للرفع")
                        success = True
                except Exception as e:
                    save(f"خطأ في عملية Git: {e}")
                    send_alert("خطأ Git", f"خطأ أثناء عملية الرفع:\n{e}")

                break
            time.sleep(5)
    else:
        save("لم يتم التصدير تلقائياً.")
        send_alert("فشل التصدير", "لم يتم العثور على زر التصدير في البوابة.\nقد تكون واجهة البوابة تغيرت.")

    if success:
        save("تمت العملية بنجاح")

finally:
    try:
        driver.quit()
    except Exception:
        pass
    save("=== انتهت العملية ===")
