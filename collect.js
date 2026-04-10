/**
 * Baseconnect から埼玉県内の企業HPを収集し companies.csv に追記する
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const CONFIG_FILE = path.join(__dirname, 'config.json');
const CSV_FILE = path.join(__dirname, 'companies.csv');

function loadConfig() {
  return JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
}

function loadExistingUrls() {
  if (!fs.existsSync(CSV_FILE)) return new Set();
  const content = fs.readFileSync(CSV_FILE, 'utf-8');
  const lines = content.trim().split('\n').slice(1); // ヘッダー除外
  return new Set(lines.map(l => l.split(',')[0]).filter(Boolean));
}

function saveCompany(url, companyName = '') {
  const line = `${url},${companyName},,,pending,,\n`;
  fs.appendFileSync(CSV_FILE, line, 'utf-8');
}

function isValidCompanyUrl(url, excludeDomains) {
  try {
    const parsed = new URL(url);
    const domain = parsed.hostname.toLowerCase();
    for (const excl of excludeDomains) {
      if (domain.includes(excl)) return false;
    }
    return url.startsWith('http');
  } catch {
    return false;
  }
}

function extractBaseUrl(url) {
  try {
    const parsed = new URL(url);
    return `${parsed.protocol}//${parsed.hostname}/`;
  } catch {
    return null;
  }
}

// Iタウンページ 埼玉県 業種別検索URL
const ITP_PAGES = [
  'https://itp.ne.jp/cgi-bin/srefer?ACT=search&prefcd=11&catcd=0401',  // 製造業
  'https://itp.ne.jp/cgi-bin/srefer?ACT=search&prefcd=11&catcd=0601',  // 建設業
  'https://itp.ne.jp/cgi-bin/srefer?ACT=search&prefcd=11&catcd=1001',  // 情報通信業
  'https://itp.ne.jp/cgi-bin/srefer?ACT=search&prefcd=11&catcd=0801',  // 不動産
  'https://itp.ne.jp/cgi-bin/srefer?ACT=search&prefcd=11&catcd=0501',  // 運輸・物流
  'https://itp.ne.jp/cgi-bin/srefer?ACT=search&prefcd=11&catcd=0701',  // 卸売・小売
  'https://itp.ne.jp/cgi-bin/srefer?ACT=search&prefcd=11&catcd=1101',  // サービス業
  'https://itp.ne.jp/cgi-bin/srefer?ACT=search&prefcd=11&catcd=0901',  // 飲食業
];

async function collectFromItp(page, listUrl, excludeDomains, existingUrls) {
  const collected = [];
  console.log(`  📂 ${listUrl}`);

  // 最大5ページ分巡回
  for (let p = 1; p <= 5; p++) {
    const url = p === 1 ? listUrl : `${listUrl}&page=${p}`;
    try {
      await page.goto(url, { timeout: 20000, waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(1500);

      // 企業名とHP URLを取得
      const entries = await page.evaluate(() => {
        const results = [];
        // 各企業ブロックを探す
        const items = document.querySelectorAll('.searchResult__item, .result-item, li[class*="result"]');
        items.forEach(item => {
          const nameEl = item.querySelector('h2, h3, .name, .company-name, strong');
          const name = nameEl ? nameEl.textContent.trim() : '';
          // HP URLを探す
          const links = Array.from(item.querySelectorAll('a[href]'));
          for (const a of links) {
            const href = a.href;
            if (
              href.startsWith('http') &&
              !href.includes('itp.ne.jp') &&
              !href.includes('google.com') &&
              !href.includes('facebook.com') &&
              !href.includes('twitter.com')
            ) {
              results.push({ url: href, name });
              break;
            }
          }
        });
        return results;
      });

      if (entries.length === 0) break; // これ以上ページなし

      for (const { url: hpUrl, name } of entries) {
        const base = extractBaseUrl(hpUrl);
        if (base && !existingUrls.has(base) && isValidCompanyUrl(base, excludeDomains)) {
          collected.push({ url: base, name });
        }
      }

      console.log(`    📄 ${p}ページ目: ${entries.length}件取得`);
    } catch (e) {
      console.log(`  ⚠️ エラー(p${p}): ${e.message.slice(0, 60)}`);
      break;
    }
  }

  return collected;
}

async function collect() {
  const config = loadConfig();
  const existingUrls = loadExistingUrls();
  const { exclude_domains } = config.search;

  // 既存データをリセット（musubu.inのゴミを削除）
  fs.writeFileSync(CSV_FILE, 'url,company_name,contact_url,status,submitted_at,note\n', 'utf-8');
  existingUrls.clear();

  let newCount = 0;

  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });
  const page = await context.newPage();

  for (const listUrl of ITP_PAGES) {
    const results = await collectFromItp(page, listUrl, exclude_domains, existingUrls);

    for (const { url, name } of results) {
      saveCompany(url, name);
      existingUrls.add(url);
      newCount++;
      console.log(`    ✅ 追加: ${url} (${name})`);
    }

    await page.waitForTimeout(2000);
  }

  await browser.close();
  console.log(`\n📊 収集完了: ${newCount}件追加 / 合計 ${existingUrls.size}件`);
}

collect().catch(console.error);
