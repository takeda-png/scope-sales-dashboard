"""
電話番号・住所ベースのURL検索スクリプト
通常の社名検索で見つからなかった363社を対象に
複数の検索戦略で再チャレンジする
"""
import csv, time, sys, re, os, random
import urllib.parse
import requests

sys.stdout.reconfigure(encoding='utf-8')

STAGING_FILE = 'builder_list_staging.csv'
OUT_FILE = 'staging_phone_search.csv'
DELAY = 2.0

EXCLUDE_DOMAINS = [
    'suumo.jp', 'homes.co.jp', 'chintai.net', 'athome.co.jp',
    'mynavi.jp', 'recruit.co.jp', 'indeed.com', 'linkedin.com',
    'facebook.com', 'twitter.com', 'x.com', 'instagram.com',
    'youtube.com', 'tiktok.com', 'wikipedia.org', 'amazon.co.jp',
    'rakuten.co.jp', 'tabelog.com', 'hotpepper.jp',
    'google.com', 'google.co.jp', 'navitime.co.jp', 'mapion.co.jp',
    'hugkumi-life.jp', 'iezoom.jp', 'b-mall.ne.jp', 'houzz.jp',
    'builder-net.jp', 'auka.jp', 'ie-eco.jp', 'jbn-support.jp',
    'itp.ne.jp', 'townpage.jp', 'ekiten.jp', 'salesnow.jp',
    'jnet-c.co.jp', 'kj-ie.co.jp', 'suke-dachi.jp',
    'lycorp.co.jp', 'yahoo.co.jp', 'yahoo.com', 'yimg.jp',
    'ocn.ne.jp', 'fukuoka-k.jp', 'benrimap.com',
    # 電話番号検索サイト（HP自体ではない）
    'jpnumber.com', 'telno.net', 'phone-number.jp', 'coco.to',
    '番号.jp', '0120.jp', 'numbersearch.jp', 'fonewho.com',
    'whocalledme.jp', 'callname.jp', 'denwa-bango.net',
    # ポータル・ディレクトリ
    'stephouse.jp', 'rebuild.hapisumu.jp', 'digitalpr.jp',
    'select-home.net', 'school.stephouse.jp',
]

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
]

session = requests.Session()
session.headers.update({
    'User-Agent': random.choice(USER_AGENTS),
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'ja-JP,ja;q=0.9,en;q=0.8',
})

def is_bad_url(url):
    return any(d in url for d in EXCLUDE_DOMAINS)

def extract_best_url(hrefs):
    """抽出したURLリストから最適なものを返す"""
    seen = set()
    candidates = []
    for u in hrefs:
        u = u.split('?')[0].rstrip('/')
        if u in seen or len(u) < 10:
            continue
        seen.add(u)
        if is_bad_url(u):
            continue
        candidates.append(u)
    # .jpドメインを優先
    for c in candidates:
        if '.jp' in c and 'http' in c:
            return c
    return candidates[0] if candidates else ''

def yahoo_search(query):
    """Yahoo Japan検索"""
    try:
        encoded = urllib.parse.quote(query)
        url = f'https://search.yahoo.co.jp/search?p={encoded}'
        r = session.get(url, timeout=12)
        hrefs = re.findall(r'href="(https?://[^"]+)"', r.text)
        hrefs = [h for h in hrefs if 'yahoo' not in h and 'yimg' not in h]
        return extract_best_url(hrefs)
    except Exception:
        return ''

def bing_search(query):
    """Bing検索（Yahoo検索の補完）"""
    try:
        encoded = urllib.parse.quote(query)
        url = f'https://www.bing.com/search?q={encoded}&setlang=ja'
        r = session.get(url, timeout=12)
        hrefs = re.findall(r'href="(https?://[^"&]+)"', r.text)
        hrefs = [h for h in hrefs if 'bing' not in h and 'microsoft' not in h]
        return extract_best_url(hrefs)
    except Exception:
        return ''

def normalize_phone(phone):
    """電話番号を正規化（ハイフン・全角→半角）"""
    phone = phone.strip()
    # 全角数字・ハイフンを半角に
    phone = phone.translate(str.maketrans('０１２３４５６７８９－', '0123456789-'))
    # 全角のハイフン類も変換
    phone = re.sub(r'[ー－―]', '-', phone)
    return phone

