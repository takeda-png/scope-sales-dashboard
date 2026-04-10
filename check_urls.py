"""
取得済みURLの死活チェッカー（20並列スレッド高速版）
結果: url_check_results.csv  (company_id, url, status, final_url, checked_at)
  status: ok / redirect / error / timeout
"""
import csv, os, glob, time, re, threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests, urllib3
urllib3.disable_warnings()

BASE = os.path.dirname(os.path.abspath(__file__))
RESULT_FILE = os.path.join(BASE, 'url_check_results.csv')
THREADS = 20
TIMEOUT = 8

FIELDNAMES = ['company_id', 'company_name', 'prefecture', 'url', 'status', 'final_url', 'note', 'checked_at']

write_lock = threading.Lock()
counter = {'ok': 0, 'redirect': 0, 'error': 0, 'timeout': 0, 'total': 0}

def make_session():
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
    })
    return s

_local = threading.local()

def get_session():
    if not hasattr(_local, 'session'):
        _local.session = make_session()
    return _local.session

def load_checked():
    if not os.path.exists(RESULT_FILE):
        return set()
    with open(RESULT_FILE, encoding='utf-8-sig') as f:
        return {r['company_id'] for r in csv.DictReader(f)}

def collect_targets(checked_ids):
    targets = {}
    for wfile in sorted(glob.glob(os.path.join(BASE, 'staging_worker*.csv'))):
        try:
            with open(wfile, encoding='utf-8-sig') as f:
                for r in csv.DictReader(f):
                    cid = r.get('company_id', '')
                    url = r.get('url', '').strip()
                    if url and cid and cid not in checked_ids:
                        targets[cid] = r
        except Exception:
            pass
    return list(targets.values())

def check_url(url):
    try:
        r = get_session().get(url, timeout=TIMEOUT, allow_redirects=True, verify=False)
        final = r.url.rstrip('/')
        original = url.rstrip('/')
        if final != original:
            return 'redirect', final, f'HTTP {r.status_code}'
        return 'ok', final, f'HTTP {r.status_code}'
    except requests.exceptions.Timeout:
        return 'timeout', '', 'timeout'
    except Exception as e:
        return 'error', '', str(e)[:60]

def process_row(row):
    cid  = row['company_id']
    url  = row['url'].strip()
    name = row.get('company_name', '')
    pref = row.get('prefecture', '')

    status, final_url, note = check_url(url)

    result_row = {
        'company_id':   cid,
        'company_name': name,
        'prefecture':   pref,
        'url':          url,
        'status':       status,
        'final_url':    final_url,
        'note':         note,
        'checked_at':   datetime.now().strftime('%Y/%m/%d %H:%M:%S'),
    }

    exists = os.path.exists(RESULT_FILE)
    with write_lock:
        with open(RESULT_FILE, 'a', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction='ignore')
            if not exists:
                writer.writeheader()
            writer.writerow(result_row)
        counter['total'] += 1
        if 'ok' in status:      counter['ok'] += 1
        elif status == 'redirect': counter['redirect'] += 1
        elif status == 'timeout':  counter['timeout'] += 1
        else:                      counter['error'] += 1

    return status, name, url

def main():
    print('[Checker] URL死活チェック開始（20並列）')
    print(f'[Checker] 結果: {RESULT_FILE}')
    print('[Checker] Ctrl+C で停止\n')

    while True:
        checked_ids = load_checked()
        targets = collect_targets(checked_ids)

        if not targets:
            print(f'[Checker] 待機中... チェック済み: {len(checked_ids)}社', flush=True)
            time.sleep(10)
            continue

        print(f'[Checker] 未チェック: {len(targets)}社 / {THREADS}並列で開始', flush=True)
        start = time.time()

        with ThreadPoolExecutor(max_workers=THREADS) as executor:
            futures = {executor.submit(process_row, row): row for row in targets}
            done_count = 0
            for future in as_completed(futures):
                try:
                    status, name, url = future.result()
                    done_count += 1
                    if done_count % 50 == 0:
                        elapsed = time.time() - start
                        rate = done_count / elapsed
                        remain = len(targets) - done_count
                        eta = int(remain / rate) if rate > 0 else 0
                        print(f'[Checker] {done_count}/{len(targets)} ({rate:.1f}件/秒) 残り約{eta}秒', flush=True)
                except Exception:
                    pass

        elapsed = time.time() - start
        c = counter
        print(f'\n[Checker] 完了: {c["total"]}社 ok:{c["ok"]} redirect:{c["redirect"]} timeout:{c["timeout"]} error:{c["error"]} ({elapsed:.0f}秒)\n', flush=True)
        time.sleep(15)

if __name__ == '__main__':
    main()
