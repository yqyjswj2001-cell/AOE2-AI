"""Small standard-library client for the local author service only."""
import json
import urllib.request
from urllib.parse import urlparse

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("本地作者接口不接受重定向。")

def request(base, route, data=None, *, headers=None):
    parsed = urlparse(base)
    if not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}
            and not parsed.username and not parsed.password and parsed.path in {"", "/"}
            and not parsed.query and not parsed.fragment):
        raise ValueError("只连接本机作者服务。")
    if not isinstance(route, str) or not route.startswith("/api/") or "://" in route:
        raise ValueError("接口路径无效。")
    payload = None if data is None else json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
    req = urllib.request.Request(base.rstrip("/") + route, data=payload,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(req, timeout=150) as response:
        return json.load(response)
