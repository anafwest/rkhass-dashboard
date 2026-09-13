# -*- coding: utf-8 -*-
import sys, json, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding='utf-8')
url = "https://ups-backoffice.alriyadh.gov.sa/ar/building-license-department?activeTab=requests"
req = urllib.request.Request("http://127.0.0.1:9222/json/new?" + urllib.parse.quote(url, safe=""), method="PUT")
nb = json.loads(urllib.request.urlopen(req, timeout=10).read())
print("tab id:", nb.get("id"))
