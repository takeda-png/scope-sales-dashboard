"""
工務店リストのURL自動検索スクリプト
builder_list_staging.csv の各社をGoogle検索してURLを取得する

使い方:
  python search_urls.py              # 全社検索（続きから再開）
  python search_urls.py --limit 100  # 100社だけ処理
  python search_urls.py --pref 東京  # 都道府県を絞って処理
"""

import csv, time, sys, re, argparse
import urllib.parse
import urllib.request

INPUT_FILE = 'builder_list_staging.csv'
OUTPUT_FILE = 'builder_list_staging.csv'  # 上書き保存

# 除外ドメイン（ポータルサイト・SNS等はURLとして採用しない）
EXCLUDE_DOMAINS = [
    'suumo.jp', 'homes.co.jp', 'chintai.net', 'athome.co.jp',
    'mynavi.jp', 'recruit.co.jp', 'indeed.com', 'linkedin.com',
    'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com',
    'wikipedia.org', 'wikimapia.org', 'tabelog.com', 'hotpepper.jp',
    'google.com', 'google.co.jp', 'amazon.co.jp', 'rakuten.co.jp',
    'benrimap.com', 'mapion.co.jp', 'itp.ne.jp', 'townpage.jp',
    'ekiten.jp', 'seikatsu-club.coop', 'kakaku.com',
    'housing.co.jp', 'houzz.jp', 'reform-online.jp',
    'pref.', '.go.jp', 'city.', 'town.', 'village.'
]

def search_company_url(company_name, prefecture, phone=''):
    """DuckDuckGo HTMLスクレイピングで会社URLを検索"""
    # 検索クエリ：会社名 + 都道府県 + 公式サイト
    query = f'{company_name} {prefecture} 工務店 公式サイト'
    encoded = urllib.parse.quote(query)
    url = f'https://html.duckduckgo.com/html/?q={encoded}'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept-Language': 'ja,en;q=0.9',
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

        # uddg= パラメータからURLを抽出（DuckDuckGo HTML版の形式）
        pattern = r'uddg=([^&"]+)'
        matches = re.findall(pattern, html)
        seen = set()
        candidates = []
        for m in matches:
            url = urllib.parse.unquote(m).split('?')[0].rstrip('/')
            if url in seen:
                continue
            seen.add(url)
            if 'duckduckgo.com' in url:
                continue
            if any(excl in url for excl in EXCLUDE_DOMAINS):
                continue
            candidates.append(url)

        # .jp ドメインを優先
        for c in candidates:
            if '.jp' in c:
                return c
        # なければ最初の有効URL
        if candidates:
            return candidates[0]

    except Exception as e:
        pass

    return ''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0, help='処理する最大社数（0=全件）')
    parser.add_argument('--pref', type=str, default='', help='都道府県絞り込み')
    parser.add_argument('--delay', type=float, default=2.0, help='検索間隔（秒）')
    args = parser.parse_args()

    # CSVを読み込む
    with open(INPUT_FILE, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))

    # 処理対象を絞り込む（URLが未取得 = 空のもの）
    targets = [r for r in rows if not r.get('url', '').strip()]
    if args.pref:
        targets = [r for r in targets if r['prefecture'] == args.pref]
    if args.limit > 0:
        targets = targets[:args.limit]

    total = len(targets)
    found = 0
    print(f"URL検索開始: {total}社対象")
    print(f"検索間隔: {args.delay}秒 / 推定時間: {total * args.delay / 60:.0f}分")
    print("-" * 50)

    # 社名→行のインデックスを作る
    row_index = {r['company_id']: r for r in rows}

    for i, target in enumerate(targets, 1):
        name = target['company_name']
        pref = target['prefecture']
        cid = target['company_id']

        sys.stdout.write(f"\r[{i}/{total}] {name[:20]:<20}...")
        sys.stdout.flush()

        url = search_company_url(name, pref)
        if url:
            row_index[cid]['url'] = url
            found += 1
            print(f"\r[{i}/{total}] {name[:20]:<20} → {url}")
        else:
            print(f"\r[{i}/{total}] {name[:20]:<20} → 未発見")

        # 50社ごとに保存
        if i % 50 == 0:
            save_csv(list(row_index.values()))
            print(f"  >>> {i}社処理完了・保存（取得済み: {found}社）")

        time.sleep(args.delay)

    # 最終保存
    save_csv(list(row_index.values()))
    print(f"\n完了: {found}/{total}社のURLを取得")
    print(f"結果: {OUTPUT_FILE}")

def save_csv(rows):
    fieldnames = ['company_id', 'company_name', 'prefecture', 'address', 'phone', 'url', 'status']
    with open(OUTPUT_FILE, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

if __name__ == '__main__':
    main()
