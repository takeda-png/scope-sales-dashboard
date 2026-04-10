#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
import_export_data.py
export_sales_data.csv から埼玉のみを抽出して
form-automation-saitama/companies.csv に重複なく追加する

使い方:
  python import_export_data.py             # 埼玉のみインポート（デフォルト）
  python import_export_data.py --dry-run   # 実際には書き込まず件数だけ確認
  python import_export_data.py --all       # 都道府県フィルタなし（全件）
"""

import csv
import sys
import os
from urllib.parse import urlparse

SRC_FILE  = os.path.join(os.path.dirname(__file__), 'export_sales_data.csv')
DEST_FILE = os.path.join(os.path.dirname(__file__), '..', 'form-automation-saitama', 'companies.csv')

DRY_RUN  = '--dry-run' in sys.argv
ALL_PREF = '--all'     in sys.argv
PREF_FILTERS = ['埼玉', 'さいたま市']  # さいたま市（ひらがな）も含む

def normalize_url(url):
    try:
        return urlparse(url.strip()).netloc.lower().replace('www.', '')
    except:
        return url.lower().strip()

def load_existing_urls(path):
    existing = set()
    if not os.path.exists(path):
        return existing
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            u = row.get('url', '').strip()
            if u:
                existing.add(normalize_url(u))
    return existing

def csv_escape(s):
    s = str(s).replace('\r', '').replace('\n', ' ').strip()
    if ',' in s or '"' in s:
        return '"' + s.replace('"', '""') + '"'
    return s

def main():
    print('=== export_sales_data.csv インポート ===')
    print(f'ソース : {SRC_FILE}')
    print(f'出力先 : {DEST_FILE}')
    print(f'フィルタ: {"なし（全件）" if ALL_PREF else " / ".join(PREF_FILTERS) + "のみ"}')
    if DRY_RUN:
        print('モード  : DRY RUN（書き込みなし）')
    print()

    if not os.path.exists(SRC_FILE):
        print(f'エラー: {SRC_FILE} が見つかりません')
        sys.exit(1)

    existing = load_existing_urls(DEST_FILE)
    print(f'既存 companies.csv: {len(existing)}件')

    # export_sales_data.csv を読み込み（cp932）
    to_add = []
    skipped_pref = 0
    skipped_dup  = 0
    skipped_nourl = 0

    with open(SRC_FILE, encoding='cp932') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        name_col = headers[0]   # 会社名
        addr_col = headers[1]   # 住所
        url_col  = headers[2]   # サイトURL

        for row in reader:
            addr = row[addr_col].strip()
            url  = row[url_col].strip()
            name = row[name_col].strip()

            # 都道府県フィルタ（埼玉 or さいたま市）
            if not ALL_PREF and not any(f in addr for f in PREF_FILTERS):
                skipped_pref += 1
                continue

            # URL なし
            if not url:
                skipped_nourl += 1
                continue

            # 重複チェック
            norm = normalize_url(url)
            if norm in existing:
                skipped_dup += 1
                continue

            existing.add(norm)
            note = addr[:50] if addr else ''
            to_add.append((url, name, note))

    print(f'都道府県フィルタでスキップ: {skipped_pref}件')
    print(f'URL無しでスキップ          : {skipped_nourl}件')
    print(f'重複スキップ               : {skipped_dup}件')
    print(f'新規追加対象               : {len(to_add)}件')

    if not to_add:
        print('\n追加対象なし。終了します。')
        return

    if DRY_RUN:
        print('\n[DRY RUN] 実際の書き込みはスキップ。')
        print('追加サンプル（先頭5件）:')
        for url, name, note in to_add[:5]:
            print(f'  {url} | {name} | {note}')
        return

    # companies.csv に追記
    with open(DEST_FILE, 'a', encoding='utf-8', newline='') as f:
        for url, name, note in to_add:
            line = f'{csv_escape(url)},{csv_escape(name)},,pending,,{csv_escape(note)}\n'
            f.write(line)

    print(f'\n[完了] {len(to_add)}件を追加しました')
    print(f'companies.csv 合計: {len(existing)}件')

if __name__ == '__main__':
    main()
