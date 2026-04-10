#!/usr/bin/env python3
"""送信ダッシュボードHTML生成スクリプト（埼玉工務店版）"""
import csv
import json
import os
from datetime import datetime
from collections import Counter

CSV_PATH = "../form-automation-saitama/companies.csv"
STAGING_PATH = "../form-automation-saitama/saitama_staging.csv"
OUTPUT_PATH = "docs/index.html"

def load_phone_map():
    """staging CSVからURL→電話番号のマップを作成"""
    phone_map = {}
    if not os.path.exists(STAGING_PATH):
        return phone_map
    with open(STAGING_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            url = (r.get("url") or "").strip().rstrip("/")
            phone = (r.get("phone") or "").strip()
            if url and phone:
                phone_map[url] = phone
    return phone_map

def load_companies():
    phone_map = load_phone_map()
    rows = []
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            url = (r.get("url") or "").strip().rstrip("/")
            r["phone"] = phone_map.get(url, "")
            rows.append(r)
    return rows

def generate_html(rows):
    counts = Counter(r["status"] for r in rows)
    total = len(rows)
    submitted = counts.get("submitted", 0)
    pending = counts.get("pending", 0)
    error = counts.get("error", 0)
    manual_check = counts.get("manual_check", 0)
    no_form = counts.get("no_form", 0)
    skip = counts.get("skip", 0)

    status_colors = {
        "submitted": "#10b981",
        "pending": "#f59e0b",
        "error": "#ef4444",
        "manual_check": "#8b5cf6",
        "no_form": "#6b7280",
        "skip": "#d1d5db",
        "": "#d1d5db",
    }
    status_labels = {
        "submitted": "送信済み",
        "pending": "送信待ち",
        "error": "エラー",
        "manual_check": "要確認",
        "no_form": "フォームなし",
        "skip": "スキップ",
        "": "未分類",
    }

    rows_json = json.dumps([
        {
            "no": i + 1,
            "company": r.get("company_name", ""),
            "url": r.get("url", ""),
            "contact_url": r.get("contact_url", ""),
            "status": r.get("status", ""),
            "submitted_at": r.get("submitted_at", ""),
            "note": r.get("note", "") or "",
            "phone": r.get("phone", "") or "",
        }
        for i, r in enumerate(rows)
    ], ensure_ascii=False)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>埼玉県 企業 フォーム営業ダッシュボード｜SINMIDO</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background: #f1f5f9; color: #1e293b; }}
  header {{ background: #0f172a; color: #fff; padding: 20px 30px; }}
  header h1 {{ font-size: 1.3rem; font-weight: 700; }}
  header p {{ font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 24px 20px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; margin-bottom: 24px; }}
  .card {{ background: #fff; border-radius: 10px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .card .label {{ font-size: 0.75rem; color: #64748b; margin-bottom: 6px; }}
  .card .value {{ font-size: 1.8rem; font-weight: 700; }}
  .card.submitted .value {{ color: #10b981; }}
  .card.pending .value {{ color: #f59e0b; }}
  .card.error .value {{ color: #ef4444; }}
  .card.manual .value {{ color: #8b5cf6; }}
  .card.total .value {{ color: #0f172a; }}
  .controls {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; align-items: center; }}
  .controls input {{ flex: 1; min-width: 200px; padding: 9px 14px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 0.9rem; }}
  .controls select {{ padding: 9px 14px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 0.9rem; background: #fff; }}
  .count-info {{ font-size: 0.85rem; color: #64748b; }}
  table {{ width: 100%; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border-collapse: collapse; }}
  th {{ background: #0f172a; color: #fff; padding: 11px 14px; text-align: left; font-size: 0.8rem; font-weight: 600; white-space: nowrap; cursor: pointer; user-select: none; }}
  th:hover {{ background: #1e293b; }}
  td {{ padding: 10px 14px; font-size: 0.82rem; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f8fafc; }}
  .badge {{ display: inline-block; padding: 3px 9px; border-radius: 20px; font-size: 0.73rem; font-weight: 600; color: #fff; }}
  .badge-submitted {{ background: #10b981; }}
  .badge-pending {{ background: #f59e0b; }}
  .badge-error {{ background: #ef4444; }}
  .badge-manual_check {{ background: #8b5cf6; }}
  .badge-no_form {{ background: #6b7280; }}
  .badge-skip {{ background: #cbd5e1; color: #475569; }}
  .badge- {{ background: #e2e8f0; color: #64748b; }}
  a {{ color: #3b82f6; text-decoration: none; word-break: break-all; }}
  a:hover {{ text-decoration: underline; }}
  .company-name {{ font-weight: 600; max-width: 180px; }}
  .url-cell {{ max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .note-cell {{ max-width: 160px; color: #64748b; font-size: 0.78rem; }}
  .pagination {{ display: flex; gap: 6px; justify-content: center; margin-top: 18px; flex-wrap: wrap; }}
  .pagination button {{ padding: 6px 12px; border: 1px solid #e2e8f0; background: #fff; border-radius: 6px; cursor: pointer; font-size: 0.82rem; }}
  .pagination button.active {{ background: #0f172a; color: #fff; border-color: #0f172a; }}
  .pagination button:hover:not(.active) {{ background: #f1f5f9; }}
</style>
</head>
<body>
<header>
  <h1>埼玉県 企業 フォーム営業ダッシュボード｜株式会社シンミドウ</h1>
  <p>最終更新: {now} &nbsp;｜&nbsp; 対象: 埼玉県内 各種企業（{total:,}社）</p>
</header>
<div class="container">
  <div class="cards">
    <div class="card total"><div class="label">総件数</div><div class="value">{total:,}</div></div>
    <div class="card submitted"><div class="label">送信済み</div><div class="value">{submitted:,}</div></div>
    <div class="card pending"><div class="label">送信待ち</div><div class="value">{pending:,}</div></div>
    <div class="card error"><div class="label">エラー</div><div class="value">{error:,}</div></div>
    <div class="card manual"><div class="label">要確認</div><div class="value">{manual_check:,}</div></div>
    <div class="card total"><div class="label">フォームなし</div><div class="value">{no_form:,}</div></div>
  </div>

  <div class="controls">
    <input type="text" id="searchInput" placeholder="会社名・URL・ノートで検索..." oninput="filterAndRender()">
    <select id="statusFilter" onchange="filterAndRender()">
      <option value="">すべてのステータス</option>
      <option value="submitted">送信済み</option>
      <option value="pending">送信待ち</option>
      <option value="error">エラー</option>
      <option value="manual_check">要確認</option>
      <option value="no_form">フォームなし</option>
      <option value="skip">スキップ</option>
    </select>
    <span class="count-info" id="countInfo"></span>
  </div>

  <table>
    <thead>
      <tr>
        <th onclick="sortBy('no')">#</th>
        <th onclick="sortBy('company')">会社名</th>
        <th onclick="sortBy('status')">ステータス</th>
        <th>電話番号</th>
        <th>URL</th>
        <th>フォームURL</th>
        <th onclick="sortBy('submitted_at')">送信日時</th>
        <th>ノート</th>
      </tr>
    </thead>
    <tbody id="tableBody"></tbody>
  </table>
  <div class="pagination" id="pagination"></div>
</div>

<script>
const ALL_DATA = {rows_json};

const STATUS_LABEL = {{
  submitted: "送信済み", pending: "送信待ち", error: "エラー",
  manual_check: "要確認", no_form: "フォームなし", skip: "スキップ", "": "未分類"
}};

let filtered = [...ALL_DATA];
let sortKey = "no";
let sortAsc = true;
let currentPage = 1;
const PAGE_SIZE = 100;

function filterAndRender() {{
  const q = document.getElementById("searchInput").value.toLowerCase();
  const st = document.getElementById("statusFilter").value;
  filtered = ALL_DATA.filter(r => {{
    const matchStatus = !st || r.status === st;
    const matchQ = !q || (r.company + r.url + r.note + r.contact_url + r.phone).toLowerCase().includes(q);
    return matchStatus && matchQ;
  }});
  currentPage = 1;
  render();
}}

function sortBy(key) {{
  if (sortKey === key) sortAsc = !sortAsc;
  else {{ sortKey = key; sortAsc = true; }}
  render();
}}

function render() {{
  filtered.sort((a, b) => {{
    const av = a[sortKey] || "";
    const bv = b[sortKey] || "";
    if (sortKey === "no") return sortAsc ? (a.no - b.no) : (b.no - a.no);
    return sortAsc ? av.localeCompare(bv, "ja") : bv.localeCompare(av, "ja");
  }});

  const total = filtered.length;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (currentPage > pages) currentPage = pages;
  const start = (currentPage - 1) * PAGE_SIZE;
  const slice = filtered.slice(start, start + PAGE_SIZE);

  document.getElementById("countInfo").textContent =
    `${{total.toLocaleString()}}件 / 全${{ALL_DATA.length.toLocaleString()}}件`;

  const tbody = document.getElementById("tableBody");
  tbody.innerHTML = slice.map(r => `
    <tr>
      <td>${{r.no}}</td>
      <td class="company-name">${{esc(r.company)}}</td>
      <td><span class="badge badge-${{r.status}}">${{STATUS_LABEL[r.status] || r.status}}</span></td>
      <td style="white-space:nowrap;color:#334155">${{esc(r.phone)}}</td>
      <td class="url-cell">${{r.url ? `<a href="${{r.url}}" target="_blank" rel="noopener">${{esc(r.url)}}</a>` : ""}}</td>
      <td class="url-cell">${{r.contact_url ? `<a href="${{r.contact_url}}" target="_blank" rel="noopener">${{esc(r.contact_url)}}</a>` : ""}}</td>
      <td>${{esc(r.submitted_at)}}</td>
      <td class="note-cell">${{esc(r.note)}}</td>
    </tr>
  `).join("");

  // ページネーション
  const pag = document.getElementById("pagination");
  let btns = "";
  const maxBtns = 10;
  let lo = Math.max(1, currentPage - Math.floor(maxBtns/2));
  let hi = Math.min(pages, lo + maxBtns - 1);
  if (hi - lo < maxBtns - 1) lo = Math.max(1, hi - maxBtns + 1);
  if (lo > 1) btns += `<button onclick="goPage(1)">1</button><button disabled>...</button>`;
  for (let i = lo; i <= hi; i++) {{
    btns += `<button class="${{i===currentPage?'active':''}}" onclick="goPage(${{i}})">${{i}}</button>`;
  }}
  if (hi < pages) btns += `<button disabled>...</button><button onclick="goPage(${{pages}})">${{pages}}</button>`;
  pag.innerHTML = btns;
}}

function goPage(p) {{ currentPage = p; render(); window.scrollTo(0,0); }}
function esc(s) {{
  if (!s) return "";
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}}

filterAndRender();
</script>
</body>
</html>
"""
    return html

if __name__ == "__main__":
    import os
    os.makedirs("docs", exist_ok=True)
    rows = load_companies()
    html = generate_html(rows)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"生成完了: {OUTPUT_PATH} ({len(rows)}社)")
