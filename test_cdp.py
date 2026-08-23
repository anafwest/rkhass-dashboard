import ssl, os, urllib3
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import re, time

opts = Options()
opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
driver = webdriver.Chrome(options=opts)

# Check all tabs/windows
print("=== All windows ===")
for handle in driver.window_handles:
    driver.switch_to.window(handle)
    print(f"  {driver.current_url[:120]} - {driver.title[:60]}")

# Switch back to first
driver.switch_to.window(driver.window_handles[0])

# Try clicking the button differently
print("\nClicking via link element...")
try:
    link = driver.find_element(By.CSS_SELECTOR, "a[onclick*='btn_FORM_APP']")
    print(f"  Found link: {link.text[:50]}")
    link.click()
    time.sleep(10)
    
    # Check again
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        print(f"  Window: {driver.current_url[:120]} - {driver.title[:60]}")
    
    driver.switch_to.window(driver.window_handles[0])
    print(f"  Current: {driver.current_url[:120]}")
except Exception as e:
    print(f"  Error: {e}")

# Save page
driver.save_screenshot("after_click.png")
with open("after_click.html", "w", encoding="utf-8") as f:
    f.write(driver.page_source[:5000])
