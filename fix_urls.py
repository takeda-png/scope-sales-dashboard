"""
URL修正スクリプト
1. HP error/timeout → URLをクリアして再検索対象に
2. redirect → HTTP→HTTPSは最終URLに更新。ポータルサイトはクリア
3. URL未取得 → 検索クエリを変えて再検索（「工務店」なし）
"""
import csv, os, glob, re, time, random, sys, threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests, urllib3
urllib3.disable_warnings()

# CP932で扱えない特殊文字のエンコードエラーを回避
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = os.path.dirname(os.path.abspath(__file__))
RESULT_FILE = os.path.join(BASE, 'url_check_results.csv')

# ポータル・不正ドメイン（リダイレクト先がここならクリア）
PORTAL_DOMAINS = [
    'suumo.jp', 'homes.co.jp', 'athome.co.jp', 'chintai.net',
    'hugkumi-life.jp', 'b-mall.ne.jp', 'iezoom.jp', 'houzz.jp',
    'builder-net.jp', 'auka.jp', 'ie-eco.jp', 'jbn-support.jp',
    'suke-dachi.jp', 'jnet-c.co.jp', 'kj-ie.co.jp',
    'liner.jp', 'fudousan.or.jp', 'rebuild.hapisumu.jp',
    'ekiten.jp', 'itp.ne.jp', 'townpage.jp', 'salesnow.jp',
    'navitime.co.jp', 'lycorp.co.jp', 'fukuoka-k.jp',
    'hapisumu.jp', 'sumaivalue.jp', 'sumai-surfin.com',
]

def is_portal(url):
    return any(d in url for d in PORTAL_DOMAINS)

def extract_domain(url):
    m = re.search(r'https?://(?:www\.)?([^/]+)', url or '')
    return m.group(1) if m else ''

# ---- Phase 1: チェック結果を処理 ----
print('=== Phase 1: HP チェック結果の修正 ===')

if not os.path.exists(RESULT_FILE):
    print('url_check_results.csv が見つかりません')
    exit()

with open(RESULT_FILE, encoding='utf-8-sig') as f:
    check_rows = list(csv.DictReader(f))

# company_id → check結果マップ
check_map = {r['company_id']: r for r in check_rows}

# 各workerCSVを修正
FIELDNAMES_W = ['company_id','company_name','prefecture','address','phone','url','status']

fixed_error = 0
fixed_redirect = 0
fixed_portal = 0

for wfile in sorted(glob.glob(os.path.join(BASE, 'staging_worker*.csv'))):
    with open(wfile, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))

    modified = False
    for r in rows:
        cid = r.get('company_id','')
        chk = check_map.get(cid, {})
        status = chk.get('status','')
        final_url = chk.get('final_url','').strip()
        url = r.get('url','').strip()

        if not url:
            continue

        if status in ('error', 'timeout'):
            # エラー → URLクリアして再検索対象に
            r['url'] = ''
            fixed_error += 1
            modified = True

        elif status == 'redirect' and final_url:
            orig_domain = extract_domain(url)
            final_domain = extract_domain(final_url)

            if is_portal(final_url):
                # ポータルへのリダイレクト → クリア
                r['url'] = ''
                fixed_portal += 1
                modified = True
            elif orig_domain != final_domain and not is_portal(final_url):
                # ドメイン変更リダイレクト → 最終URLに更新
                r['url'] = final_url
                fixed_redirect += 1
                modified = True
            else:
                # HTTP→HTTPS等の同ドメインリダイレクト → 最終URLに更新
                r['url'] = final_url
                fixed_redirect += 1
                modified = True

    if modified:
        with open(wfile, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES_W, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
        print(f'  {os.path.basename(wfile)}: 修正済み')

print(f'\nPhase 1 完了:')
print(f'  error/timeout クリア: {fixed_error}件')
print(f'  redirect → URL更新:  {fixed_redirect}件')
print(f'  ポータルリダイレクト クリア: {fixed_portal}件')

# ---- Phase 2: URL未取得の再検索（クエリ変更版） ----
print('\n=== Phase 2: URL未取得の再検索 ===')

EXCLUDE_DOMAINS = [
    'suumo.jp','homes.co.jp','chintai.net','athome.co.jp','mynavi.jp',
    'recruit.co.jp','indeed.com','linkedin.com','facebook.com','twitter.com',
    'x.com','instagram.com','youtube.com','tiktok.com','wikipedia.org',
    'amazon.co.jp','rakuten.co.jp','tabelog.com','hotpepper.jp',
    'google.com','google.co.jp','navitime.co.jp','mapion.co.jp','benrimap.com',
    'hugkumi-life.jp','iezoom.jp','b-mall.ne.jp','houzz.jp','builder-net.jp',
    'auka.jp','ie-eco.jp','jbn-support.jp','suke-dachi.jp','jnet-c.co.jp',
    'kj-ie.co.jp','itp.ne.jp','townpage.jp','ekiten.jp','salesnow.jp',
    'lycorp.co.jp','yahoo.co.jp','yahoo.com','yimg.jp','ocn.ne.jp',
    'fukuoka-k.jp','liner.jp','fudousan.or.jp','hapisumu.jp','pref.','.go.jp',
]

import urllib.parse

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
]

