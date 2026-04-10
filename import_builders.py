"""
builder_list_staging.csv から URL取得済み社を companies.csv にインポートする

使い方:
  python import_builders.py              # URLありの全社をインポート
  python import_builders.py --pref 東京  # 都道府県を絞ってインポート
  python import_builders.py --all        # URL未取得分も含めてインポート
"""

import csv, argparse
from datetime import datetime

STAGING_FILE = 'builder_list_staging.csv'
COMPANIES_FILE = 'companies.csv'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pref', type=str, default='', help='都道府県絞り込み')
    parser.add_argument('--all', action='store_true', help='URL未取得分も含める')
    args = parser.parse_args()

    # 既存companies.csvを読み込む
    with open(COMPANIES_FILE, encoding='utf-8') as f:
        existing = list(csv.DictReader(f))
    existing_names = {r['company_name'].strip() for r in existing}
    existing_urls = {r['url'].strip() for r in existing if r.get('url')}

    # ステージングCSVを読み込む
    with open(STAGING_FILE, encoding='utf-8-sig') as f:
        staging = list(csv.DictReader(f))

    # フィルタリング
    to_add = []
    skip_no_url = 0
    skip_dup = 0

    for row in staging:
        name = row['company_name'].strip()
        url = row.get('url', '').strip()
        pref = row.get('prefecture', '')

        # 都道府県フィルタ
        if args.pref and pref != args.pref:
            continue

        # URL未取得はスキップ（--allオプションがない場合）
        if not url and not args.all:
            skip_no_url += 1
            continue

        # 既存との重複チェック（社名）
        name_clean = name.replace('㈱','').replace('㈲','').replace('株式会社','').replace('有限会社','').strip()
        is_dup = any(
            name_clean == ex.replace('㈱','').replace('㈲','').replace('株式会社','').replace('有限会社','').strip()
            for ex in existing_names
        )
        if is_dup:
            skip_dup += 1
            continue

        to_add.append({
            'url': url,
            'company_name': name,
            'contact_url': '',
            'status': 'pending',
            'submitted_at': '',
            'note': f"{pref} {row.get('address','')}"
        })

    # companies.csv に追記
    all_rows = existing + to_add
    with open(COMPANIES_FILE, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['url','company_name','contact_url','status','submitted_at','note'])
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"インポート完了")
    print(f"  追加: {len(to_add)}社")
    print(f"  スキップ（URL未取得）: {skip_no_url}社")
    print(f"  スキップ（重複）: {skip_dup}社")
    print(f"  companies.csv 合計: {len(all_rows)}社")

if __name__ == '__main__':
    main()
