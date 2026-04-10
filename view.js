/**
 * companies.csv を読み込んでブラウザで確認できるHTMLを生成して開く
 * 使い方: node view.js
 */
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');

const CSV_FILE = path.join(__dirname, 'companies.csv');
const OUT_FILE = path.join(__dirname, 'dashboard.html');

const STATUS_LABEL = {
  pending:      { label: '未送信',   color: '#6c757d' },
  submitted:    { label: '送信済み', color: '#198754' },
  no_form:      { label: 'フォームなし', color: '#fd7e14' },
  manual_check: { label: '要確認',   color: '#0dcaf0' },
  error:        { label: 'エラー',   color: '#dc3545' },
};

function loadCsv() {
  if (!fs.existsSync(CSV_FILE)) return [];
  const content = fs.readFileSync(CSV_FILE, 'utf-8');
  const lines = content.trim().split('\n');
  const headers = lines[0].split(',').map(h => h.trim());
  return lines.slice(1).filter(l => l.trim()).map(line => {
    const values = line.split(',');
    const obj = {};
    headers.forEach((h, i) => obj[h] = (values[i] || '').trim());
    return obj;
  });
}

function buildHtml(companies) {
  const total = companies.length;
  const counts = {};
  for (const s of Object.keys(STATUS_LABEL)) counts[s] = 0;
  companies.forEach(c => { if (counts[c.status] !== undefined) counts[c.status]++; });

  const csvData = encodeURIComponent(
    'url,company_name,contact_url,status,submitted_at,note\n' +
    companies.map(c =>
      `${c.url},${c.company_name},${c.contact_url},${c.status},${c.submitted_at},${c.note}`
    ).join('\n')
  );

  const rows = companies.map((c, i) => {
    const s = STATUS_LABEL[c.status] || { label: c.status, color: '#aaa' };
    return `
    <tr data-status="${c.status}">
      <td>${i + 1}</td>
      <td>${c.company_name || '-'}</td>
      <td><a href="${c.contact_url || c.url}" target="_blank">${c.contact_url || c.url}</a></td>
      <td><span class="badge" style="background:${s.color}">${s.label}</span></td>
      <td>${c.submitted_at || '-'}</td>
      <td style="font-size:11px;color:#888">${c.note || ''}</td>
    </tr>`;
  }).join('');

  const filterButtons = Object.entries(STATUS_LABEL).map(([key, { label, color }]) =>
    `<button class="filter-btn" onclick="filterStatus('${key}')" style="border-color:${color};color:${color}">
      ${label} <span class="cnt">${counts[key]}</span>
    </button>`
  ).join('');

  return `<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>営業パイプライン ダッシュボード</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', sans-serif; font-size: 13px; background: #f8f9fa; color: #333; }
  .header { background: #1a1a2e; color: #fff; padding: 16px 24px; display: flex; align-items: center; justify-content: space-between; }
  .header h1 { font-size: 18px; font-weight: 600; }
  .header .meta { font-size: 12px; color: #aaa; }
  .stats { display: flex; gap: 12px; padding: 16px 24px; flex-wrap: wrap; }
  .stat-card { background: #fff; border-radius: 8px; padding: 12px 20px; min-width: 120px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
  .stat-card .num { font-size: 28px; font-weight: 700; }
  .stat-card .lbl { font-size: 11px; color: #888; margin-top: 2px; }
  .toolbar { display: flex; gap: 8px; align-items: center; padding: 0 24px 12px; flex-wrap: wrap; }
  .filter-btn { border: 1.5px solid; background: #fff; border-radius: 20px; padding: 4px 14px; cursor: pointer; font-size: 12px; transition: all .15s; }
  .filter-btn:hover, .filter-btn.active { color: #fff !important; }
  .filter-btn.active[onclick*="pending"]      { background: #6c757d; }
  .filter-btn.active[onclick*="submitted"]    { background: #198754; }
  .filter-btn.active[onclick*="no_form"]      { background: #fd7e14; }
  .filter-btn.active[onclick*="manual_check"] { background: #0dcaf0; }
  .filter-btn.active[onclick*="error"]        { background: #dc3545; }
  .btn-all { border: 1.5px solid #333; background: #fff; border-radius: 20px; padding: 4px 14px; cursor: pointer; font-size: 12px; }
  .btn-csv { margin-left: auto; background: #0d6efd; color: #fff; border: none; border-radius: 6px; padding: 6px 16px; cursor: pointer; font-size: 12px; }
  .search-box { padding: 5px 12px; border: 1.5px solid #ddd; border-radius: 6px; font-size: 12px; width: 200px; }
  .table-wrap { padding: 0 24px 24px; }
  table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
  th { background: #f0f0f0; padding: 10px 12px; text-align: left; font-size: 12px; color: #555; position: sticky; top: 0; }
  td { padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }
  tr:hover td { background: #fffbe6; }
  tr.hidden { display: none; }
  a { color: #1a73e8; text-decoration: none; font-size: 12px; }
  a:hover { text-decoration: underline; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; color: #fff; font-size: 11px; }
  .cnt { font-weight: 700; }
  .summary { padding: 4px 24px 8px; font-size: 12px; color: #888; }
</style>
</head>
<body>
<div class="header">
  <h1>📊 営業パイプライン ダッシュボード</h1>
  <div class="meta">最終更新: ${new Date().toLocaleString('ja-JP')} ／ 合計 ${total}社</div>
</div>

<div class="stats">
  <div class="stat-card"><div class="num">${total}</div><div class="lbl">合計</div></div>
  <div class="stat-card" style="border-top:3px solid #198754"><div class="num" style="color:#198754">${counts.submitted}</div><div class="lbl">送信済み</div></div>
  <div class="stat-card" style="border-top:3px solid #6c757d"><div class="num" style="color:#6c757d">${counts.pending}</div><div class="lbl">未送信</div></div>
  <div class="stat-card" style="border-top:3px solid #dc3545"><div class="num" style="color:#dc3545">${counts.error}</div><div class="lbl">エラー</div></div>
  <div class="stat-card" style="border-top:3px solid #fd7e14"><div class="num" style="color:#fd7e14">${counts.no_form}</div><div class="lbl">フォームなし</div></div>
</div>

<div class="toolbar">
  <button class="btn-all" onclick="filterStatus('all')">すべて</button>
  ${filterButtons}
  <input class="search-box" type="text" placeholder="会社名で検索..." oninput="searchCompany(this.value)">
  <a href="data:text/csv;charset=utf-8,${csvData}" download="companies_${Date.now()}.csv">
    <button class="btn-csv">⬇ CSVダウンロード</button>
  </a>
</div>
<div class="summary" id="summary">${total}件表示中</div>

<div class="table-wrap">
<table id="mainTable">
  <thead>
    <tr>
      <th>#</th><th>会社名</th><th>フォームURL</th><th>ステータス</th><th>送信日時</th><th>備考</th>
    </tr>
  </thead>
  <tbody>${rows}</tbody>
</table>
</div>

<script>
let currentStatus = 'all';
let currentSearch = '';

function filterStatus(status) {
  currentStatus = status;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  if (status !== 'all') {
    const btn = document.querySelector(\`.filter-btn[onclick*="\${status}"]\`);
    if (btn) btn.classList.add('active');
  }
  applyFilter();
}

function searchCompany(query) {
  currentSearch = query.toLowerCase();
  applyFilter();
}

function applyFilter() {
  const rows = document.querySelectorAll('#mainTable tbody tr');
  let visible = 0;
  rows.forEach(row => {
    const statusMatch = currentStatus === 'all' || row.dataset.status === currentStatus;
    const searchMatch = !currentSearch || row.textContent.toLowerCase().includes(currentSearch);
    if (statusMatch && searchMatch) { row.classList.remove('hidden'); visible++; }
    else row.classList.add('hidden');
  });
  document.getElementById('summary').textContent = \`\${visible}件表示中\`;
}
</script>
</body>
</html>`;
}

const companies = loadCsv();
const html = buildHtml(companies);
fs.writeFileSync(OUT_FILE, html, 'utf-8');
console.log(`✅ ダッシュボード生成: ${OUT_FILE}`);
// exec(`start "" "${OUT_FILE}"`); // 自動起動無効化
