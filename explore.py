import ssl, os, urllib3, time
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)

opts = Options()
opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
opts.page_load_strategy = "eager"
driver = webdriver.Chrome(options=opts)
print(f"Connected: {driver.current_url}")

driver.execute_cdp_cmd("Page.navigate", {"url": "https://app.alriyadh.gov.sa/SSO/faces/report/permitsDahBoard"})
print("Navigation started")
time.sleep(20)

print(f"URL: {driver.current_url}")
print(f"Title: {driver.title}")

driver.save_screenshot("page_screenshot.png")
print("Screenshot saved")

src = driver.page_source
with open("page_source.html", "w", encoding="utf-8") as f:
    f.write(src)
print(f"HTML saved: {len(src)} chars")

from selenium.webdriver.common.by import By
body = driver.find_element(By.TAG_NAME, "body")
print(f"Body text ({len(body.text)} chars):")
print(body.text[:2000])
