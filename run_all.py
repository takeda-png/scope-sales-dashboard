#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
フォーム営業 全自動ループスクリプト
pipeline.js 実行 → エラー修正 → pending がなくなるまで繰り返す
"""

import csv
import subprocess
import shutil
import sys
import time
from collections import Counter
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

CSV_FILE = 'companies.csv'

RETRY_KEYWORDS = [
    'Target page',
    'context or browser has been closed',
    'timeout',
    'Timeout',
    'ERR_NETWORK_IO_SUSPENDED',
    'interrupted by another',
]
SKIP_PREFIXES = ['tel:', 'mailto:']


def load_companies():
    with open(CSV_FILE, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def save_companies(rows, fieldnames):
    with open(CSV_FILE, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def get_status_counts():
    rows = load_companies()
    return Counter(r['status'] for r in rows)


def fix_errors():
    rows = load_companies()
    fieldnames = list(rows[0].keys())
    shutil.copy(CSV_FILE, f'companies_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')

    retry_count = 0
    no_form_count = 0

    for r in rows:
        if r['status'] != 'error':
            continue
        note = r.get('note', '')
        contact = r.get('contact_url', '')

        if any(contact.startswith(p) for p in SKIP_PREFIXES) or \
           any(note.startswith(f'page.goto: net::ERR_ABORTED at {p}') for p in SKIP_PREFIXES):
            r['status'] = 'no_form'
            r['note'] = 'tel or mailto url'
            no_form_count += 1
        elif any(kw in note for kw in RETRY_KEYWORDS):
            r['status'] = 'pending'
            r['submitted_at'] = ''
            r['note'] = ''
            retry_count += 1

    save_companies(rows, fieldnames)
    return retry_count, no_form_count


def run_pipeline():
    log_file = f'logs/pipeline_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    print(f'  ログ: {log_file}')
    with open(log_file, 'w', encoding='utf-8') as f:
        proc = subprocess.run(
            ['node', 'pipeline.js'],
            stdout=f, stderr=subprocess.STDOUT,
            encoding='utf-8'
        )
    # 結果サマリー取得
    with open(log_file, encoding='utf-8') as f:
        lines = f.readlines()
    summary = [l.strip() for l in lines if '完了:' in l or 'pending:' in l]
    return summary


def main():
    import os
    os.makedirs('logs', exist_ok=True)

    batch = 0
    prev_pending = None

    print('=' * 60)
    print('フォーム営業 全自動ループ開始')
    print('=' * 60)

    while True:
        batch += 1
        counts = get_status_counts()
        pending = counts.get('pending', 0)

        print(f'\n【バッチ {batch}】{datetime.now().strftime("%H:%M:%S")}')
        print(f'  pending: {pending}件 / submitted: {counts.get("submitted", 0)}件 / error: {counts.get("error", 0)}件')

        if pending == 0:
            print('\n✅ pending が0件になりました。全送信完了！')
            break

        # 前回と同じ pending 数なら無限ループ防止
        if prev_pending is not None and pending >= prev_pending:
            print(f'\n⚠️ pendingが減らなくなりました（{prev_pending} → {pending}）。処理を終了します。')
            break

        prev_pending = pending

        print(f'  → pipeline.js 実行中...')
        summary = run_pipeline()
        for s in summary:
            print(f'  {s}')

        print(f'  → エラー修正中...')
        retry, no_form = fix_errors()
        print(f'  pendingに戻した: {retry}件 / no_form: {no_form}件')

        counts_after = get_status_counts()
        print(f'  修正後: pending={counts_after.get("pending", 0)} / submitted={counts_after.get("submitted", 0)} / error={counts_after.get("error", 0)}')

        # 3秒待機
        time.sleep(3)

    # 最終サマリー
    print('\n' + '=' * 60)
    print('最終結果')
    print('=' * 60)
    final = get_status_counts()
    for k, v in sorted(final.items(), key=lambda x: -x[1]):
        print(f'  {k}: {v}')


if __name__ == '__main__':
    main()
