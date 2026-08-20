import pandas as pd
import time, os, json, glob, shutil
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)

def save(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with open("scraper_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)

save("=" * 60)
save("بدء عملية سحب البيانات")

PORTAL_URL = "https://app.alriyadh.gov.sa/SSO/faces/home"

try:
    service = Service(ChromeDriverManager().install())
    opts = webdriver.ChromeOptions()
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("prefs", {
        "download.default_directory": PROJECT_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
    })
    driver = webdriver.Chrome(service=service, options=opts)
except Exception as e:
    save(f"FATAL: Can't start Chrome: {e}")
    os._exit(1)

save("فتح البوابة...")
driver.get(PORTAL_URL)
save("تم فتح Chrome. سجّل دخولك وتنقل لصفحة الطلبات ثم اضغط Enter هنا")
input(">>> اضغط Enter بعد ما توصل لصفحة البحث والتصدير... ")
time.sleep(3)

save(f"الرابط: {driver.current_url[:200]}")
save(f"العنوان: {driver.title[:200]}")

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
    save("لم يتم إيجاد زر التصدير. حاول البحث بناءً على نوع العنصر...")
    for e in elements_info:
        if not (e["visible"] and e["enabled"]):
            continue
        if e["tag"] in ("button", "a"):
            text_lower = e["text"].lower()
            if any(k in text_lower for k in ["search", "بحث", "تصدير", "export", "search"]):
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
            break
        time.sleep(5)
else:
    save("لم يتم التصدير. يمكنك تصدير الملف يدوياً من المتصفح")

driver.quit()
save("=== انتهت العملية ===")