def search_by_phone(phone, company_name, prefecture):
    """電話番号で検索（複数戦略）"""
    phone_normalized = normalize_phone(phone)
    if not phone_normalized or phone_normalized == '-':
        return ''

    # 戦略1: 電話番号のみでYahoo検索
    result = yahoo_search(phone_normalized)
    if result:
        return result
    time.sleep(DELAY * 0.5)

    # 戦略2: 電話番号 + 社名でBing検索
    result = bing_search(f'{phone_normalized} {company_name}')
    if result:
        return result
    time.sleep(DELAY * 0.5)

    # 戦略3: 社名 + 住所の市区町村でYahoo検索（都道府県なし）
    # 住所から市区町村を抽出
    return ''

def search_by_address(company_name, address, prefecture):
    """住所ベースで検索"""
    if not address:
        return ''
    # 住所から市区町村を抽出（最初の市・区・町・村まで）
    city_match = re.search(r'(.+?[市区町村郡])', address)
    city = city_match.group(1) if city_match else address[:6]

    # Yahoo: 社名 + 市区町村
    result = yahoo_search(f'{company_name} {city}')
    if result:
        return result
    time.sleep(DELAY * 0.5)

    # Bing: 社名 + 市区町村 + 工務店
    result = bing_search(f'{company_name} {city} 工務店')
    return result

def main():
    # staging CSV読み込み
    with open(STAGING_FILE, encoding='utf-8-sig') as f:
        all_rows = list(csv.DictReader(f))

    # URL未取得のみ対象
    targets = [r for r in all_rows if not r.get('url', '').strip()]
    total = len(targets)
    print(f'対象: {total}社（URL未取得）')
    print(f'検索戦略: 電話番号検索 → Bing検索 → 住所ベース検索')
    print()

    # 既存の出力ファイルから引き継ぎ
    already_found = {}
    if os.path.exists(OUT_FILE):
        with open(OUT_FILE, encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                url = row.get('url', '').strip()
                if url:
                    already_found[row['company_id']] = url
        print(f'前回結果を引き継ぎ: {len(already_found)}社')

    results = dict(already_found)
    found_count = len(already_found)

    fieldnames = ['company_id', 'company_name', 'prefecture', 'address', 'phone', 'url', 'status']

    for i, row in enumerate(targets, 1):
        cid = row['company_id']
        name = row['company_name']
        phone = row.get('phone', '')
        address = row.get('address', '')
        prefecture = row.get('prefecture', '')

        # 既に前回で発見済みならスキップ
        if cid in results:
            print(f'[{i}/{total}] {name[:18]} → スキップ（前回取得済み）')
            continue

        url = ''

        # 戦略1: 電話番号検索
        if phone and phone.strip() not in ('', '-'):
            url = search_by_phone(phone, name, prefecture)
            if url:
                print(f'[{i}/{total}] {name[:18]} → [電話] {url}')

        # 戦略2: 住所ベース検索
        if not url and address:
            time.sleep(DELAY * 0.3)
            url = search_by_address(name, address, prefecture)
            if url:
                print(f'[{i}/{total}] {name[:18]} → [住所] {url}')

        if not url:
            print(f'[{i}/{total}] {name[:18]} → 未発見')
        else:
            found_count += 1
            results[cid] = url

        # 30社ごとに中間保存
        if i % 30 == 0:
            save_results(OUT_FILE, all_rows, results, fieldnames)
            print(f'  --- 中間保存: {i}社完了 / 取得:{found_count}社 ---')

        time.sleep(DELAY)

    save_results(OUT_FILE, all_rows, results, fieldnames)
    print()
    print(f'=== 完了 ===')
    print(f'新規取得: {found_count - len(already_found)}社')
    print(f'合計取得: {found_count} / {total}社')
    print(f'結果: {OUT_FILE}')

def save_results(out_file, all_rows, results, fieldnames):
    rows_to_save = []
    for r in all_rows:
        if not r.get('url', '').strip():
            r = dict(r)
            r['url'] = results.get(r['company_id'], '')
        rows_to_save.append(r)
    with open(out_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows_to_save)

if __name__ == '__main__':
    main()
