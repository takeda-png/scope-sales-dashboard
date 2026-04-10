#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
エラー修正スクリプト
- Target page closed / timeout / ネットワークエラー → pending に戻して再送対象に
- tel: / mailto: URL → no_form にしてスキップ
"""

import csv
import shutil
from datetime import datetime
from collections import Counter

RETRY_KEYWORDS = [
    'Target page',
    'context or browser has been closed',
    'timeout',
    'Timeout',
    'ERR_NETWORK_IO_SUSPENDED',
    'interrupted by another',
]
SKIP_PREFIXES = ['tel:', 'mailto:']

with open('companies.csv', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
fieldnames = list(rows[0].keys())

shutil.copy('companies.csv', f'companies_backup_fixretry_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')

retry_count = 0
no_form_count = 0
corrupt_count = 0

# 壊れた行（None/空ステータス・URLが正常でない）を除去
valid_statuses = {'pending', 'submitted', 'manual_check', 'error', 'skip', 'no_form'}
rows = [r for r in rows if r.get('status', '') in valid_statuses or (r.get('url', '').startswith('http') and not r.get('status', ''))]
rows_clean = []
for r in rows:
    if not r.get('url', '').startswith('http'):
        corrupt_count += 1
        continue
    if r.get('status', '') not in valid_statuses:
        r['status'] = 'pending'
        r['submitted_at'] = ''
        r['note'] = ''
        corrupt_count += 1
    rows_clean.append(r)
rows = rows_clean

for r in rows:
    if r['status'] != 'error':
        continue

    note = r.get('note', '')
    contact = r.get('contact_url', '')

    # tel: / mailto: → no_form
    if any(contact.startswith(p) for p in SKIP_PREFIXES) or \
       any(note.startswith(f'page.goto: net::ERR_ABORTED at {p}') for p in SKIP_PREFIXES):
        r['status'] = 'no_form'
        r['note'] = 'tel or mailto url'
        no_form_count += 1

    # 再試行可能エラー → pending
    elif any(kw in note for kw in RETRY_KEYWORDS):
        r['status'] = 'pending'
        r['submitted_at'] = ''
        r['note'] = ''
        retry_count += 1

with open('companies.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

c = Counter(r['status'] for r in rows)
print(f'修正完了')
print(f'  pending に戻した（再送対象）: {retry_count}件')
print(f'  no_form にした: {no_form_count}件')
print(f'  壊れた行を修復: {corrupt_count}件')
print()
print('現在のステータス:')
for k, v in sorted(c.items(), key=lambda x: -x[1]):
    print(f'  {k}: {v}')
