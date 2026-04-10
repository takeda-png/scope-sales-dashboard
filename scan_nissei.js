const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setExtraHTTPHeaders({ 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' });
  await page.goto('https://www.nissei-service.jp/contact.html', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);

  // ページのHTML（フォーム部分）を取得
  const html = await page.content();
  const submitIdx = html.indexOf('送信内容確認');
  if (submitIdx > -1) {
    console.log('Submit area HTML:\n', html.substring(submitIdx - 200, submitIdx + 300));
  }

  // submitまわりの要素
  const allEls = await page.locator('[onclick], a:has-text("確認"), a:has-text("送信"), p:has-text("確認"), div:has-text("送信内容確認")').evaluateAll(function(els) {
    return els.slice(0, 10).map(function(el) {
      return {
        tag: el.tagName,
        type: el.type,
        class: el.className,
        onclick: el.getAttribute('onclick'),
        href: el.getAttribute('href'),
        text: (el.textContent || '').trim().slice(0, 50),
        visible: el.offsetParent !== null
      };
    });
  });
  console.log('\nClickable elements near submit:');
  allEls.forEach(function(el) { console.log(JSON.stringify(el)); });
})().catch(console.error);
