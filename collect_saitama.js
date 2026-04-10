/**
 * collect_saitama.js
 * 埼玉県 企業一括収集（目標: 5000社）
 *
 * Phase 1: Iタウンページ（全業種 × 最大50ページ）
 * Phase 2: DuckDuckGo検索（63市区町村 × 業種キーワード）
 * Phase 3: Googleマップ（主要市 × キーワード）
 *
 * 使い方:
 *   node collect_saitama.js           # 全フェーズ
 *   node collect_saitama.js --phase=1 # ITのみ
 *   node collect_saitama.js --phase=2 # DDGのみ
 *   node collect_saitama.js --phase=3 # Mapsのみ
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

// ===== 設定 =====
const RAW_FILE      = path.join(__dirname, 'saitama_raw.csv');
const COMPANIES_FILE = path.join(__dirname, 'companies.csv');
const PROGRESS_FILE  = path.join(__dirname, 'saitama_progress.json');

const DELAY_BASE   = 2000;
const MAX_ITP_PAGES = 50;

const EXCLUDE_DOMAINS = [
  'suumo.jp','homes.co.jp','chintai.net','athome.co.jp',
  'mynavi.jp','indeed.com','linkedin.com','facebook.com',
  'twitter.com','instagram.com','youtube.com','wikipedia.org',
  'google.com','google.co.jp','amazon.co.jp','rakuten.co.jp',
  'itp.ne.jp','townpage.jp','benrimap.com','mapion.co.jp',
  'ekiten.jp','hotpepper.jp','tabelog.com','jalan.net',
  'recruit.co.jp','doda.jp','rikunabi.com','townwork.net',
  'nikkei.com','.go.jp','city.','town.','village.',
  'kakaku.com','price.com','houzz.jp','reform-online.jp',
  'hellowork','wordpress.com','wix.com','jimdo.com',
  'ameblo.jp','note.com','cookpad.com','yahoo.co.jp',
  'tiktok.com','line.me','gnavi.co.jp','retty.me',
  'pref.saitama','microsoft.com','apple.com','adobe.com',
  'appstore.com','play.google','housing.co.jp',
  'homes.ne.jp','ieul.jp','sumai-entry.com','lifull.com',
];

// 埼玉県 全市区町村
const SAITAMA_CITIES = [
  'さいたま市','川口市','越谷市','所沢市','春日部市',
  '草加市','熊谷市','上尾市','川越市','入間市',
  '新座市','久喜市','深谷市','飯能市','加須市',
  '富士見市','三郷市','坂戸市','鴻巣市','狭山市',
  '北本市','行田市','秩父市','蕨市','戸田市',
  '朝霞市','志木市','和光市','吉川市','ふじみ野市',
  '白岡市','八潮市','伊奈町','三芳町','毛呂山町',
  '越生町','滑川町','嵐山町','小川町','川島町',
  '吉見町','鳩山町','ときがわ町','横瀬町','皆野町',
  '長瀞町','小鹿野町','東秩父村','美里町','神川町',
  '上里町','寄居町','宮代町','杉戸町','松伏町',
];

// DuckDuckGo 業種キーワード
const DDG_KEYWORDS = [
  '工務店','建設','設計事務所','リフォーム','不動産',
  '製造','運送','電気工事','設備工事','塗装',
  'IT','システム開発','医院','クリニック','歯科',
  '保育園','介護','ホテル','美容室','学習塾',
  '税理士','社労士','印刷','広告','食品',
];

// Google Maps キーワード
const MAPS_KEYWORDS = [
  '会社','工務店','建設','不動産','クリニック',
  '設計','リフォーム','製造','ITシステム','介護',
];

// Googleマップ対象（主要市のみ）
const MAPS_CITIES = [
  'さいたま市','川口市','越谷市','所沢市','春日部市',
  '草加市','熊谷市','上尾市','川越市','入間市',
  '新座市','久喜市','深谷市','蕨市','戸田市',
  '朝霞市','志木市','和光市','富士見市','三郷市',
];

// Iタウンページ カテゴリ（prefcd=11 = 埼玉県）
const ITP_CATEGORIES = [
  { cd: '0601', name: '建設業' },
  { cd: '0401', name: '製造業' },
  { cd: '1001', name: '情報通信業' },
  { cd: '0801', name: '不動産' },
  { cd: '0501', name: '運輸・物流' },
  { cd: '0701', name: '卸売・小売' },
  { cd: '1101', name: 'サービス業' },
  { cd: '0901', name: '飲食・宿泊' },
  { cd: '1201', name: '医療・福祉' },
  { cd: '1301', name: '教育・学習' },
  { cd: '1401', name: '金融・保険' },
  { cd: '1501', name: '生活関連' },
  { cd: '1601', name: '娯楽' },
  { cd: '0201', name: '農林漁業' },
  { cd: '1701', name: 'その他' },
];

// ===== ユーティリティ =====

function csvEscape(s) {
  if (!s) return '';
  s = String(s).replace(/[\r\n]+/g, ' ').trim();
  if (s.includes(',') || s.includes('"')) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

function normalizeUrl(url) {
  try {
    const u = new URL(url.trim());
    return u.hostname.toLowerCase().replace(/^www\./, '');
  } catch { return url.toLowerCase().trim(); }
}

function isValidUrl(url) {
  if (!url || !url.startsWith('http')) return false;
  try {
    const hostname = new URL(url).hostname.toLowerCase();
    return !EXCLUDE_DOMAINS.some(d => hostname.includes(d) || hostname.startsWith(d));
  } catch { return false; }
}

function loadExistingUrls() {
  const existing = new Set();
  for (const f of [COMPANIES_FILE, RAW_FILE]) {
    if (!fs.existsSync(f)) continue;
    const lines = fs.readFileSync(f, 'utf8').split('\n').slice(1);
    for (const line of lines) {
      if (!line.trim()) continue;
      // CSVの最初のカラム（url）を取得（クォート対応）
      const m = line.match(/^"([^"]+)"|^([^,]+)/);
      const url = m ? (m[1] || m[2]).trim() : '';
      if (url) existing.add(normalizeUrl(url));
    }
  }
  return existing;
}

function initRawFile() {
  if (!fs.existsSync(RAW_FILE)) {
    fs.writeFileSync(RAW_FILE, 'url,company_name,contact_url,status,submitted_at,note\n', 'utf8');
  }
}

function saveEntry(url, name, source, existingUrls) {
  const norm = normalizeUrl(url);
  if (existingUrls.has(norm)) return false;
  existingUrls.add(norm);
  const line = `${csvEscape(url)},${csvEscape(name)},,pending,,${csvEscape(source)}\n`;
  fs.appendFileSync(RAW_FILE, line, 'utf8');
  return true;
}

function loadProgress() {
  if (fs.existsSync(PROGRESS_FILE)) {
    try { return JSON.parse(fs.readFileSync(PROGRESS_FILE, 'utf8')); }
    catch {}
  }
  return {};
}

function saveProgress(p) {
  fs.writeFileSync(PROGRESS_FILE, JSON.stringify(p, null, 2));
}

function countRaw() {
  if (!fs.existsSync(RAW_FILE)) return 0;
  return fs.readFileSync(RAW_FILE, 'utf8')
    .split('\n').filter(l => l.trim() && !l.startsWith('url,')).length;
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms + Math.random() * 1000));
}

// ===== Phase 1: Iタウンページ =====

async function collectITP(page, existingUrls, progress) {
  let total = 0;
  console.log('\n========================================');
  console.log('Phase 1: Iタウンページ');
  console.log('========================================');

  for (const cat of ITP_CATEGORIES) {
    const key = `itp_${cat.cd}`;
    if (progress[key] === 'done') {
      console.log(`  ✓ ${cat.name} (スキップ済み)`);
      continue;
    }

    console.log(`\n  📂 ${cat.name}`);
    let catCount = 0;
    let emptyStreak = 0;

    for (let p = 1; p <= MAX_ITP_PAGES; p++) {
      const url = `https://itp.ne.jp/cgi-bin/srefer?ACT=search&prefcd=11&catcd=${cat.cd}&page=${p}`;
      try {
        await page.goto(url, { timeout: 30000, waitUntil: 'domcontentloaded' });
        await sleep(1500);

        const entries = await page.evaluate((excludes) => {
          const results = [];

          // セレクタを複数試す
          const SELECTORS = [
            '.searchResult__item', '.result-item', '.shop-item',
            'li.item', '.company-item', '.listing-item',
            '[class*="result"] li', 'article[class*="item"]',
          ];

          let items = [];
          for (const sel of SELECTORS) {
            items = Array.from(document.querySelectorAll(sel));
            if (items.length > 0) break;
          }

          // フォールバック: ページ内の外部リンクを全取得
          if (items.length === 0) {
            document.querySelectorAll('a[href^="http"]').forEach(a => {
              if (excludes.some(d => a.href.includes(d))) return;
              const name = (a.closest('li, div, article')?.querySelector('h2,h3,h4,strong,b')?.textContent || a.textContent || '').trim();
              if (name) results.push({ url: a.href, name });
            });
            return results;
          }

          items.forEach(item => {
            const nameEl = item.querySelector('h2, h3, h4, .name, .company-name, strong, b');
            const name = nameEl ? nameEl.textContent.trim() : '';
            for (const a of item.querySelectorAll('a[href^="http"]')) {
              if (excludes.some(d => a.href.includes(d))) continue;
              results.push({ url: a.href, name });
              break;
            }
          });

          return results;
        }, EXCLUDE_DOMAINS);

        if (entries.length === 0) {
          emptyStreak++;
          if (emptyStreak >= 2) {
            console.log(`    ページ${p}: 結果なし → 終了`);
            break;
          }
          continue;
        }
        emptyStreak = 0;

        let pageAdded = 0;
        for (const { url: hpUrl, name } of entries) {
          if (isValidUrl(hpUrl) && saveEntry(hpUrl, name, `ITP_${cat.name}`, existingUrls)) {
            pageAdded++;
            catCount++;
            total++;
          }
        }
        console.log(`    ページ${p}: ${entries.length}件取得 → ${pageAdded}件追加（累計 ${total}件）`);

        // 次ページリンクがなければ終了
        const hasNext = await page.evaluate(() => {
          return !!document.querySelector('a[rel="next"], .next, [class*="next"]:not([class*="noNext"])');
        });
        if (!hasNext && p > 1) break;

      } catch (e) {
        console.log(`    ⚠️ ページ${p} エラー: ${e.message.slice(0, 60)}`);
        if (p === 1) break;
      }

      await sleep(DELAY_BASE);
    }

    console.log(`  ✅ ${cat.name}: ${catCount}件追加`);
    progress[key] = 'done';
    saveProgress(progress);
  }

  return total;
}

// ===== Phase 2: DuckDuckGo検索 =====

async function collectDDG(page, existingUrls, progress) {
  let total = 0;
  const queries = [];

  // 全市区町村 × 業種キーワード
  for (const city of SAITAMA_CITIES) {
    for (const kw of DDG_KEYWORDS) {
      queries.push({ query: `埼玉県 ${city} ${kw}`, key: `ddg_${city}_${kw}` });
    }
  }
  // 業種単体クエリ（県全体）
  for (const kw of DDG_KEYWORDS) {
    queries.push({ query: `埼玉 ${kw} 公式サイト`, key: `ddg_pref_${kw}` });
  }

  console.log('\n========================================');
  console.log(`Phase 2: DuckDuckGo検索（${queries.length}クエリ）`);
  console.log('========================================');

  let qi = 0;
  for (const { query, key } of queries) {
    qi++;
    if (progress[key] === 'done') continue;

    const encoded = encodeURIComponent(query);
    const searchUrl = `https://html.duckduckgo.com/html/?q=${encoded}&kl=jp-jp`;

    try {
      await page.goto(searchUrl, { timeout: 20000, waitUntil: 'domcontentloaded' });
      await sleep(2000);

      const urls = await page.evaluate(() => {
        const results = new Set();

        // DDG HTML版: uddg= パラメータ
        document.querySelectorAll('a[href*="uddg="]').forEach(a => {
          const m = a.href.match(/uddg=([^&]+)/);
          if (m) {
            try { results.add(decodeURIComponent(m[1])); } catch {}
          }
        });

        // result__urlクラス
        document.querySelectorAll('.result__url, .result__a').forEach(a => {
          if (a.href && a.href.startsWith('http') && !a.href.includes('duckduckgo')) {
            results.add(a.href);
          }
        });

        return [...results];
      });

      let added = 0;
      for (const u of urls) {
        if (isValidUrl(u) && saveEntry(u, '', `DDG_${query}`, existingUrls)) {
          added++;
          total++;
        }
      }

      if (added > 0) {
        console.log(`  [${qi}/${queries.length}] ${query}: ${added}件追加（累計 ${total}件）`);
      }

      progress[key] = 'done';
      saveProgress(progress);

    } catch (e) {
      if (!e.message.includes('timeout')) {
        console.log(`  ⚠️ ${query}: ${e.message.slice(0, 50)}`);
      }
    }

    await sleep(DELAY_BASE);
  }

  return total;
}

// ===== Phase 3: Googleマップ =====

async function collectMaps(page, existingUrls, progress) {
  let total = 0;
  console.log('\n========================================');
  console.log('Phase 3: Googleマップ');
  console.log('========================================');

  for (const city of MAPS_CITIES) {
    for (const kw of MAPS_KEYWORDS) {
      const key = `maps_${city}_${kw}`;
      if (progress[key] === 'done') continue;

      const query = `埼玉県 ${city} ${kw}`;
      const mapsUrl = `https://www.google.com/maps/search/${encodeURIComponent(query)}`;

      try {
        await page.goto(mapsUrl, { timeout: 30000, waitUntil: 'networkidle' });
        await sleep(3000);

        // フィードをスクロールして追加読み込み
        for (let i = 0; i < 5; i++) {
          await page.evaluate(() => {
            const feed = document.querySelector('[role="feed"]');
            if (feed) feed.scrollTop += 3000;
          });
          await sleep(1500);
        }

        const entries = await page.evaluate((excludes) => {
          const results = [];
          const feed = document.querySelector('[role="feed"]');
          if (!feed) return results;

          // 各ビジネスカードのウェブサイトリンクを取得
          feed.querySelectorAll('a[href^="http"]').forEach(a => {
            if (a.href.includes('google.com') || a.href.includes('goo.gl')) return;
            if (excludes.some(d => a.href.includes(d))) return;
            const card = a.closest('[jsaction], [data-result-index]');
            const nameEl = card?.querySelector('.fontHeadlineSmall, [class*="fontTitle"], h3');
            const name = nameEl?.textContent?.trim() || '';
            results.push({ url: a.href, name });
          });

          return results;
        }, EXCLUDE_DOMAINS);

        let added = 0;
        for (const { url, name } of entries) {
          if (isValidUrl(url) && saveEntry(url, name, `Maps_${city}_${kw}`, existingUrls)) {
            added++;
            total++;
          }
        }

        if (added > 0) {
          console.log(`  ${city} × ${kw}: ${added}件追加（累計 ${total}件）`);
        }

        progress[key] = 'done';
        saveProgress(progress);

      } catch (e) {
        console.log(`  ⚠️ Maps ${city} × ${kw}: ${e.message.slice(0, 50)}`);
      }

      await sleep(DELAY_BASE + 1000);
    }
  }

  return total;
}

// ===== メイン =====

async function main() {
  const args = process.argv.slice(2);
  const phaseArg = (args.find(a => a.startsWith('--phase=')) || '').split('=')[1] || 'all';

  initRawFile();
  const existingUrls = loadExistingUrls();
  const progress = loadProgress();

  console.log('========================================');
  console.log('  埼玉県 企業収集スクリプト');
  console.log('========================================');
  console.log(`既存URL数 : ${existingUrls.size}件`);
  console.log(`出力先    : saitama_raw.csv`);
  console.log(`フェーズ  : ${phaseArg}`);

  const browser = await chromium.launch({
    headless: false,
    args: ['--lang=ja-JP'],
  });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    locale: 'ja-JP',
  });
  const page = await context.newPage();

  let total = 0;
  try {
    if (phaseArg === 'all' || phaseArg === '1') total += await collectITP(page, existingUrls, progress);
    if (phaseArg === 'all' || phaseArg === '2') total += await collectDDG(page, existingUrls, progress);
    if (phaseArg === 'all' || phaseArg === '3') total += await collectMaps(page, existingUrls, progress);
  } finally {
    await browser.close();
  }

  const rawCount = countRaw();
  console.log('\n========================================');
  console.log(`  収集完了！`);
  console.log(`  今回追加  : ${total}件`);
  console.log(`  RAW合計   : ${rawCount}件`);
  console.log('========================================');
  console.log('\n次のステップ: node merge_saitama.js');
}

main().catch(console.error);
