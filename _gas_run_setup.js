// GASエディタを開いて setup() を実行する（Playwright / ログイン済みプロファイル使用）
const { chromium } = require('playwright');

const PROFILE = 'C:\\Users\\taked\\AppData\\Local\\ms-playwright\\mcp-chrome-122caf9';
const SCRIPT_ID = '1eyARFfjktsnK5hzHSar4ckc0YYzJy4lm1zH8eOcc-Wg-nBCkDmlFsypz';
const URL = `https://script.google.com/home/projects/${SCRIPT_ID}/edit`;
const SHOT = 'C:\\Users\\taked\\AppData\\Local\\Temp\\claude\\C--Windows-System32\\24bff0b8-6f7b-4c4f-bfb5-e39efa142e9d\\scratchpad\\';

(async () => {
  const ctx = await chromium.launchPersistentContext(PROFILE, {
    channel: 'chrome',
    headless: false,
    viewport: { width: 1500, height: 950 },
    args: ['--no-first-run', '--no-default-browser-check']
  });
  const page = ctx.pages()[0] || await ctx.newPage();

  console.log('→ navigating…');
  await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.waitForTimeout(15000);

  console.log('URL:', page.url());
  console.log('TITLE:', await page.title());

  // ツールバーのボタン/コンボボックスを列挙
  const items = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('button,[role="button"],[role="combobox"],select').forEach(el => {
      const t = (el.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 40);
      const a = el.getAttribute('aria-label') || '';
      const tip = el.getAttribute('data-tooltip') || '';
      if (t || a || tip) out.push({ tag: el.tagName, role: el.getAttribute('role') || '', text: t, aria: a, tip: tip });
    });
    return out.slice(0, 60);
  });
  console.log(JSON.stringify(items, null, 1));

  await page.screenshot({ path: SHOT + 'gas_editor.png', fullPage: false });
  console.log('screenshot saved');

  await page.waitForTimeout(2000);
  await ctx.close();
})().catch(e => { console.error('ERROR:', e.message); process.exit(1); });