_tlocal = threading.local()

def get_session():
    if not hasattr(_tlocal, 'session'):
        s = requests.Session()
        s.headers.update({'User-Agent': random.choice(USER_AGENTS), 'Accept': 'text/html'})
        _tlocal.session = s
    return _tlocal.session

def filter_url(hrefs):
    seen = set()
    candidates = []
    for u in hrefs:
        u = u.split('?')[0].rstrip('/')
        if u in seen: continue
        seen.add(u)
        if any(ex in u for ex in EXCLUDE_DOMAINS): continue
        candidates.append(u)
    for c in candidates:
        if '.jp' in c or '.com' in c:
            return c
    return candidates[0] if candidates else ''

def search_url_v2(name, pref):
    """工務店を外した広いクエリで再検索"""
    for query_tmpl in [
        f'{name} {pref} 公式サイト',
        f'{name} {pref}',
        f'{name} 工務店',
    ]:
        encoded = urllib.parse.quote(query_tmpl)
        url = f'https://search.yahoo.co.jp/search?p={encoded}'
        for attempt in range(2):
            try:
                r = get_session().get(url, timeout=12)
                hrefs = re.findall(r'href="(https?://[^"]+)"', r.text)
                hrefs = [h for h in hrefs if 'yahoo' not in h and 'yimg' not in h and 'lycorp' not in h]
                result = filter_url(hrefs)
                if result:
                    return result
            except Exception:
                time.sleep(1.5)
        time.sleep(1)
    return ''

# 未取得リストを収集
no_url_targets = {}
for wfile in sorted(glob.glob(os.path.join(BASE, 'staging_worker*.csv'))):
    with open(wfile, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            cid = r.get('company_id','')
            url = r.get('url','').strip()
            if cid and not url:
                no_url_targets[cid] = {'file': wfile, 'row': r}

THREADS = 5
print(f'URL未取得: {len(no_url_targets)}件 → 再検索開始（{THREADS}並列）')

# ファイル別にグループ化
from collections import defaultdict
file_groups = defaultdict(list)
for cid, info in no_url_targets.items():
    file_groups[info['file']].append((cid, info['row']))

found_count = 0
write_lock = threading.Lock()

# 全ターゲットをフラットリストに
all_targets = []
for wfile, items in sorted(file_groups.items()):
    for cid, row in items:
        all_targets.append((wfile, cid, row))

# ファイル別にurl_mapをロード
file_url_maps = {}
for wfile in sorted(file_groups.keys()):
    with open(wfile, encoding='utf-8-sig') as f:
        all_rows = list(csv.DictReader(f))
    file_url_maps[wfile] = {r['company_id']: r for r in all_rows}

def process_one(task):
    wfile, cid, row = task
    name = row.get('company_name', '')
    pref = row.get('prefecture', '')
    result = search_url_v2(name, pref)
    time.sleep(0.5)
    return wfile, cid, name, result

done_count = 0
with ThreadPoolExecutor(max_workers=THREADS) as executor:
    futures = {executor.submit(process_one, t): t for t in all_targets}
    for future in as_completed(futures):
        try:
            wfile, cid, name, result = future.result()
            done_count += 1
            with write_lock:
                if result:
                    file_url_maps[wfile][cid]['url'] = result
                    found_count += 1
                    print(f'  [{found_count}] {name[:18]} -> {result[:50]}', flush=True)
                else:
                    print(f'  [ - ] {name[:18]} 未発見', flush=True)

                # 50件ごとに保存
                if done_count % 50 == 0:
                    for wf, url_map in file_url_maps.items():
                        with open(wf, 'w', encoding='utf-8-sig', newline='') as f:
                            writer = csv.DictWriter(f, fieldnames=FIELDNAMES_W, extrasaction='ignore')
                            writer.writeheader()
                            writer.writerows(url_map.values())
                    print(f'  [保存] {done_count}/{len(all_targets)}件処理済み', flush=True)
        except Exception as e:
            print(f'  [ERR] {e}', flush=True)

# 最終保存
for wfile, url_map in file_url_maps.items():
    with open(wfile, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES_W, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(url_map.values())

print(f'\nPhase 2 完了: {found_count}/{len(no_url_targets)}件 URL取得')
print('\n全修正完了。merge_workers.py → import_builders.py を実行してください。')
