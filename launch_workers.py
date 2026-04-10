"""全6ワーカーを並列起動し、全完了まで待機して自動マージ"""
import subprocess, sys, os, time

BASE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(BASE, 'search_urls_fast.py')
PYTHON = sys.executable
DELAY = '5.0'

procs = {}
for w in range(6):
    p = subprocess.Popen(
        [PYTHON, SCRIPT, '--worker', str(w), '--delay', DELAY],
        cwd=BASE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
        bufsize=1,
    )
    procs[w] = p
    print(f'[Launcher] Worker{w} 起動 PID={p.pid}')
    time.sleep(1)

# リアルタイムで全ワーカーの出力を読む（ノンブロッキング）
import threading

def stream(wid, proc):
    for line in proc.stdout:
        print(f'[W{wid}] {line}', end='', flush=True)
    proc.wait()
    print(f'[W{wid}] 終了 (code={proc.returncode})')

threads = [threading.Thread(target=stream, args=(w, p), daemon=True) for w, p in procs.items()]
for t in threads: t.start()

print(f'\n[Launcher] 6ワーカー起動完了。完了まで待機中...\n')
for t in threads: t.join()

print('\n[Launcher] 全ワーカー完了！マージ&インポートを実行します...')
subprocess.run([PYTHON, os.path.join(BASE, 'merge_workers.py')], cwd=BASE)
subprocess.run([PYTHON, os.path.join(BASE, 'import_builders.py')], cwd=BASE)
print('[Launcher] 完了！')
