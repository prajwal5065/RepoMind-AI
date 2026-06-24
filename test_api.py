import urllib.request
import urllib.error

try:
    req = urllib.request.Request("http://127.0.0.1:8000/api/docs/test_e2e_session", method="POST")
    res = urllib.request.urlopen(req, timeout=120)
    print("Status:", res.getcode())
    print("Body length:", len(res.read()))
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code)
    print("Body:", e.read().decode('utf-8'))
except Exception as e:
    print("Exception:", e)
