/**
 * send_list_preview.html または任意のCSVを companies.csv にインポートする
 *
 * 使い方:
 *   node import.js                        # send_list_preview.html から自動インポート
 *   node import.js --csv path/to/file.csv # CSVファイルからインポート
 */
const fs = require('fs');
const path = require('path');

const CSV_FILE = path.join(__dirname, 'companies.csv');
const HTML_FILE = path.join(__dirname, '..', 'send_list_preview.html'); // デスクトップ直下

// ===== HTMLパース =====
function parseHtml(filePath) {
  const html = fs.readFileSync(filePath, 'utf-8');
  const rows = [];
  // <tr><td>番号</td><td>会社名</td><td>所在地</td><td><a href="URL">...</a></td></tr>
  const rowRegex = /<tr><td>\d+<\/td><td>(.*?)<\/td><td>(.*?)<\/td><td><a href="(.*?)"[^>]*>/g;
  let match;
  while ((match = rowRegex.exec(html)) !== null) {
    const [, name, location, formUrl] = match;
    if (formUrl && formUrl.startsWith('http')) {
      rows.push({ name, location, formUrl });
    }
  }
  return rows;
}

// ===== CSVパース =====
function parseCsv(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  const lines = content.trim().split('\n');
  const headers = lines[0].split(',').map(h => h.trim());

  return lines.slice(1).map(line => {
    const values = line.split(',');
    const obj = {};
    headers.forEach((h, i) => obj[h] = (values[i] || '').trim());
    return obj;
  });
}

// ===== 既存URL読み込み =====
function loadExistingUrls() {
  if (!fs.existsSync(CSV_FILE)) return new Set();
  const content = fs.readFileSync(CSV_FILE, 'utf-8');
  const lines = content.trim().split('\n').slice(1);
  return new Set(lines.map(l => l.split(',')[0]).filter(Boolean));
}

// ===== companies.csv に書き込み =====
function initCsv() {
  if (!fs.existsSync(CSV_FILE)) {
    fs.writeFileSync(CSV_FILE, 'url,company_name,contact_url,status,submitted_at,note\n', 'utf-8');
  }
}

function appendCompany(url, name, contactUrl) {
  const line = `${url},${name},${contactUrl},pending,,\n`;
  fs.appendFileSync(CSV_FILE, line, 'utf-8');
}

function extractBaseUrl(url) {
  try {
    const parsed = new URL(url);
    return `${parsed.protocol}//${parsed.hostname}/`;
  } catch {
    return url;
  }
}

// ===== メイン =====
function main() {
  const args = process.argv.slice(2);
  const csvIndex = args.indexOf('--csv');
  const useHtml = csvIndex === -1;

  initCsv();
  const existingUrls = loadExistingUrls();
  let entries = [];

  if (useHtml) {
    // send_list_preview.html からインポート
    const htmlPath = path.join(__dirname, '..', 'send_list_preview.html');
    if (!fs.existsSync(htmlPath)) {
      console.error(`❌ ファイルが見つかりません: ${htmlPath}`);
      process.exit(1);
    }
    console.log(`📂 インポート元: ${htmlPath}`);
    const rows = parseHtml(htmlPath);
    entries = rows.map(r => ({
      url: extractBaseUrl(r.formUrl),
      name: r.name,
      contactUrl: r.formUrl,
    }));
  } else {
    // CSVからインポート
    const csvPath = args[csvIndex + 1];
    if (!csvPath || !fs.existsSync(csvPath)) {
      console.error(`❌ CSVファイルが見つかりません: ${csvPath}`);
      process.exit(1);
    }
    console.log(`📂 インポート元: ${csvPath}`);
    const rows = parseCsv(csvPath);

    // カラム名を自動検出
    const firstRow = rows[0] || {};
    const keys = Object.keys(firstRow);
    const urlKey = keys.find(k => /url|URL|リンク|アドレス/i.test(k) && !/baseconnect/i.test(k)) || keys[1];
    const nameKey = keys.find(k => /会社名|名前|name/i.test(k)) || keys[0];
    const formUrlKey = keys.find(k => /お問い合わせ|form|フォーム/i.test(k));

    console.log(`  会社名カラム: "${nameKey}"`);
    console.log(`  URLカラム: "${urlKey}"`);
    if (formUrlKey) console.log(`  フォームURLカラム: "${formUrlKey}"`);

    entries = rows.filter(r => r[urlKey]).map(r => ({
      url: extractBaseUrl(r[urlKey]),
      name: r[nameKey] || '',
      contactUrl: formUrlKey ? r[formUrlKey] || '' : '',
    }));
  }

  let added = 0;
  let skipped = 0;

  for (const { url, name, contactUrl } of entries) {
    if (!url || url === 'undefined') { skipped++; continue; }
    if (existingUrls.has(url)) {
      console.log(`  ⏭️  既存: ${name}`);
      skipped++;
      continue;
    }
    appendCompany(url, name, contactUrl);
    existingUrls.add(url);
    added++;
    console.log(`  ✅ 追加: ${name} → ${contactUrl || url}`);
  }

  console.log(`\n📊 完了: ${added}件追加 / ${skipped}件スキップ`);
  console.log(`📄 companies.csv に ${existingUrls.size}件 登録済み`);
}

main();
