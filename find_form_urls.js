/**
 * フォームURL探索スクリプト
 * companies.csv の pending 企業のHPを巡回し、contact_url（フォームページ）を探す
 * 送信は一切しない。contact_url を埋めるだけ。
 */

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const COMPANIES_CSV  = path.join(__dirname, 'companies.csv');
const URL_CHECK_CSV  = path.join(__dirname, 'url_check_results.csv');
const CONCURRENCY    = 5;   // 並列ブラウザ数
const PAGE_TIMEOUT   = 15000; // 1社あたり最大15秒
const SAVE_INTERVAL  = 20;    // 20社ごとにCSV保存

// ポータルサイト・不正URL パターン（これらは会社HPではないので除外）
const BAD_URL_PATTERNS = [
  'hugkumi-life.jp',
  '#:~:text=',
  'ckg.jp/',
  'google.com',
  'google.co.jp',
  'yahoo.co.jp',
  'facebook.com',
  'instagram.com',
  'twitter.com',
  'x.com',
  'linkedin.com',
  'youtube.com',
  'wikipedia.org',
  'townwork.net',
  'hellowork.mhlw.go.jp',
  'suumo.jp',
  'homes.co.jp',
  'athome.co.jp',
  'chintai.net',
  'lifull.com',
];

// フォームURL検索キーワード
const CONTACT_KEYWORDS = [
  'お問い合わせ', 'お問合せ', 'お問合わせ',
  'CONTACT', 'Contact', 'contact',
  'コンタクト', 'ご相談', 'ご連絡', 'ご質問',
  'inquiry', 'INQUIRY',
];

// ブラックリスト（採用・ニュースページ等）
const HUB_BLACKLIST = [
  '/recruit', '/recruitment', '/career', '/job',
  '/news/', '/press', '/support', '/ir/', '/investor',
  '/information/', '/product', '/event', '/pdf/',
];

// ===== CSV ユーティリティ =====

function parseCSVLine(line) {
  const cols = [];
  let cur = '', inQ = false;
  for (const c of line) {
    if (c === '"') inQ = !inQ;
    else if (c === ',' && !inQ) { cols.push(cur); cur = ''; }
    else cur += c;
  }
  cols.push(cur);
  return cols;
}

function loadCompanies() {
  const content = fs.readFileSync(COMPANIES_CSV, 'utf-8');
  const lines = content.trim().split('\n');
  const headers = parseCSVLine(lines[0]);
  return lines.slice(1).map(line => {
    const vals = parseCSVLine(line);
    const obj = {};
    headers.forEach((h, i) => obj[h.trim()] = (vals[i] || '').trim());
    return obj;
  });
}

function saveCompanies(companies) {
  const headers = ['url', 'company_name', 'contact_url', 'status', 'submitted_at', 'note'];
  const lines = [headers.join(',')];
  for (const c of companies) {
    lines.push(headers.map(h => (c[h] || '').replace(/,/g, '；')).join(','));
  }
  fs.writeFileSync(COMPANIES_CSV, lines.join('\n') + '\n', 'utf-8');
}

function loadUrlCheckResults() {
  // company_name → final_url (status が ok/redirect/ok(ssl-warn) のもの)
  const map = {};
  if (!fs.existsSync(URL_CHECK_CSV)) return map;
  const content = fs.readFileSync(URL_CHECK_CSV, 'utf-8');
  const lines = content.trim().split('\n');
  lines.slice(1).forEach(line => {
    const cols = parseCSVLine(line);
    // company_id,company_name,prefecture,url,status,final_url,note,checked_at
    const name   = (cols[1] || '').trim();
    const status = (cols[4] || '').trim();
    const finalUrl = (cols[5] || '').trim();
    if (name && finalUrl && finalUrl.startsWith('http') &&
        (status === 'ok' || status === 'redirect' || status === 'ok(ssl-warn)')) {
      map[name] = finalUrl;
    }
  });
  return map;
}

// ===== URL チェック =====

function isBadUrl(url) {
  if (!url || !url.startsWith('http')) return true;
  return BAD_URL_PATTERNS.some(p => url.includes(p));
}

function isBlacklisted(url) {
  const lower = url.toLowerCase();
  return HUB_BLACKLIST.some(p => lower.includes(p));
}

// ===== Playwright: フォームURL探索 =====

