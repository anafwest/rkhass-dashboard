import pandas as pd
import time, os, shutil, glob
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
from hijri_converter import Hijri, Gregorian

folder = __file__ if "__file__" in dir() else "."
os.chdir(os.path.dirname(os.path.abspath(folder)))

def log(msg):
    with open("scraper_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().strftime('%H:%M:%S')} {msg}\n")
    print(msg)

def snap(name):
    driver.save_screenshot(f"snap_{name}.png")
    with open(f"snap_{name}.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)

def wait_any(timeout, interval, condition_fn):
    for _ in range(int(timeout / interval)):
        time.sleep(interval)
        try:
            if condition_fn(): return True
        except: continue
    return False

profile_dir = os.path.join(os.getcwd(), "chrome_profile")
opts = webdriver.ChromeOptions()
opts.add_argument(f"--user-data-dir={profile_dir}")
opts.add_argument("--profile-directory=Default")
opts.add_argument("--no-first-run")
opts.add_argument("--disable-popup-blocking")
opts.add_experimental_option("prefs", {
    "download.default_directory": os.getcwd(),
    "download.prompt_for_download": False,
})

try:
    driver = webdriver.Chrome(options=opts)
except:
    log("خطأ: سكر Chrome كامل اولا")
    input("اضغط Enter للخروج...")
    exit()

wait = WebDriverWait(driver, 30)
driver.get("https://app.alriyadh.gov.sa/SSO/faces/home")
time.sleep(3)

log("سجل دخولك في Chrome اللي فتح (يوزر + باسورد + كابتشا + كود)")
log("بانتظر لمدة 15 دقيقة لحين تخلص")

# انتظر حتى ينتقل من صفحة تسجيل الدخول (يتغير الـ URL)
login_url = "SSO/faces/login"
def not_on_login():
    return login_url not in driver.current_url

if not wait_any(900, 5, not_on_login):
    log("لم يتم تسجيل الدخول - انتهاء الوقت"); input("اضغط Enter للخروج..."); exit()
log("تم تسجيل الدخول")

# إذا ظهرت صفحة OTP (التحقق برمز)
if "التحقق" in driver.find_element(By.TAG_NAME, "body").text:
    log("🔐 صفحة OTP - أدخل رمز التحقق المرسل لجوالك")
    # انتظر حتى يختفي حقل OTP أو يتغير الرابط
    if not wait_any(180, 3, lambda: "التحقق" not in driver.find_element(By.TAG_NAME, "body").text):
        log("OTP لم يتم إدخاله - نكمل")
    else:
        log("تم إدخال OTP")

time.sleep(2)

log("1/6 بوابة الانظمة الاساسية")
try:
    for btn in driver.find_elements(By.XPATH, "//*[contains(text(),'بوابة الأنظمة الأساسية')]"):
        if btn.is_displayed():
            driver.execute_script("arguments[0].click();", btn); break
except: pass
time.sleep(5)
if len(driver.window_handles) > 1:
    driver.switch_to.window(driver.window_handles[-1])
time.sleep(2)

log("2/6 نظام رخص البناء")
for text in ["نظام رخص البناء", "رخص البناء"]:
    for btn in driver.find_elements(By.XPATH, f"//*[contains(text(),'{text}')]"):
        if btn.is_displayed():
            driver.execute_script("arguments[0].click();", btn); break
    else: continue; break
time.sleep(3)

log("3/6 متابعة الطلبات")
for text in ["متابعة الطلبات", "استعلامات ومتابعة"]:
    for btn in driver.find_elements(By.XPATH, f"//*[contains(text(),'{text}')]"):
        if btn.is_displayed():
            driver.execute_script("arguments[0].click();", btn); break
    else: continue; break
time.sleep(6)
# إغلاق أي نافذة منبثقة إن وجدت
try:
    for btn in driver.find_elements(By.XPATH, "//*[contains(text(),'إغلاق') or contains(text(),'تخطي')]"):
        if btn.is_displayed(): driver.execute_script("arguments[0].click();", btn); time.sleep(2); break
except: pass

log("4/6 استعلام عن بيانات الطلبات (BLS8510)")

def find_bls8510():
    # استراتيجية 1: فتح كل العناصر المخفية
    try:
        driver.execute_script("""
            document.querySelectorAll('#searchMenuScreensUL li, li, a, span').forEach(function(el) {
                el.style.display = '';
            });
        """)
    except: pass
    # استراتيجية 2: ID (بدون is_displayed)
    try:
        link = driver.find_element(By.ID, "pt1:SearchLi8510")
        driver.execute_script("arguments[0].click();", link)
        return True
    except: pass
    # استراتيجية 3: callButtonFcuntion
    try:
        driver.execute_script("callButtonFcuntion('8510')")
        return True
    except: pass
    # استراتيجية 4: نص BLS8510
    try:
        for el in driver.find_elements(By.XPATH, "//*[contains(text(),'BLS8510') or contains(text(),'استعلام عن بيانات الطلبات')]"):
            driver.execute_script("arguments[0].click();", el)
            return True
    except: pass
    # استراتيجية 5: أي عنصر فيه 8510 في id
    try:
        for el in driver.find_elements(By.XPATH, "//*[contains(@id,'8510')]"):
            driver.execute_script("arguments[0].click();", el)
            return True
    except: pass
    return False

if not find_bls8510():
    log("فشل الوصول للرابط"); snap("05_failed"); input("اضغط Enter للخروج..."); exit()
log("تم الضغط على BLS8510")
time.sleep(5)

snap("05_inquiry_page")

log("5/6 تعبئة وتصدير")
g_start = Gregorian(2025, 10, 5).to_hijri()
g_today = Gregorian.today().to_hijri()
start_date = f"{g_start.year}/{g_start.month:02d}/{g_start.day:02d}"
today_date = f"{g_today.year}/{g_today.month:02d}/{g_today.day:02d}"
log(f"التاريخ الهجري: {start_date} - {today_date}")

def fill_adf_date(field_id, date_str):
    script = """
    var el = document.getElementById(arguments[0]);
    if (el) {
        el.value = arguments[1];
        el.dispatchEvent(new Event('input', {bubbles:true}));
        el.dispatchEvent(new Event('change', {bubbles:true}));
        el.dispatchEvent(new Event('blur', {bubbles:true}));
        return true;
    }
    return false;
    """
    return driver.execute_script(script, field_id, date_str)

from_field = "pt1:cBodFDC:r1:0:masteraTable:Fromdate::content"
to_field = "pt1:cBodFDC:r1:0:masteraTable:Todate::content"

ok1 = fill_adf_date(from_field, start_date)
ok2 = fill_adf_date(to_field, today_date)
log(f"تعبئة من تاريخ: {'تم' if ok1 else 'فشل'}")
log(f"تعبئة إلى تاريخ: {'تم' if ok2 else 'فشل'}")
time.sleep(2)

if not ok1 or not ok2:
    for inp in driver.find_elements(By.XPATH, "//input[@type='text']"):
        pid = inp.get_attribute("id") or ""
        if inp.is_displayed() and ("Fromdate" in pid or "Todate" in pid):
            inp.clear(); inp.send_keys(start_date if "Fromdate" in pid else today_date)
            log(f"تم بالـ send_keys: {pid}")

for label, fid in [("حالة الطلب", "smc1"), ("الخدمة", "smc2")]:
    try:
        drop = driver.find_element(By.ID, f"pt1:cBodFDC:r1:0:masteraTable:{fid}::drop")
        driver.execute_script("arguments[0].click();", drop)
        time.sleep(1)
        sa = driver.find_element(By.ID, f"pt1:cBodFDC:r1:0:masteraTable:{fid}::saId")
        if not sa.is_selected():
            driver.execute_script("arguments[0].click();", sa)
        log(f"تم اختيار الكل في {label}")
        # إغلاق القائمة بالضغط خارجها
        driver.execute_script("arguments[0].click();", drop)
        time.sleep(0.5)
    except Exception as e:
        log(f"فشل اختيار الكل في {label}: {e}")

time.sleep(2)

# بحث - مرة واحدة فقط مع انتظار أطول
log("البحث")
for btn in driver.find_elements(By.XPATH, "//*[contains(text(),'بحث')]"):
    if btn.is_displayed():
        driver.execute_script("arguments[0].click();", btn)
        break
# انتظر لحين يختفي شريط التحميل أو تظهر النتائج
wait_any(60, 3, lambda: "لا توجد بيانات" in driver.find_element(By.TAG_NAME, "body").text or "جار" not in driver.find_element(By.TAG_NAME, "body").text)
snap("06_after_search")
log("تم البحث")

time.sleep(3)

# تصدير
for attempt in range(5):
    for btn in driver.find_elements(By.XPATH, "//*[contains(text(),'تصدير') or contains(text(),'اكسل') or contains(text(),'Excel')]"):
        if btn.is_displayed():
            driver.execute_script("arguments[0].click();", btn)
            log(f"تصدير (محاولة {attempt+1})")
            time.sleep(5)
            break
    # انتظر الملف ينزل
    for _ in range(30):
        xls_files = [f for f in glob.glob("*.xls*") if f not in ("data.xls", "data.xlsx", "الطلبات.xls")]
        if xls_files: break
        time.sleep(2)
    else:
        continue
    break

time.sleep(5)

# نقل الملف + نسخ احتياطي
xls_files = [f for f in glob.glob("*.xls*") if f not in ("data.xls", "data.xlsx", "الطلبات.xls")]
if xls_files:
    newest = max(xls_files, key=os.path.getctime)
    shutil.copy2(newest, "الطلبات.xls")
    log(f"الطلبات.xls {os.path.getsize('الطلبات.xls')} bytes ({newest})")
    # نسخ احتياطي
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"data_{ts}.xls")
    shutil.copy2(newest, backup_path)
    log(f"نسخة احتياطية: {backup_path}")
    # تنظيف النسخ القديمة (آخر 30)
    all_bk = sorted(glob.glob(os.path.join(backup_dir, "data_*.xls")))
    for old in all_bk[:-30]:
        try: os.remove(old)
        except: pass
else:
    log("ما لقيت ملف مLoaded")

input("\n🔹 السكرابر انتهى. اضغط Enter لإغلاق المتصفح والخروج...")
driver.quit()
log("تم")
