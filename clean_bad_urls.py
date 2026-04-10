"""
ポータルサイト・誤ドメインのURLをstaging CSVから削除し、再検索対象に戻す
"""
import csv, os, re, glob
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))

# 同一ドメインが複数社に当たっていたら誤URL（閾値: 4社以上）
DOMAIN_THRESHOLD = 4

# 強制除外ドメイン（追加分）
FORCE_EXCLUDE = [
    'lycorp.co.jp', 'fukuoka-k.jp', 'navitime.co.jp', 'hugkumi-life.jp',
    'b-mall.ne.jp', 'ocn.ne.jp', 'jnet-c.co.jp', 'kj-ie.co.jp',
    'suke-dachi.jp', 'jbn-support.jp', 'ie-eco.jp', 'auka.jp',
    'salesnow.jp', 'itp.ne.jp', 'ekiten.jp',
]

def extract_domain(url):
    m = re.search(r'https?://(?:www\.)?([^/]+)', url)
    return m.group(1) if m else ''

# 全ワーカーCSVのURL集計
domain_counter = Counter()
all_files = sorted(glob.glob(os.path.join(BASE, 'staging_worker*.csv')))

for fname in all_files:
    with open(fname, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            url = r.get('url', '').strip()
            if url:
                domain_counter[extract_domain(url)] += 1

# 閾値超えドメイン（ポータル疑い）＋強制除外ドメイン
bad_domains = {d for d, c in domain_counter.items() if c >= DOMAIN_THRESHOLD}
bad_domains |= set(FORCE_EXCLUDE)

# 1社しかないドメインは会社固有サイトの可能性が高いので除外
# → 閾値処理で自動除外済み

total_cleared = 0

for fname in all_files:
    with open(fname, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
        fieldnames = f.fieldnames if hasattr(f, 'fieldnames') else None

    with open(fname, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    cleared = 0
    for r in rows:
        url = r.get('url', '').strip()
        if not url:
            continue
        domain = extract_domain(url)
        if any(bad in domain for bad in bad_domains):
            r['url'] = ''
            cleared += 1

    with open(fname, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    total_cleared += cleared
    print(f'{os.path.basename(fname)}: {cleared}件クリア')

print(f'\n合計 {total_cleared}件のURLをクリア → 再検索対象に戻しました')
print(f'除外ドメイン数: {len(bad_domains)}')

# 残存URL確認
total_done = 0
total_all = 0
for fname in all_files:
    with open(fname, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    done = sum(1 for r in rows if r.get('url','').strip())
    total_all += len(rows)
    total_done += done

print(f'\nクリーンアップ後 URL取得済み: {total_done} / {total_all}社')
