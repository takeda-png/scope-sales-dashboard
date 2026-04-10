/**
 * SCOPE営業パイプライン
 * companies.csv の pending 企業にフォーム送信する
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const CONFIG_FILE = path.join(__dirname, 'config.json');
const CSV_FILE = path.join(__dirname, 'companies.csv');

const CONTACT_KEYWORDS = [
  'お問い合わせ', 'お問合せ', 'お問合わせ',
  'CONTACT', 'Contact', 'contact',
  'コンタクト', 'ご相談', 'ご連絡', 'ご質問',
  'inquiry', 'INQUIRY',
];

const FIELD_LABELS = {
  name:          ['お名前', '氏名', '名前', 'お名前（漢字）', '姓名', 'ご担当者名'],
  furigana:      ['ふりがな', 'フリガナ', 'カナ', 'よみがな'],
  company:       ['会社名', '御社名', '企業名', '法人名', '貴社名', '会社・団体名'],
  department:    ['部署', '部署名', '所属', '役職・部署'],
  phone:         ['電話番号', 'TEL', 'Tel', '電話', 'お電話番号', '携帯番号'],
  email:         ['メールアドレス', 'メール', 'E-mail', 'email', 'Email'],
  email_confirm: ['メールアドレス(確認)', 'メールアドレス（確認）', 'メール確認', '確認用メール', 'E-mail（確認）', 'メールアドレス（再入力）', 'メール再入力'],
};

const FIELD_NAME_ATTRS = {
  name:          ['name', 'full_name', 'fullname', 'your_name'],
  furigana:      ['kana', 'furigana', 'yomi'],
  company:       ['company', 'company_name', 'corp'],
  department:    ['department', 'dept', 'section'],
  phone:         ['phone', 'tel', 'telephone', 'mobile'],
  email:         ['email', 'mail', 'e_mail'],
  email_confirm: ['email_confirm', 'email2', 'email_check', 'mail_confirm', 'mail2', 'confirm_email'],
};

// ハブページ誤検知ブラックリスト（リクルート・ニュース・サービス詳細・サポート等）
const HUB_BLACKLIST_PATTERNS = [
  '/recruit', '/recruitment', '/career', '/job',
  '/news/', '/press',
  '/support',
  '/brand/',
  '/product',
  '/pdf/',
  '/event',
  '/ir/',
  '/investor',
  '/information/',
  '/cloud-platform',
  '/capabilities/',
  '/security',
  '/service/security', '/service/camera', '/service/network',
];

function isBlacklistedHubUrl(url) {
  const lower = url.toLowerCase();
  return HUB_BLACKLIST_PATTERNS.some(p => lower.includes(p));
}

// ===== CSV操作 =====

function loadConfig() {
  return JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
}

function loadCompanies() {
  if (!fs.existsSync(CSV_FILE)) return [];
  const content = fs.readFileSync(CSV_FILE, 'utf-8');
  const lines = content.trim().split('\n');
  const headers = lines[0].split(',');
  return lines.slice(1).map(line => {
    const values = line.split(',');
    const obj = {};
    headers.forEach((h, i) => obj[h.trim()] = (values[i] || '').trim());
    return obj;
  });
}

function saveCompanies(companies) {
  const headers = ['url', 'company_name', 'contact_url', 'status', 'submitted_at', 'note'];
  const lines = [headers.join(',')];
  for (const c of companies) {
    lines.push(headers.map(h => c[h] || '').join(','));
  }
  fs.writeFileSync(CSV_FILE, lines.join('\n') + '\n', 'utf-8');
}

function updateStatus(companies, url, status, contactUrl = '', note = '') {
  const now = new Date().toLocaleString('ja-JP');
  for (const c of companies) {
    if (c.url === url) {
      c.status = status;
      c.submitted_at = now;
      if (contactUrl) c.contact_url = contactUrl;
      if (note) c.note = note.replace(/,/g, '；').replace(/[\r\n]+/g, ' ');
      break;
    }
  }
  saveCompanies(companies);
}

// ===== フォーム操作 =====

// ハブページ上のフォームリンクを探す（「お問い合わせフォームはこちら」等）
async function findFormLinkOnPage(page, baseUrl) {
  const formKeywords = [
    'お問い合わせフォーム', '問い合わせフォーム', 'お問合わせフォーム',
    'フォームはこちら', 'フォームへ', 'こちらのフォーム',
    'サービスに関するお問い合わせ', 'ご提案', '協業',
    // 同意ページ対応: 「同意して問い合わせる」リンクを自動クリック
    '同意して問い合わせる', '同意してお問い合わせ', '同意して問い合わせ',
    '上記に同意', '上記内容に同意',
  ];
  for (const keyword of formKeywords) {
    try {
      const links = page.locator(`a:has-text('${keyword}')`);
      const count = await links.count();
      for (let i = 0; i < count; i++) {
        const href = await links.nth(i).getAttribute('href');
        if (href && !href.startsWith('tel:') && !href.startsWith('mailto:')) {
          try {
            const full = new URL(href, baseUrl).href;
            if (!isBlacklistedHubUrl(full)) return full;
          } catch { continue; }
        }
      }
    } catch { continue; }
  }
  // URL に form/entry/inquiry/contact が含まれるリンクを探す
  try {
    const linkEls = page.locator('a[href*="form"], a[href*="entry"], a[href*="inquiry"]');
    const count = await linkEls.count();
    for (let i = 0; i < count; i++) {
      const href = await linkEls.nth(i).getAttribute('href');
      if (href && !href.includes('#')) {
        try {
          const full = new URL(href, baseUrl).href;
          if (full !== page.url() && !isBlacklistedHubUrl(full)) return full;
        } catch { continue; }
      }
    }
  } catch { }
  return null;
}

// ===== Google Forms 対応 =====

async function fillGoogleForm(page, config, companyName) {
  const message = config.message
    .replace('○○様', `${companyName} ご担当者様`)
    .replace('〇〇様', `${companyName} ご担当者様`)
    .replace('〇〇と申します', '佐々木と申します');

  const fieldMap = [
    { keywords: ['名前', '氏名', 'お名前', 'name', 'Name', '担当者'], value: config.sender.name },
    { keywords: ['会社', 'company', 'Company', '会社名', '企業名'], value: config.sender.company },
    { keywords: ['メール', 'email', 'Email', 'E-mail', 'mail', 'Mail'], value: config.sender.email },
    { keywords: ['電話', 'phone', 'Phone', 'tel', 'Tel', 'TEL'], value: config.sender.phone },
    { keywords: ['内容', 'message', 'Message', '問い合わせ', 'お問い合わせ', 'ご質問', '本文', '詳細', '用件'], value: message },
  ];

  for (const field of fieldMap) {
    for (const kw of field.keywords) {
      try {
        const inp = page.locator(`[aria-label*="${kw}"], [aria-labelledby] input[aria-label*="${kw}"]`).first();
        if (await inp.count() > 0) {
          const val = await inp.inputValue().catch(() => '');
          if (val === '') await inp.fill(field.value);
          break;
        }
      } catch { }
    }
  }

  // Fallback: 未入力のtextareaにメッセージを入れる
  try {
    const tas = page.locator('textarea:visible');
    const taCount = await tas.count();
    for (let i = 0; i < taCount; i++) {
      const val = await tas.nth(i).inputValue().catch(() => '');
      if (val === '') { await tas.nth(i).fill(message); break; }
    }
  } catch { }

  // Google Forms の送信ボタン（div[role="button"]）
  await page.waitForTimeout(500);
  for (const text of ['送信', 'Submit', '提出']) {
    try {
      const btn = page.locator(`div[role="button"]:has-text("${text}")`).first();
      if (await btn.count() > 0) { await btn.click(); return true; }
    } catch { }
  }
  return false;
}

async function findContactUrl(page, baseUrl) {
  for (const keyword of CONTACT_KEYWORDS) {
    try {
      const links = page.locator(`a:has-text('${keyword}')`);
      const count = await links.count();
      for (let i = 0; i < count; i++) {
        const href = await links.nth(i).getAttribute('href');
        if (href && !href.startsWith('tel:') && !href.startsWith('mailto:') && !href.startsWith('javascript:')) {
          try {
            return new URL(href, baseUrl).href;
          } catch { continue; }
        }
      }
    } catch { continue; }
  }
  return null;
}

async function tryFillInput(page, fieldType, labels, value) {
  if (!value) return false;

  // 1. label[for] で探す
  for (const labelText of labels) {
    try {
      const label = page.locator(`label:has-text('${labelText}')`).first();
      if (await label.count() > 0) {
        const forId = await label.getAttribute('for');
        if (forId) {
          const inp = page.locator(`#${forId}`).first();
          if (await inp.count() > 0) {
            await inp.fill(value);
            return true;
          }
        }
      }
    } catch { }
  }

  // 2. placeholder で探す
  for (const labelText of labels) {
    try {
      const inp = page.locator(`input[placeholder*='${labelText}']`).first();
      if (await inp.count() > 0) {
        await inp.fill(value);
        return true;
      }
    } catch { }
  }

  // 3. name/id 属性で探す
  for (const attrVal of (FIELD_NAME_ATTRS[fieldType] || [])) {
    try {
      const inp = page.locator(`input[name*='${attrVal}'], input[id*='${attrVal}']`).first();
      if (await inp.count() > 0) {
        await inp.fill(value);
        return true;
      }
    } catch { }
  }

  // 4. テーブル行のヘッダーテキストで探す（例: sinmido.com のように th/td 構造のフォーム）
  for (const labelText of labels) {
    try {
      const inp = page.locator(`tr:has(th:has-text('${labelText}')) input, tr:has(td:has-text('${labelText}')) input`).first();
      if (await inp.count() > 0) {
        await inp.fill(value);
        return true;
      }
    } catch { }
  }

  // 5. 直前の要素テキストで探す（dt/dd 構造など）
  for (const labelText of labels) {
    try {
      const inp = page.locator(`dt:has-text('${labelText}') + dd input, .label:has-text('${labelText}') input`).first();
      if (await inp.count() > 0) {
        await inp.fill(value);
        return true;
      }
    } catch { }
  }

  return false;
}

async function fillAndSubmit(page, config, companyName) {
  const sender = config.sender;
  const filled = {};

  // メッセージの会社名・担当者名を差し込む
  const senderLastName = config.sender.name.replace(/[ぁ-んァ-ン]/g, '').replace('ようけん', '').trim() || '佐々木';
  config = {
    ...config,
    message: config.message
      .replace('○○様', `${companyName} ご担当者様`)
      .replace('〇〇様', `${companyName} ご担当者様`)
      .replace('〇〇と申します', `佐々木と申します`)
  };

  const fieldData = {
    name:          sender.name,
    furigana:      sender.furigana,
    company:       sender.company,
    department:    sender.department || '',
    phone:         sender.phone,
    email:         sender.email,
    email_confirm: sender.email,
  };

  for (const [fieldType, labels] of Object.entries(FIELD_LABELS)) {
    filled[fieldType] = await tryFillInput(page, fieldType, labels, fieldData[fieldType]);
  }

  // お問い合わせ内容（textarea）
  try {
    const textarea = page.locator('textarea').first();
    if (await textarea.count() > 0) {
      await textarea.fill(config.message);
      filled.message = true;
    }
  } catch { filled.message = false; }

  // <select> ドロップダウン（問い合わせ種別など）: 「その他」を選択
  try {
    const selects = page.locator('select');
    const selCount = await selects.count();
    for (let i = 0; i < selCount; i++) {
      const sel = selects.nth(i);
      const opts = await sel.locator('option:not([disabled])').allTextContents();
      if (opts.length === 0) continue;
      // 「その他」があれば選択、なければ最後の有効な選択肢
      const sonotaOpt = opts.find(o => o.includes('その他') || o.toLowerCase().includes('other'));
      const chosen = sonotaOpt || opts[opts.length - 1];
      await sel.selectOption({ label: chosen }).catch(async () => {
        await sel.selectOption(opts[opts.length - 1]).catch(() => {});
      });
    }
    filled.select = selCount > 0;
  } catch { }

  // お問い合わせ種別チェックボックス（「その他」または最初の選択肢をチェック）
  try {
    const checkboxes = page.locator("input[type='checkbox']");
    const cbCount = await checkboxes.count();
    if (cbCount > 1) {
      // 「その他」ラベルのチェックボックスを優先
      const sonotaLabels = ['その他', 'other', 'Other', 'その他（自由記入）'];
      let checked = false;
      for (const lbl of sonotaLabels) {
        try {
          const cb = page.locator(`input[type='checkbox'][value*='${lbl}'], label:has-text('${lbl}') input[type='checkbox']`).first();
          if (await cb.count() > 0) { await cb.check(); checked = true; break; }
        } catch { }
      }
      // 見つからなければ最初のチェックボックスをチェック
      if (!checked) {
        await checkboxes.first().check();
      }
      filled.inquiry_type = true;

      // チェック後に新たに現れたテキスト入力欄（自由入力欄など）を埋める
      try {
        await page.waitForTimeout(400);
        const allInputs = page.locator("input[type='text']:visible, textarea:visible");
        const inputCount = await allInputs.count();
        for (let i = 0; i < inputCount; i++) {
          const inp = allInputs.nth(i);
          const val = await inp.inputValue().catch(() => '');
          if (val === '') {
            await inp.fill('その他のお問合せ');
          }
        }
      } catch { }
    }
  } catch { filled.inquiry_type = false; }

  // プライバシーポリシー同意（最後のチェックボックス）
  try {
    const checkboxes = page.locator("input[type='checkbox']");
    const cbCount = await checkboxes.count();
    if (cbCount > 0) {
      const ppCb = checkboxes.nth(cbCount - 1);
      try {
        await ppCb.check({ force: true });
      } catch {
        // spanが覆っている場合は親要素クリック
        await ppCb.locator('xpath=..').click({ force: true }).catch(() => {});
      }
      filled.privacy = true;
    }
  } catch { filled.privacy = false; }

  // お問い合わせ種別: ARIA role="radio"/"checkbox" カスタム要素対応（複数ある場合のみ）
  try {
    const roleEls = page.locator('[role="radio"], [role="checkbox"]');
    const roleCount = await roleEls.count();
    if (roleCount > 1) {  // 1つだけならPPチェックボックスなので除外
      let clicked = false;
      for (let i = 0; i < roleCount; i++) {
        const txt = await roleEls.nth(i).textContent().catch(() => '');
        if (txt.includes('その他') || txt.includes('Other') || txt.includes('other')) {
          await roleEls.nth(i).click({ force: true });
          clicked = true;
          break;
        }
      }
      if (!clicked) await roleEls.first().click({ force: true });
      filled.inquiry_type_aria = true;
      await page.waitForTimeout(300);
    }
  } catch { }

  // PP同意: 非チェックボックス型のクリック要素対応
  try {
    const agreeSelectors = [
      "label:has-text('同意する')",
      "label:has-text('プライバシーポリシーに同意')",
      "form [class*='agree']",
      "form [class*='privacy']",
      "span:has-text('同意する')",
    ];
    let ppClicked = false;
    for (const sel of agreeSelectors) {
      try {
        const el = page.locator(sel).first();
        if (await el.count() > 0) {
          const tag = await el.evaluate(e => e.tagName.toLowerCase());
          // <a>タグはナビゲーションリンクの可能性があるためスキップ
          if (tag === 'a') continue;
          if (tag !== 'label' || !(await el.getAttribute('for'))) {
            await el.click();
            ppClicked = true;
            break;
          }
        }
      } catch { }
    }
    if (ppClicked) {
      filled.privacy_custom = true;
      await page.waitForTimeout(300);
    }
  } catch { }

  // 送信ボタン
  const submitTexts = [
    '送信する', '送信', '確認する', '入力内容を確認', '次へ',
    '送信内容の確認', '確認画面へ', 'お問い合わせを送る',
    '送信いたします', '内容を確認し送信する',
    '確認へ', '送信内容確認', '同意して確認画面へ',
    'submit', 'Submit', 'SUBMIT',
  ];
  let submitted = false;

  async function trySubmit() {
    for (const btnText of submitTexts) {
      try {
        const btns = page.locator([
          `button:has-text('${btnText}'):not([disabled])`,
          `input[type='submit'][value*='${btnText}']:not([disabled])`,
          `input[type='button'][value*='${btnText}']:not([disabled])`,
        ].join(', '));
        const count = await btns.count();
        for (let i = 0; i < count; i++) {
          try {
            const btn = btns.nth(i);
            if (await btn.isVisible()) {
              await btn.click();
              return true;
            }
          } catch { }
        }
        // visible なものが見つからなければ force: true で試みる
        if (count > 0) {
          try {
            await btns.first().click({ force: true });
            return true;
          } catch { }
        }
      } catch { }
    }
    try {
      const btn = page.locator("input[type='submit']:not([disabled]), button[type='submit']:not([disabled]), input[type='button'][id*='submit']:not([disabled])").first();
      if (await btn.count() > 0 && await btn.isVisible()) {
        await btn.click();
        return true;
      }
    } catch { }
    // <a>タグ型の送信リンク対応（javascript:void(0)等）
    for (const btnText of submitTexts) {
      try {
        const lnk = page.locator(`a:has-text('${btnText}')`).first();
        if (await lnk.count() > 0) {
          await lnk.click();
          return true;
        }
      } catch { }
    }
    return false;
  }

  submitted = await trySubmit();

  // disabledボタンがある場合: 必須項目のカスタムUI要素をクリックして再試行
  if (!submitted) {
    try {
      const disabledBtn = page.locator("button[type='submit'][disabled], input[type='submit'][disabled]");
      if (await disabledBtn.count() > 0) {
        console.log('  ⚙️  disabled ボタン検出 → カスタム要素をクリックして再試行');
        // お問い合わせ種別のカスタムクリック要素（汎用 div/span）
        const clickableItems = page.locator('form [class*="item"]:visible, form [class*="type"]:visible, form [class*="category"]:visible');
        const cCount = await clickableItems.count();
        if (cCount > 0) {
          // 「その他」または最後の項目をクリック
          let found = false;
          for (let i = 0; i < cCount; i++) {
            const txt = await clickableItems.nth(i).textContent().catch(() => '');
            if (txt.includes('その他') || txt.includes('Other')) {
              await clickableItems.nth(i).click();
              found = true;
              break;
            }
          }
          if (!found) await clickableItems.last().click();
          await page.waitForTimeout(400);
        }
        submitted = await trySubmit();
      }
    } catch { }
  }

  return { filled, submitted };
}

// ===== メイン処理 =====

async function processCompany(page, company, companies, config, delay) {
  const url = company.url;
  console.log(`\n${'='.repeat(50)}`);
  console.log(`🌐 ${url}`);

  try {
    await page.goto(url, { timeout: 15000, waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);

    // フォームURLが既にある場合はスキップ、なければ自動検索
    let contactUrl = company.contact_url || '';
    if (contactUrl) {
      console.log(`  📋 フォームページ（既存）: ${contactUrl}`);
    } else {
      contactUrl = await findContactUrl(page, url);
      if (!contactUrl) {
        console.log('  ❌ お問い合わせページが見つかりません');
        updateStatus(companies, url, 'no_form', '', 'contact link not found');
        return false;
      }
      console.log(`  📋 フォームページ（自動検出）: ${contactUrl}`);
    }

    await page.goto(contactUrl, { timeout: 15000, waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);

    // ハブページ検出: inputが少ない場合はフォームリンクを辿る
    const inputCount = await page.locator("input[type='text'], input[type='email'], input[type='tel'], textarea").count();
    if (inputCount < 2) {
      const formLink = await findFormLinkOnPage(page, contactUrl);
      if (formLink && formLink !== contactUrl) {
        console.log(`  🔗 ハブページ検出 → フォームリンクへ: ${formLink}`);
        await page.goto(formLink, { timeout: 15000, waitUntil: 'domcontentloaded' });
        await page.waitForTimeout(1500);
        contactUrl = formLink;
      }
    }

    // Google Forms 対応
    if (contactUrl.includes('docs.google.com/forms')) {
      console.log('  📋 Google Forms を検出 → 専用ハンドラで送信');
      const submitted = await fillGoogleForm(page, config, company.company_name || '');
      if (submitted) {
        await page.waitForTimeout(2000);
        console.log('  📤 送信完了（Google Forms）');
        updateStatus(companies, url, 'submitted', contactUrl);
      } else {
        console.log('  ⚠️ Google Forms: 送信ボタンが見つかりません');
        updateStatus(companies, url, 'manual_check', contactUrl, 'google forms submit not found');
      }
      await page.waitForTimeout(delay * 1000);
      return submitted;
    }

    const { filled, submitted } = await fillAndSubmit(page, config, company.company_name || '');
    const filledFields = Object.entries(filled).filter(([, v]) => v).map(([k]) => k);
    console.log(`  ✅ 入力完了: ${filledFields.join(', ')}`);

    if (submitted) {
      await page.waitForTimeout(2000);

      // 確認画面が表示された場合、最終送信ボタンを押す（2段階フォーム対応）
      const finalSubmitTexts = ['送信する', '送信', '確定する', '完了', 'この内容で送信'];
      for (const btnText of finalSubmitTexts) {
        try {
          const btn = page.locator(`button:has-text('${btnText}'), input[type='submit'][value*='${btnText}']`).first();
          if (await btn.count() > 0) {
            await btn.click();
            console.log(`  📨 確認画面から最終送信: ${btnText}`);
            await page.waitForTimeout(2000);
            break;
          }
        } catch { }
      }

      console.log('  📤 送信完了');
      updateStatus(companies, url, 'submitted', contactUrl);
    } else {
      console.log('  ⚠️ 送信ボタンが見つかりません（手動確認が必要）');
      updateStatus(companies, url, 'manual_check', contactUrl, 'submit button not found');
    }

    await page.waitForTimeout(delay * 1000);
    return submitted;

  } catch (e) {
    const msg = e.message || String(e);
    if (msg.includes('Timeout') || msg.includes('timeout')) {
      console.log('  ⏱️ タイムアウト');
      updateStatus(companies, url, 'error', '', 'timeout');
    } else if (msg.includes('Download is starting')) {
      console.log('  📥 ダウンロードURL → スキップ');
      updateStatus(companies, url, 'skip', '', 'download url');
    } else if (msg.includes('interrupted by another navigation')) {
      // JSリダイレクト中断は再試行せずerrorに
      console.log('  ↩️ ナビゲーション中断 → error');
      updateStatus(companies, url, 'error', '', 'navigation interrupted');
    } else if (msg.includes('ERR_CERT') || msg.includes('ERR_SSL')) {
      console.log('  🔒 SSL証明書エラー → スキップ');
      updateStatus(companies, url, 'skip', '', 'ssl error');
    } else {
      console.log(`  ❌ エラー: ${msg.slice(0, 80)}`);
      updateStatus(companies, url, 'error', '', msg.slice(0, 80));
    }
    return false;
  }
}

async function runWorker(workerId, workerBatch, companies, config, headless, delay) {
  const browser = await chromium.launch({ headless });
  let success = 0;
  for (const company of workerBatch) {
    let page;
    try {
      page = await browser.newPage();
      await page.setExtraHTTPHeaders({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      });
      const ok = await processCompany(page, company, companies, config, delay);
      if (ok) success++;
    } catch (e) {
      const msg = (e.message || String(e)).slice(0, 80);
      console.log(`  ❌ Worker${workerId} エラー: ${msg}`);
      updateStatus(companies, company.url, 'error', '', msg);
    } finally {
      await page?.close().catch(() => {});
    }
  }
  await browser.close().catch(() => {});
  return success;
}

async function runPipeline() {
  const config = loadConfig();
  const { delay_between_sites, max_per_session, headless, parallel_workers = 1 } = config.submission;
  const companies = loadCompanies();

  const pending = companies.filter(c => c.status === 'pending');
  console.log(`📊 pending: ${pending.length}件`);

  if (pending.length === 0) {
    console.log('送信待ちの企業がありません。先に collect.js を実行してURLを収集してください。');
    return;
  }

  const batch = pending.slice(0, max_per_session);
  console.log(`🚀 今回の送信: ${batch.length}件 / ${parallel_workers}並列\n`);

  // バッチをworker数で均等分割
  const chunkSize = Math.ceil(batch.length / parallel_workers);
  const chunks = [];
  for (let i = 0; i < parallel_workers; i++) {
    const chunk = batch.slice(i * chunkSize, (i + 1) * chunkSize);
    if (chunk.length > 0) chunks.push(chunk);
  }

  const results = await Promise.all(
    chunks.map((chunk, i) => runWorker(i + 1, chunk, companies, config, headless, delay_between_sites))
  );

  const success = results.reduce((a, b) => a + b, 0);
  console.log(`\n${'='.repeat(50)}`);
  console.log(`✅ 完了: ${success}/${batch.length}件 送信成功`);
}

runPipeline().catch(console.error);
