"""
ワーカーCSVをマージして builder_list_staging.csv を更新する
"""
import csv, sys, glob
sys.stdout.reconfigure(encoding='utf-8')

STAGING_FILE = 'builder_list_staging.csv'

with open(STAGING_FILE, encoding='utf-8-sig') as f:
    staging = {r['company_id']: r for r in csv.DictReader(f)}

merged = 0
for worker_file in sorted(glob.glob('staging_worker*.csv')):
    with open(worker_file, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            cid = row['company_id']
            url = row.get('url', '').strip()
            if cid in staging and url and not staging[cid].get('url', '').strip():
                staging[cid]['url'] = url
                merged += 1

fieldnames = ['company_id','company_name','prefecture','address','phone','url','status']
with open(STAGING_FILE, 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(staging.values())

with_url = sum(1 for r in staging.values() if r.get('url','').strip())
print(f'マージ完了: +{merged}社のURL追加')
print(f'URL取得済み合計: {with_url} / {len(staging)}社')
