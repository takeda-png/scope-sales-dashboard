"""2秒以上の間隔を保証するキャッシュ付き取得 + robots.txt 判定"""
import hashlib, os, time, sys
import urllib.robotparser
from urllib.parse import urlparse
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept-Language": "ja,en;q=0.9"}
BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "raw")
os.makedirs(CACHE, exist_ok=True)
MIN_INTERVAL = 2.2  # 秒（同一ホスト）
_last = {}
_robots = {}


def allowed(url):
    p = urlparse(url)
    host = p.netloc
    if host not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(f"{p.scheme}://{host}/robots.txt", headers=HEADERS, timeout=10)
            _wait_mark(host)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp.parse([])
        _robots[host] = rp
    return _robots[host].can_fetch("*", url)


def _wait_mark(host):
    _last[host] = time.time()


def _wait(host):
    t = _last.get(host, 0)
    d = time.time() - t
    if d < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - d)


def get(url, timeout=25, use_cache=True, check_robots=True):
    """戻り値: (status, final_url, text)。robots不可は (-1, url, '')"""
    key = hashlib.md5(url.encode()).hexdigest()
    path = os.path.join(CACHE, key + ".html")
    meta = path + ".meta"
    if use_cache and os.path.exists(path):
        st, fu = open(meta, encoding="utf-8").read().split("\t", 1)
        return int(st), fu, open(path, encoding="utf-8", errors="replace").read()
    if check_robots and not allowed(url):
        return -1, url, ""
    host = urlparse(url).netloc
    _wait(host)
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        _wait_mark(host)
        r.encoding = r.apparent_encoding if (r.encoding or "").lower() in ("iso-8859-1", "") else r.encoding
        st, fu, tx = r.status_code, r.url, r.text
    except Exception as e:
        _wait_mark(host)
        st, fu, tx = 0, url, ""
    with open(path, "w", encoding="utf-8") as f:
        f.write(tx)
    with open(meta, "w", encoding="utf-8") as f:
        f.write(f"{st}\t{fu}")
    return st, fu, tx
