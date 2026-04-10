/**
 * merge_saitama.js
 * saitama_raw.csv を companies.csv にマージ（重複除外）
 *
 * 使い方: node merge_saitama.js
 */

const fs = require('fs');
const path = require('path');

const RAW_FILE      = path.join(__dirname, 'saitama_raw.csv');
const COMPANIES_FILE = path.join(__dirname, 'companies.csv');

function normalizeUrl(url) {
  try {
    const u = new URL(url.trim());
    return u.hostname.toLowerCase().replace(/^www\./, '');
  } catch { return url.toLowerCase().trim(); }
}

function getFirstCol(line) {
  // クォート対応でurlカラムを取得
  const m = line.match(/^"([^"]+)"|^([^,]+)/);
  return m ? (m[1] || m[2] || '').trim() : '';
}

function main() {
  if (!fs.existsSync(RAW_FILE)) {
    console.log('❌ saitama_raw.csv が見つかりません。先に node collect_saitama.js を実行してください。');
    process.exit(1);
  }

  const rawLines   = fs.readFileSync(RAW_FILE, 'utf8').split('\n');
  const compLines  = fs.readFileSync(COMPANIES_FILE, 'utf8').split('\n');

  const rawRows  = rawLines.slice(1).filter(l => l.trim());
  const compRows = compLines.slice(1).filter(l => l.trim());

  // 既存URLのセット
  const existingUrls = new Set();
  for (const row of compRows) {
    const url = getFirstCol(row);
    if (url) existingUrls.add(normalizeUrl(url));
  }

  const toAdd = [];
  let skipped = 0;

  for (const row of rawRows) {
    const url = getFirstCol(row);
    if (!url) continue;
    const norm = normalizeUrl(url);
    if (existingUrls.has(norm)) {
      skipped++;
      continue;
    }
    existingUrls.add(norm);
    toAdd.push(row);
  }

  if (toAdd.length === 0) {
    console.log(`マージ対象なし（重複スキップ: ${skipped}件）`);
    return;
  }

  // companies.csv に追記
  fs.appendFileSync(COMPANIES_FILE, toAdd.join('\n') + '\n', 'utf8');

  const total = compRows.length + toAdd.length;
  console.log('========================================');
  console.log('  マージ完了');
  console.log(`  追加        : ${toAdd.length}件`);
  console.log(`  重複スキップ: ${skipped}件`);
  console.log(`  companies.csv 合計: ${total}件`);
  console.log('========================================');
}

main();
