"""
工務店URL検索 + フォーム営業 監視サーバー
http://localhost:8765        → URL検索モニター
http://localhost:8765/pipeline → フォーム営業ダッシュボード
"""
import csv, os, json, time, re
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
STAGING = os.path.join(BASE, 'builder_list_staging.csv')

WORKERS = [
    {'id': 0, 'label': '北海道〜福島'},
    {'id': 1, 'label': '栃木〜神奈川'},
    {'id': 2, 'label': '富山〜愛知'},
    {'id': 3, 'label': '三重〜鳥取'},
    {'id': 4, 'label': '島根〜高知'},
    {'id': 5, 'label': '福岡〜沖縄'},
]

def get_stats():
    workers = []
    total_done = 0
    total_all = 0

    for w in WORKERS:
        wid = w['id']
        fname = os.path.join(BASE, f'staging_worker{wid}.csv')
        if not os.path.exists(fname):
            workers.append({'id': wid, 'label': w['label'], 'done': 0, 'total': 0, 'pct': 0, 'recent': []})
            continue
        try:
            with open(fname, encoding='utf-8-sig') as f:
                rows = list(csv.DictReader(f))
            done = sum(1 for r in rows if r.get('url', '').strip())
            total = len(rows)
            total_done += done
            total_all += total
            # 直近5件の取得済みURLを抽出
            recent = [(r['company_name'], r['url']) for r in rows if r.get('url', '').strip()][-5:]
            workers.append({
                'id': wid,
                'label': w['label'],
                'done': done,
                'total': total,
                'pct': round(done / total * 100, 1) if total else 0,
                'recent': recent,
            })
        except Exception as e:
            workers.append({'id': wid, 'label': w['label'], 'done': 0, 'total': 0, 'pct': 0, 'recent': [], 'error': str(e)})

    return {
        'updated': datetime.now().strftime('%H:%M:%S'),
        'total_done': total_done,
        'total_all': total_all,
        'total_pct': round(total_done / total_all * 100, 1) if total_all else 0,
        'workers': workers,
    }

HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>工務店URL検索 モニター</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; }
.header { padding: 20px 28px; border-bottom: 1px solid #1e293b; display: flex; align-items: center; justify-content: space-between; }
.header h1 { font-size: 20px; font-weight: 700; color: #f1f5f9; }
.badge-live { background: #22c55e; color: #fff; font-size: 11px; padding: 2px 8px; border-radius: 20px; margin-left: 10px; animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
.updated { font-size: 12px; color: #64748b; }

.summary { display: flex; gap: 16px; padding: 20px 28px; flex-wrap: wrap; }
.s-card { background: #1e293b; border-radius: 10px; padding: 16px 24px; min-width: 140px; text-align: center; }
.s-card .num { font-size: 32px; font-weight: 800; }
.s-card .lbl { font-size: 12px; color: #94a3b8; margin-top: 4px; }
.s-card.main .num { color: #38bdf8; }
.s-card.done .num { color: #4ade80; }
.s-card.remain .num { color: #f59e0b; }

.progress-bar-wrap { padding: 0 28px 8px; }
.progress-outer { background: #1e293b; border-radius: 8px; height: 20px; overflow: hidden; }
.progress-inner { height: 100%; background: linear-gradient(90deg, #38bdf8, #6366f1); border-radius: 8px; transition: width .6s ease; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; color: #fff; min-width: 30px; }

.workers { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; padding: 20px 28px; }
.w-card { background: #1e293b; border-radius: 10px; padding: 16px; }
.w-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.w-name { font-weight: 700; font-size: 14px; }
.w-id { font-size: 11px; color: #64748b; }
.w-nums { font-size: 13px; color: #94a3b8; }
.w-nums span { color: #4ade80; font-weight: 700; }
.w-bar-outer { background: #0f172a; border-radius: 6px; height: 8px; margin: 8px 0; overflow: hidden; }
.w-bar-inner { height: 100%; background: linear-gradient(90deg, #38bdf8, #818cf8); border-radius: 6px; transition: width .5s ease; }
.w-recent { margin-top: 10px; border-top: 1px solid #2d3748; padding-top: 8px; }
.w-recent-title { font-size: 11px; color: #64748b; margin-bottom: 4px; }
.w-recent-item { font-size: 11px; color: #94a3b8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding: 2px 0; }
.w-recent-item a { color: #38bdf8; text-decoration: none; }
.w-recent-item a:hover { text-decoration: underline; }
.w-pct { font-size: 12px; font-weight: 700; color: #a5b4fc; }
.idle { opacity: .45; }

.footer { text-align: center; padding: 20px; font-size: 12px; color: #475569; }
</style>
</head>
<body>
<div class="header">
  <div><h1>工務店URL検索 <span class="badge-live">LIVE</span></h1></div>
  <div class="updated" id="updated">--</div>
</div>

<div class="summary">
  <div class="s-card main"><div class="num" id="total-all">--</div><div class="lbl">合計</div></div>
  <div class="s-card done"><div class="num" id="total-done">--</div><div class="lbl">取得済み</div></div>
  <div class="s-card remain"><div class="num" id="total-remain">--</div><div class="lbl">残り</div></div>
  <div class="s-card"><div class="num" id="total-pct" style="color:#a5b4fc">--%</div><div class="lbl">進捗</div></div>
</div>

<div class="progress-bar-wrap">
  <div class="progress-outer">
    <div class="progress-inner" id="global-bar" style="width:0%">0%</div>
  </div>
</div>

<div class="workers" id="workers"></div>

<div class="footer">3秒ごとに自動更新 ／ search_monitor.py</div>

<script>
async function refresh() {
  try {
    const r = await fetch('/data');
    const d = await r.json();

    document.getElementById('updated').textContent = '最終更新: ' + d.updated;
    document.getElementById('total-all').textContent = d.total_all.toLocaleString();
    document.getElementById('total-done').textContent = d.total_done.toLocaleString();
    document.getElementById('total-remain').textContent = (d.total_all - d.total_done).toLocaleString();
    document.getElementById('total-pct').textContent = d.total_pct + '%';

    const bar = document.getElementById('global-bar');
    bar.style.width = d.total_pct + '%';
    bar.textContent = d.total_pct + '%';

    const wrap = document.getElementById('workers');
    wrap.innerHTML = d.workers.map(w => {
      const idle = w.total === 0;
      const pct = w.pct || 0;
      const recentHtml = w.recent && w.recent.length
        ? '<div class="w-recent"><div class="w-recent-title">直近取得</div>'
          + w.recent.slice().reverse().map(([name, url]) =>
              `<div class="w-recent-item">${esc(name.slice(0,18))} → <a href="${esc(url)}" target="_blank">${esc(url.replace(/^https?:\/\//,'').slice(0,40))}</a></div>`
            ).join('')
          + '</div>'
        : '';
      return `
        <div class="w-card${idle?' idle':''}">
          <div class="w-header">
            <div><div class="w-name">Worker${w.id}</div><div class="w-id">${w.label}</div></div>
            <div class="w-pct">${pct}%</div>
          </div>
          <div class="w-nums"><span>${w.done}</span> / ${w.total} 社取得</div>
          <div class="w-bar-outer"><div class="w-bar-inner" style="width:${pct}%"></div></div>
          ${recentHtml}
        </div>`;
    }).join('');
  } catch(e) {
    document.getElementById('updated').textContent = 'サーバー接続エラー';
  }
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

refresh();
setInterval(refresh, 3000);
</script>
</body>
</html>"""

def get_builders_data():
    staging_file  = os.path.join(BASE, 'builder_list_staging.csv')
    companies_file = os.path.join(BASE, 'companies.csv')
    config_file   = os.path.join(BASE, 'config.json')

    # メッセージタイトル
    msg_title = 'SCOPE営業'
    try:
        with open(config_file, encoding='utf-8') as f:
            cfg = json.load(f)
        for line in cfg.get('message','').splitlines():
            line = line.strip()
            if line.startswith('・'):
                msg_title = line.lstrip('・').strip(); break
    except Exception:
        pass

    # companies.csv から送信状況を社名キーで引く
    sent_map = {}
    if os.path.exists(companies_file):
        with open(companies_file, encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                key = re.sub(r'[㈱㈲株式会社有限会社\s]', '', r.get('company_name',''))
                sent_map[key] = {'status': r.get('status',''), 'submitted_at': r.get('submitted_at','')}

    # url_check_results.csv からチェック結果を引く
    check_map = {}  # company_id → {status, final_url, note}
    check_file = os.path.join(BASE, 'url_check_results.csv')
    if os.path.exists(check_file):
        with open(check_file, encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                check_map[r['company_id']] = {
                    'check_status': r.get('status',''),
                    'final_url':    r.get('final_url',''),
                    'check_note':   r.get('note',''),
                }

    if not os.path.exists(staging_file):
        return {'updated': datetime.now().strftime('%H:%M:%S'), 'title': msg_title,
                'stats': {}, 'total': 0, 'rows': []}

    with open(staging_file, encoding='utf-8-sig') as f:
        staging = list(csv.DictReader(f))

    # staging_worker*.csv から最新URLを上書きマージ（マージ前でもリアルタイム反映）
    import glob as _glob
    url_map = {r['company_id']: r.get('url', '').strip() for r in staging if r.get('company_id')}
    for wfile in sorted(_glob.glob(os.path.join(BASE, 'staging_worker*.csv'))):
        try:
            with open(wfile, encoding='utf-8-sig') as f:
                for wr in csv.DictReader(f):
                    cid = wr.get('company_id', '')
                    wurl = wr.get('url', '').strip()
                    if cid and wurl:
                        url_map[cid] = wurl
        except Exception:
            pass
    for r in staging:
        cid = r.get('company_id', '')
        if cid and url_map.get(cid):
            r['url'] = url_map[cid]

    stats = {'url_found': 0, 'url_missing': 0,
             'submitted': 0, 'skip': 0, 'error': 0, 'pending_send': 0,
             'url_ok': 0, 'url_error': 0}
    rows = []
    for r in staging:
        name  = r.get('company_name', '')
        url   = r.get('url', '').strip()
        pref  = r.get('prefecture', '')
        cid   = r.get('company_id', '')
        key   = re.sub(r'[㈱㈲株式会社有限会社\s]', '', name)
        send  = sent_map.get(key, {})
        send_status   = send.get('status', '')
        submitted_at  = send.get('submitted_at', '')
        chk   = check_map.get(cid, {})
        check_status  = chk.get('check_status', '')
        final_url     = chk.get('final_url', '')
        check_note    = chk.get('check_note', '')

        if url:
            stats['url_found'] += 1
        else:
            stats['url_missing'] += 1

        if send_status == 'submitted':
            stats['submitted'] += 1
        elif send_status in ('skip','error'):
            stats[send_status] += 1
        elif url:
            stats['pending_send'] += 1

        if check_status and 'ok' in check_status:
            stats['url_ok'] += 1
        elif check_status in ('error', 'timeout'):
            stats['url_error'] += 1

        rows.append({
            'company_name': name,
            'prefecture':   pref,
            'url':          url,
            'send_status':  send_status,
            'submitted_at': submitted_at,
            'check_status': check_status,
            'final_url':    final_url,
            'check_note':   check_note,
        })

    # 送信済み→URL取得済み→未取得 の順にソート
    order = {'submitted': 0, 'skip': 1, 'error': 2, '': 3}
    rows.sort(key=lambda r: (order.get(r['send_status'], 3), r['prefecture'], r['company_name']))

    return {
        'updated': datetime.now().strftime('%H:%M:%S'),
        'title': msg_title,
        'stats': stats,
        'total': len(rows),
        'rows': rows,
    }


BUILDERS_HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>工務店営業リスト</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', sans-serif; background: #f8fafc; color: #1e293b; font-size: 13px; }
.header { background: #0f172a; color: #f1f5f9; padding: 16px 24px; display: flex; align-items: center; justify-content: space-between; }
.header h1 { font-size: 18px; font-weight: 700; }
.nav a { color: #94a3b8; text-decoration: none; font-size: 12px; margin-left: 16px; }
.nav a:hover { color: #fff; }
.badge-live { background: #22c55e; color: #fff; font-size: 10px; padding: 1px 7px; border-radius: 20px; margin-left: 8px; animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }

.summary { display: flex; gap: 12px; padding: 16px 24px; flex-wrap: wrap; }
.s-card { background: #fff; border-radius: 8px; padding: 12px 20px; min-width: 110px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,.08); border-top: 3px solid #e2e8f0; }
.s-card .num { font-size: 26px; font-weight: 800; }
.s-card .lbl { font-size: 11px; color: #94a3b8; margin-top: 2px; }
.s-card.url_found  { border-color: #38bdf8; } .s-card.url_found .num  { color: #0284c7; }
.s-card.url_miss   { border-color: #e2e8f0; } .s-card.url_miss .num   { color: #94a3b8; }
.s-card.submitted  { border-color: #22c55e; } .s-card.submitted .num  { color: #16a34a; }
.s-card.pend_send  { border-color: #f59e0b; } .s-card.pend_send .num  { color: #d97706; }
.s-card.skip       { border-color: #fb923c; } .s-card.skip .num       { color: #ea580c; }
.s-card.error      { border-color: #ef4444; } .s-card.error .num      { color: #dc2626; }

.toolbar { padding: 0 24px 12px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.filter-btn { border: 1.5px solid #cbd5e1; background: #fff; border-radius: 20px; padding: 4px 14px; cursor: pointer; font-size: 12px; color: #475569; transition: all .15s; }
.filter-btn:hover { background: #f1f5f9; }
.filter-btn.active { color: #fff; border-color: transparent; }
.filter-btn.active.all       { background: #0f172a; }
.filter-btn.active.url_found { background: #0284c7; }
.filter-btn.active.url_miss  { background: #94a3b8; }
.filter-btn.active.submitted { background: #16a34a; }
.filter-btn.active.pend_send { background: #d97706; }
.filter-btn.active.error     { background: #dc2626; }
.pref-select { padding: 5px 10px; border: 1.5px solid #e2e8f0; border-radius: 6px; font-size: 12px; }
.search-box  { padding: 5px 12px; border: 1.5px solid #e2e8f0; border-radius: 6px; font-size: 12px; width: 180px; }
.count-label { margin-left: auto; font-size: 12px; color: #94a3b8; }

.table-wrap { padding: 0 24px 32px; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
th { background: #f1f5f9; padding: 9px 12px; text-align: left; font-size: 12px; color: #64748b; font-weight: 600; white-space: nowrap; }
td { padding: 8px 12px; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #fefce8; }
tr.hidden { display: none; }
a { color: #6366f1; text-decoration: none; font-size: 12px; }
a:hover { text-decoration: underline; }
.badge { display: inline-block; padding: 2px 9px; border-radius: 12px; font-size: 11px; font-weight: 600; white-space: nowrap; }
.badge.submitted { background: #16a34a; color:#fff; }
.badge.skip      { background: #ea580c; color:#fff; }
.badge.error     { background: #dc2626; color:#fff; }
.badge.pending   { background: #f59e0b; color:#fff; }
.badge.no_url    { background: #e2e8f0; color:#94a3b8; }
.badge.not_sent  { background: #e0f2fe; color:#0284c7; }
.title-chip { background: #eff6ff; color: #2563eb; border-radius: 4px; padding: 2px 8px; font-size: 11px; }
.pref-tag { background: #f1f5f9; color: #64748b; border-radius: 4px; padding: 1px 7px; font-size: 11px; }
.chk-ok      { color: #16a34a; font-weight:700; font-size:12px; }
.chk-redirect{ color: #d97706; font-weight:700; font-size:12px; }
.chk-error   { color: #dc2626; font-weight:700; font-size:12px; }
.chk-pending { color: #cbd5e1; font-size:12px; }
</style>
</head>
<body>
<div class="header">
  <h1>工務店営業リスト <span class="badge-live">LIVE</span></h1>
  <div class="nav">
    <a href="/">URL検索モニター</a>
    <a href="/pipeline">フォーム営業</a>
  </div>
</div>

<div class="summary" id="summary"></div>

<div class="toolbar">
  <button class="filter-btn active all"       onclick="setFilter('all',this)">すべて</button>
  <button class="filter-btn submitted"        onclick="setFilter('submitted',this)">送信成功</button>
  <button class="filter-btn pend_send"        onclick="setFilter('pending_send',this)">送信待ち</button>
  <button class="filter-btn url_found"        onclick="setFilter('url_found',this)">URL取得済み</button>
  <button class="filter-btn url_miss"         onclick="setFilter('url_miss',this)">URL未取得</button>
  <button class="filter-btn error"            onclick="setFilter('error',this)">エラー</button>
  <select class="pref-select" onchange="applyFilter()" id="pref-select"><option value="">都道府県</option></select>
  <input  class="search-box" type="text" placeholder="会社名で検索..." oninput="applyFilter()">
  <span class="count-label" id="count-label"></span>
</div>

<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>#</th>
      <th>会社名</th>
      <th>都道府県</th>
      <th>サイトURL</th>
      <th>HP確認</th>
      <th>送信日時</th>
      <th>ステータス</th>
      <th>送付内容タイトル</th>
    </tr>
  </thead>
  <tbody id="tbody"></tbody>
</table>
</div>
<div style="text-align:center;padding:12px;font-size:11px;color:#94a3b8" id="footer-updated"></div>

<script>
let allRows = [];
let currentFilter = 'all';
let msgTitle = '';

async function refresh() {
  try {
    const r = await fetch('/builders/data');
    const d = await r.json();
    allRows = d.rows || [];
    msgTitle = d.title || '';

    const s = d.stats || {};
    document.getElementById('summary').innerHTML = `
      <div class="s-card"><div class="num">${(d.total||0).toLocaleString()}</div><div class="lbl">合計</div></div>
      <div class="s-card url_found"><div class="num">${(s.url_found||0).toLocaleString()}</div><div class="lbl">URL取得済み</div></div>
      <div class="s-card url_miss"><div class="num">${(s.url_missing||0).toLocaleString()}</div><div class="lbl">URL未取得</div></div>
      <div class="s-card submitted"><div class="num">${(s.submitted||0).toLocaleString()}</div><div class="lbl">送信成功</div></div>
      <div class="s-card pend_send"><div class="num">${(s.pending_send||0).toLocaleString()}</div><div class="lbl">送信待ち</div></div>
      <div class="s-card error"><div class="num">${(s.error||0).toLocaleString()}</div><div class="lbl">エラー</div></div>
    `;
    document.getElementById('footer-updated').textContent = '最終更新: ' + d.updated + '  ／  5秒ごとに自動更新';

    // 都道府県リスト更新
    const prefs = [...new Set(allRows.map(r => r.prefecture).filter(Boolean))].sort();
    const sel = document.getElementById('pref-select');
    const cur = sel.value;
    sel.innerHTML = '<option value="">都道府県</option>' + prefs.map(p => `<option${p===cur?' selected':''}>${p}</option>`).join('');

    applyFilter();
  } catch(e) {}
}

function setFilter(f, btn) {
  currentFilter = f;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active','all','url_found','url_miss','submitted','pend_send','error'));
  const cls = {all:'all', url_found:'url_found', url_miss:'url_miss', submitted:'submitted', pending_send:'pend_send', error:'error'}[f] || 'all';
  btn.classList.add('active', cls);
  applyFilter();
}

function applyFilter() {
  const q    = document.querySelector('.search-box').value.trim().toLowerCase();
  const pref = document.getElementById('pref-select').value;
  const tbody = document.getElementById('tbody');
  let shown = 0;
  tbody.innerHTML = allRows.map((r, i) => {
    const hasUrl = !!r.url;
    const matchFilter =
      currentFilter === 'all'         ? true :
      currentFilter === 'url_found'   ? hasUrl && !r.send_status :
      currentFilter === 'url_miss'    ? !hasUrl :
      currentFilter === 'submitted'   ? r.send_status === 'submitted' :
      currentFilter === 'pending_send'? hasUrl && !r.send_status :
      currentFilter === 'error'       ? r.send_status === 'error' : true;
    const matchPref   = !pref || r.prefecture === pref;
    const matchSearch = !q || r.company_name.toLowerCase().includes(q);
    if (!matchFilter || !matchPref || !matchSearch) return '<tr class="hidden"></tr>';
    shown++;

    const urlCell = r.url
      ? `<a href="${esc(r.url)}" target="_blank">${esc(r.url.replace(/^https?:\/\//,'').replace(/\/$/,'').slice(0,36))}</a>`
      : '<span style="color:#cbd5e1">―</span>';

    let statusBadge, titleCell;
    if (r.send_status === 'submitted') {
      statusBadge = `<span class="badge submitted">送信成功</span>`;
      titleCell   = `<span class="title-chip" title="${esc(msgTitle)}">${esc(msgTitle.slice(0,28))}${msgTitle.length>28?'…':''}</span>`;
    } else if (r.send_status === 'error') {
      statusBadge = `<span class="badge error">エラー</span>`;
      titleCell   = '―';
    } else if (r.send_status === 'skip') {
      statusBadge = `<span class="badge skip">スキップ</span>`;
      titleCell   = '―';
    } else if (r.url) {
      statusBadge = `<span class="badge not_sent">送信待ち</span>`;
      titleCell   = '―';
    } else {
      statusBadge = `<span class="badge no_url">URL未取得</span>`;
      titleCell   = '―';
    }

    let chkHtml;
    if (!r.url) {
      chkHtml = '<span class="chk-pending">―</span>';
    } else if (!r.check_status) {
      chkHtml = '<span class="chk-pending">未確認</span>';
    } else if (r.check_status.startsWith('ok')) {
      chkHtml = '<span class="chk-ok">✓ OK</span>';
    } else if (r.check_status === 'redirect') {
      const fl = r.final_url ? `<br><a href="${esc(r.final_url)}" target="_blank" style="font-size:11px">${esc(r.final_url.replace(/^https?:\/\//,'').slice(0,35))}</a>` : '';
      chkHtml = `<span class="chk-redirect">→ リダイレクト</span>${fl}`;
    } else {
      chkHtml = `<span class="chk-error">✗ ${esc(r.check_status)}</span>`;
    }

    return `<tr>
      <td style="color:#94a3b8;width:36px">${i+1}</td>
      <td style="font-weight:600">${esc(r.company_name)}</td>
      <td><span class="pref-tag">${esc(r.prefecture)}</span></td>
      <td>${urlCell}</td>
      <td>${chkHtml}</td>
      <td style="white-space:nowrap;color:#64748b;font-size:12px">${esc(r.submitted_at||'―')}</td>
      <td>${statusBadge}</td>
      <td>${titleCell}</td>
    </tr>`;
  }).join('');
  document.getElementById('count-label').textContent = `${shown.toLocaleString()}件表示`;
}

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>"""


def get_pipeline_data():
    companies_file = os.path.join(BASE, 'companies.csv')
    config_file = os.path.join(BASE, 'config.json')

    # メッセージタイトルをconfig.jsonから抽出（最初の「・」行）
    msg_title = 'SCOPE営業'
    try:
        with open(config_file, encoding='utf-8') as f:
            cfg = json.load(f)
        msg = cfg.get('message', '')
        # 最初の「・」行を抽出
        for line in msg.splitlines():
            line = line.strip()
            if line.startswith('・'):
                msg_title = line.lstrip('・').strip()
                break
    except Exception:
        pass

    if not os.path.exists(companies_file):
        return {'updated': datetime.now().strftime('%H:%M:%S'), 'title': msg_title,
                'stats': {}, 'rows': []}

    with open(companies_file, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))

    stats = {'submitted': 0, 'skip': 0, 'error': 0, 'manual_check': 0, 'pending': 0}
    result = []
    for r in rows:
        status = r.get('status', 'pending')
        stats[status] = stats.get(status, 0) + 1
        result.append({
            'company_name': r.get('company_name', ''),
            'url': r.get('url', ''),
            'contact_url': r.get('contact_url', ''),
            'status': status,
            'submitted_at': r.get('submitted_at', ''),
            'note': r.get('note', ''),
        })

    # 送信日時の新しい順にソート（pendingは末尾）
    def sort_key(r):
        return r['submitted_at'] if r['submitted_at'] else '0000'
    result.sort(key=sort_key, reverse=True)

    return {
        'updated': datetime.now().strftime('%H:%M:%S'),
        'title': msg_title,
        'stats': stats,
        'total': len(rows),
        'rows': result,
    }


PIPELINE_HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>フォーム営業 ダッシュボード</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', sans-serif; background: #f8fafc; color: #1e293b; font-size: 13px; }
.header { background: #1e293b; color: #f1f5f9; padding: 16px 24px; display: flex; align-items: center; justify-content: space-between; }
.header h1 { font-size: 18px; font-weight: 700; }
.header .nav a { color: #94a3b8; text-decoration: none; font-size: 12px; margin-left: 16px; }
.header .nav a:hover { color: #fff; }
.updated { font-size: 11px; color: #64748b; }

.summary { display: flex; gap: 12px; padding: 16px 24px; flex-wrap: wrap; }
.s-card { background: #fff; border-radius: 8px; padding: 12px 20px; min-width: 110px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,.08); border-top: 3px solid #e2e8f0; }
.s-card .num { font-size: 26px; font-weight: 800; }
.s-card .lbl { font-size: 11px; color: #94a3b8; margin-top: 2px; }
.s-card.submitted { border-color: #22c55e; } .s-card.submitted .num { color: #16a34a; }
.s-card.skip     { border-color: #f59e0b; } .s-card.skip .num     { color: #d97706; }
.s-card.error    { border-color: #ef4444; } .s-card.error .num    { color: #dc2626; }
.s-card.manual   { border-color: #6366f1; } .s-card.manual .num   { color: #4f46e5; }
.s-card.pending  { border-color: #94a3b8; } .s-card.pending .num  { color: #64748b; }

.toolbar { padding: 0 24px 12px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.filter-btn { border: 1.5px solid #cbd5e1; background: #fff; border-radius: 20px; padding: 4px 14px; cursor: pointer; font-size: 12px; color: #475569; transition: all .15s; }
.filter-btn:hover { background: #f1f5f9; }
.filter-btn.active { color: #fff; border-color: transparent; }
.filter-btn.active.all        { background: #1e293b; }
.filter-btn.active.submitted  { background: #16a34a; }
.filter-btn.active.skip       { background: #d97706; }
.filter-btn.active.error      { background: #dc2626; }
.filter-btn.active.manual     { background: #4f46e5; }
.filter-btn.active.pending    { background: #64748b; }
.search-box { padding: 5px 12px; border: 1.5px solid #e2e8f0; border-radius: 6px; font-size: 12px; width: 200px; outline: none; }
.search-box:focus { border-color: #6366f1; }
.count-label { margin-left: auto; font-size: 12px; color: #94a3b8; }

.table-wrap { padding: 0 24px 32px; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
th { background: #f1f5f9; padding: 9px 12px; text-align: left; font-size: 12px; color: #64748b; font-weight: 600; white-space: nowrap; }
td { padding: 8px 12px; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #fefce8; }
tr.hidden { display: none; }
a { color: #6366f1; text-decoration: none; font-size: 12px; }
a:hover { text-decoration: underline; }
.badge { display: inline-block; padding: 2px 9px; border-radius: 12px; font-size: 11px; font-weight: 600; color: #fff; white-space: nowrap; }
.badge.submitted { background: #16a34a; }
.badge.skip      { background: #d97706; }
.badge.error     { background: #dc2626; }
.badge.manual_check { background: #4f46e5; }
.badge.pending   { background: #94a3b8; }
.title-chip { background: #eff6ff; color: #2563eb; border-radius: 4px; padding: 2px 8px; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 220px; display: inline-block; }
</style>
</head>
<body>
<div class="header">
  <h1>フォーム営業 ダッシュボード</h1>
  <div class="nav">
    <a href="/">URL検索モニター</a>
  </div>
</div>

<div class="summary" id="summary"></div>

<div class="toolbar">
  <button class="filter-btn active all" onclick="setFilter('all',this)">すべて</button>
  <button class="filter-btn submitted" onclick="setFilter('submitted',this)">送信成功</button>
  <button class="filter-btn skip"      onclick="setFilter('skip',this)">スキップ</button>
  <button class="filter-btn error"     onclick="setFilter('error',this)">エラー</button>
  <button class="filter-btn manual"    onclick="setFilter('manual_check',this)">要確認</button>
  <button class="filter-btn pending"   onclick="setFilter('pending',this)">未送信</button>
  <input class="search-box" type="text" placeholder="会社名で検索..." oninput="applyFilter()">
  <span class="count-label" id="count-label"></span>
</div>

<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>#</th>
      <th>会社名</th>
      <th>サイトURL</th>
      <th>送信日時</th>
      <th>ステータス</th>
      <th>送付内容タイトル</th>
    </tr>
  </thead>
  <tbody id="tbody"></tbody>
</table>
</div>

<div style="text-align:center;padding:12px;font-size:11px;color:#94a3b8" id="footer-updated"></div>

<script>
let allRows = [];
let currentFilter = 'all';
let msgTitle = '';

async function refresh() {
  try {
    const r = await fetch('/pipeline/data');
    const d = await r.json();
    allRows = d.rows || [];
    msgTitle = d.title || 'SCOPE営業';

    // サマリーカード
    const s = d.stats || {};
    const total = d.total || 0;
    document.getElementById('summary').innerHTML = `
      <div class="s-card"><div class="num">${total}</div><div class="lbl">合計</div></div>
      <div class="s-card submitted"><div class="num">${s.submitted||0}</div><div class="lbl">送信成功</div></div>
      <div class="s-card skip"><div class="num">${s.skip||0}</div><div class="lbl">スキップ</div></div>
      <div class="s-card error"><div class="num">${s.error||0}</div><div class="lbl">エラー</div></div>
      <div class="s-card manual"><div class="num">${s.manual_check||0}</div><div class="lbl">要確認</div></div>
      <div class="s-card pending"><div class="num">${s.pending||0}</div><div class="lbl">未送信</div></div>
    `;
    document.getElementById('footer-updated').textContent = '最終更新: ' + d.updated + '  ／  5秒ごとに自動更新';
    applyFilter();
  } catch(e) {}
}

function setFilter(f, btn) {
  currentFilter = f;
  document.querySelectorAll('.filter-btn').forEach(b => {
    b.classList.remove('active','all','submitted','skip','error','manual','pending');
  });
  btn.classList.add('active', f === 'manual_check' ? 'manual' : f);
  applyFilter();
}

function applyFilter() {
  const q = document.querySelector('.search-box').value.trim().toLowerCase();
  const tbody = document.getElementById('tbody');
  let shown = 0;
  tbody.innerHTML = allRows.map((r, i) => {
    const show = (currentFilter === 'all' || r.status === currentFilter)
               && (!q || r.company_name.toLowerCase().includes(q));
    if (!show) return `<tr class="hidden"></tr>`;
    shown++;
    const sent = r.status !== 'pending' && r.submitted_at ? r.submitted_at : '―';
    const title = r.status === 'submitted'
      ? `<span class="title-chip" title="${esc(msgTitle)}">${esc(msgTitle.slice(0,30))}${msgTitle.length>30?'…':''}</span>`
      : '―';
    const urlCell = r.url
      ? `<a href="${esc(r.url)}" target="_blank">${esc(r.url.replace(/^https?:\/\//,'').replace(/\/$/,'').slice(0,35))}</a>`
      : '―';
    return `<tr>
      <td style="color:#94a3b8;width:36px">${i+1}</td>
      <td style="font-weight:600">${esc(r.company_name)}</td>
      <td>${urlCell}</td>
      <td style="white-space:nowrap;color:#64748b">${esc(sent)}</td>
      <td><span class="badge ${esc(r.status)}">${statusLabel(r.status)}</span></td>
      <td>${title}</td>
    </tr>`;
  }).join('');
  document.getElementById('count-label').textContent = `${shown}件表示`;
}

function statusLabel(s) {
  return {submitted:'送信成功', skip:'スキップ', error:'エラー', manual_check:'要確認', pending:'未送信'}[s] || s;
}
function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/data':
            data = json.dumps(get_stats(), ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(data)
        elif self.path == '/' or self.path == '/index.html':
            body = HTML.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(body)
        elif self.path == '/pipeline':
            body = PIPELINE_HTML.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(body)
        elif self.path == '/pipeline/data':
            data = json.dumps(get_pipeline_data(), ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(data)
        elif self.path == '/builders':
            body = BUILDERS_HTML.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(body)
        elif self.path == '/builders/data':
            data = json.dumps(get_builders_data(), ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass  # ログ出力を抑制

if __name__ == '__main__':
    port = 8765
    print(f'[モニター] http://localhost:{port} を開いてください')
    print(f'[モニター] Ctrl+C で停止')
    server = HTTPServer(('localhost', port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n停止しました')
