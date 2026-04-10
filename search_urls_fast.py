"""
並列URL検索スクリプト（高速版）
使い方: python search_urls_fast.py --worker 0  (0〜5のいずれか)
"""

import csv, time, sys, re, argparse, os
import urllib.parse, urllib.request

STAGING_FILE = 'builder_list_staging.csv'

EXCLUDE_DOMAINS = [
    # 求人・ポータル
    'suumo.jp', 'homes.co.jp', 'chintai.net', 'athome.co.jp',
    'mynavi.jp', 'recruit.co.jp', 'indeed.com', 'linkedin.com',
    # SNS・動画
    'facebook.com', 'twitter.com', 'x.com', 'instagram.com', 'youtube.com', 'tiktok.com',
    # 百科・EC
    'wikipedia.org', 'amazon.co.jp', 'rakuten.co.jp',
    # グルメ・レジャー
    'tabelog.com', 'hotpepper.jp',
    # 地図・ナビ
    'google.com', 'google.co.jp', 'navitime.co.jp', 'mapion.co.jp', 'benrimap.com',
    # 住宅ポータル
    'hugkumi-life.jp', 'iezoom.jp', 'b-mall.ne.jp', 'houzz.jp',
    'builder-net.jp', 'auka.jp', 'ie-eco.jp', 'jbn-support.jp',
    # 地域ビジネス系ポータル
    'itp.ne.jp', 'townpage.jp', 'ekiten.jp', 'salesnow.jp',
    'jnet-c.co.jp', 'kj-ie.co.jp', 'suke-dachi.jp',
    # Yahoo系（LYCorp含む）
    'lycorp.co.jp', 'yahoo.co.jp', 'yahoo.com', 'yimg.jp',
    # 行政
    'pref.', '.go.jp',
    # OCN個人ページ
    'ocn.ne.jp',
    # 不動産系ポータル
    'fukuoka-k.jp',
]

# 都道府県を6グループに分割
PREF_GROUPS = [
    ['北海道','青森','岩手','宮城','秋田','山形','福島','茨城'],
    ['栃木','群馬','埼玉','千葉','東京','神奈川','新潟'],
    ['富山','石川','福井','山梨','長野','岐阜','静岡','愛知'],
    ['三重','滋賀','京都','大阪','兵庫','奈良','和歌山','鳥取'],
    ['島根','岡山','広島','山口','徳島','香川','愛媛','高知'],
    ['福岡','佐賀','長崎','熊本','大分','宮崎','鹿児島','沖縄'],
]

import random

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
]

import requests as _requests

_session = None

def _get_session():
    global _session
    if _session is None:
        _session = _requests.Session()
        _session.headers.update({
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'ja-JP,ja;q=0.9,en;q=0.8',
        })
    return _session

def _filter_urls(hrefs):
    seen = set()
    candidates = []
    for u in hrefs:
        u = u.split('?')[0].rstrip('/')
        if u in seen: continue
        seen.add(u)
        if any(excl in u for excl in EXCLUDE_DOMAINS): continue
        candidates.append(u)
    for c in candidates:
        if '.jp' in c:
            return c
    return candidates[0] if candidates else ''

def search_url(company_name, prefecture):
    query = f'{company_name} {prefecture} 工務店'
    encoded = urllib.parse.quote(query)
    url = f'https://search.yahoo.co.jp/search?p={encoded}'

    for attempt in range(3):
        try:
            session = _get_session()
            r = session.get(url, timeout=12)
            hrefs = re.findall(r'href="(https?://[^"]+)"', r.text)
            # Yahooの自サイトURLを除外
            hrefs = [h for h in hrefs if 'yahoo' not in h and 'yimg' not in h and 'google' not in h]
            result = _filter_urls(hrefs)
            return result
        except Exception:
            wait = (attempt + 1) * 3 + random.uniform(1, 2)
            time.sleep(wait)
    return ''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', type=int, required=True, help='ワーカー番号 0〜5')
    parser.add_argument('--delay', type=float, default=1.0)
    args = parser.parse_args()

    prefs = PREF_GROUPS[args.worker]
    out_file = f'staging_worker{args.worker}.csv'

    # ステージングCSV読み込み
    with open(STAGING_FILE, encoding='utf-8-sig') as f:
        all_rows = list(csv.DictReader(f))

    # ワーカー自身の出力ファイルが既に存在すればそこからURLを優先的に引き継ぐ
    result = {r['company_id']: r.get('url','') for r in all_rows}
    if os.path.exists(out_file):
        with open(out_file, encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                cid = r['company_id']
                url = r.get('url','').strip()
                if url and cid in result:
                    result[cid] = url

    # このワーカー担当の都道府県・URL未取得のみ
    targets = [r for r in all_rows if r['prefecture'] in prefs and not result.get(r['company_id'],'').strip()]

    total = len(targets)
    found = 0
    sys.stdout.reconfigure(encoding='utf-8')
    print(f'[Worker{args.worker}] {prefs[0]}〜{prefs[-1]}: {total}社')

    for i, row in enumerate(targets, 1):
        name = row['company_name']
        pref = row['prefecture']
        cid = row['company_id']

        url = search_url(name, pref)
        result[cid] = url
        if url:
            found += 1
            print(f'[W{args.worker}][{i}/{total}] {name[:15]} → {url}')
        else:
            print(f'[W{args.worker}][{i}/{total}] {name[:15]} → 未発見')

        # 30社ごとに中間保存
        if i % 30 == 0:
            save_worker_csv(out_file, all_rows, result, prefs)
            print(f'  [W{args.worker}] 保存: {i}社完了 (取得:{found})')

        time.sleep(args.delay)

    save_worker_csv(out_file, all_rows, result, prefs)
    print(f'[Worker{args.worker}] 完了: {found}/{total}社取得 → {out_file}')

def save_worker_csv(out_file, all_rows, result_map, prefs):
    fieldnames = ['company_id','company_name','prefecture','address','phone','url','status']
    rows_to_save = [r for r in all_rows if r['prefecture'] in prefs]
    for r in rows_to_save:
        r['url'] = result_map.get(r['company_id'], r.get('url',''))
    with open(out_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows_to_save)

if __name__ == '__main__':
    main()
