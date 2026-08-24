import requests
import urllib3
urllib3.disable_warnings()

# Try requests-negotiate-sspi (Windows Integrated Auth)
try:
    from requests_negotiate_sspi import HttpNegotiateAuth
    print("Using negotiate auth")
    s = requests.Session()
    s.auth = HttpNegotiateAuth()
    s.verify = False
except ImportError:
    print("negotiate not available, trying ntlm")
    from requests_ntlm import HttpNtlmAuth
    s = requests.Session()
    s.verify = False

# Hit BLS loginApi
r = s.get('https://app.alriyadh.gov.sa/BLS/loginApi', allow_redirects=False, timeout=30)
print(f'Status: {r.status_code}')
for k,v in r.headers.items():
    print(f'  {k}: {v}')
print(f'Cookies: {dict(s.cookies)}')
body = r.text[:500]
print(f'Body: {body}')

# If redirect, follow it
if r.status_code in (301, 302, 303):
    loc = r.headers.get('Location','')
    print(f'\nFollowing redirect to: {loc}')
    r2 = s.get(loc, allow_redirects=True, timeout=30)
    print(f'Final URL: {r2.url}')
    print(f'Final Status: {r2.status_code}')
    print(f'Final Cookies: {dict(s.cookies)}')
    print(f'Body[:500]: {r2.text[:500]}')