async function findContactUrl(page, baseUrl) {
  // 1. テキストリンクから探す
  for (const keyword of CONTACT_KEYWORDS) {
    try {
      const links = page.locator(`a:has-text('${keyword}')`);
      const count = await links.count();
      for (let i = 0; i < count; i++) {
        const href = await links.nth(i).getAttribute('href').catch(() => null);
        if (!href || href.startsWith('tel:') || href.startsWith('mailto:')) continue;
        try {
          const full = new URL(href, baseUrl).href;
          if (!isBlacklisted(full)) return full;
        } catch { continue; }
      }
    } catch { continue; }
  }

  // 2. href属性にキーワードを含むリンクから探す
  try {
    const linkEls = page.locator('a[href*="contact"], a[href*="inquiry"], a[href*="form"], a[href*="toiawase"]');
    const count = await linkEls.count();
    for (let i = 0; i < count; i++) {
      const href = await linkEls.nth(i).getAttribute('href').catch(() => null);
      if (!href || href.includes('#')) continue;
      try {
        const full = new URL(href, baseUrl).href;
        if (full !== baseUrl && !isBlacklisted(full)) return full;
      } catch { continue; }
    }
  } catch { }

  return null;
}

async function processCompany(browser, company, verifiedUrlMap) {
  // URL の決定（url_check_results から verified URL を優先）
  let targetUrl = verifiedUrlMap[company.company_name] || company.url;

  if (isBadUrl(targetUrl)) {
    return { contactUrl: null, note: 'bad_url: ' + (targetUrl || '').substring(0, 60) };
  }

  // URLをオリジン（ドメインのトップ）に正規化（パスが長すぎる場合）
  try {
    const u = new URL(targetUrl);
    if (u.pathname.length > 50 || u.search.length > 0) {
      targetUrl = u.origin + '/';
    }
  } catch {
    return { contactUrl: null, note: 'invalid_url' };
  }

  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();

  try {
    await page.goto(targetUrl, { timeout: PAGE_TIMEOUT, waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1000);

    const contactUrl = await findContactUrl(page, targetUrl);
    return { contactUrl, note: contactUrl ? '' : 'contact_link_not_found' };
  } catch (e) {
    const msg = (e.message || '').substring(0, 80);
    return { contactUrl: null, note: 'error: ' + msg };
  } finally {
    await context.close().catch(() => {});
  }
}

// ===== メイン =====

async function main() {
  console.log('=== フォームURL探索スクリプト ===');
  console.log(`並列数: ${CONCURRENCY} | タイムアウト: ${PAGE_TIMEOUT}ms\n`);

  const companies = loadCompanies();
  const verifiedUrlMap = loadUrlCheckResults();
  console.log(`url_check_results: ${Object.keys(verifiedUrlMap).length}社のURLをロード`);

  // pending かつ contact_url が空のものだけ対象
  const targets = companies.filter(c => c.status === 'pending' && !c.contact_url);
  console.log(`対象: ${targets.length}社（pending & contact_url未設定）\n`);

  if (targets.length === 0) {
    console.log('対象なし。終了します。');
    return;
  }

  let done = 0, found = 0, notFound = 0, badUrl = 0;
  const startTime = Date.now();

  const browser = await chromium.launch({ headless: true });

  // セマフォ（並列制御）
  const queue = [...targets];
  let running = 0;
  let saveCounter = 0;

  async function runNext() {
    if (queue.length === 0) return;
    const company = queue.shift();
    running++;

    const result = await processCompany(browser, company, verifiedUrlMap);

    // companies配列の対応する行を更新
    const idx = companies.findIndex(c => c.url === company.url && c.company_name === company.company_name);
    if (idx >= 0) {
      if (result.contactUrl) {
        companies[idx].contact_url = result.contactUrl;
        found++;
      } else {
        companies[idx].note = result.note;
        if (result.note && result.note.startsWith('bad_url')) badUrl++;
        else notFound++;
      }
    }

    done++;
    saveCounter++;

    const elapsed = Math.round((Date.now() - startTime) / 1000);
    const rate = done / elapsed;
    const remaining = Math.round((targets.length - done) / rate);
    process.stdout.write(
      `\r[${done}/${targets.length}] 発見:${found} 未発見:${notFound} 不正URL:${badUrl} | ` +
      `経過:${elapsed}s 残り約${remaining}s  `
    );

    // 定期保存
    if (saveCounter >= SAVE_INTERVAL) {
      saveCompanies(companies);
      saveCounter = 0;
    }

    running--;
    await runNext();
  }

  // CONCURRENCY 分だけ並列起動
  const workers = [];
  for (let i = 0; i < Math.min(CONCURRENCY, targets.length); i++) {
    workers.push(runNext());
  }
  await Promise.all(workers);

  // 最終保存
  saveCompanies(companies);
  await browser.close();

  const elapsed = Math.round((Date.now() - startTime) / 1000);
  console.log('\n\n=== 完了 ===');
  console.log(`処理: ${done}社 / 所要時間: ${elapsed}秒`);
  console.log(`フォームURL発見: ${found}社`);
  console.log(`リンク未発見:    ${notFound}社`);
  console.log(`不正URL:         ${badUrl}社`);
  console.log(`\ncompanies.csv を更新しました`);
}

main().catch(err => {
  console.error('\nFatal error:', err);
  process.exit(1);
});
