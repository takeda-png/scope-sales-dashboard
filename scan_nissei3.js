const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setExtraHTTPHeaders({ 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' });
  await page.goto('https://www.nissei-service.jp/contact.html', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);

  // 「物流」「フード」などのリンク/ボタンを探す
  const links = await page.locator('a, [onclick]').evaluateAll(function(els) {
    return els.filter(function(el) {
      var txt = (el.textContent || '').trim();
      return txt.includes('物流') || txt.includes('フード') || txt.includes('広告') || txt.includes('問合せ先');
    }).map(function(el) {
      return {
        tag: el.tagName,
        href: el.getAttribute('href'),
        onclick: el.getAttribute('onclick'),
        text: (el.textContent || '').trim().slice(0, 60),
        visible: el.offsetParent !== null
      };
    });
  });
  console.log('Links/onclick:', JSON.stringify(links, null, 2));

  // 「物流」テキストのある要素をクリックしてみる
  try {
    await page.locator('a:has-text("総合物流")').first().click();
    await page.waitForTimeout(800);
    const submitVisible = await page.locator('#submit').isVisible().catch(() => false);
    console.log('\nAfter 総合物流 click, #submit visible:', submitVisible);
    const url = page.url();
    console.log('Current URL:', url);
  } catch(e) {
    console.log('click error:', e.message.slice(0, 80));
  }
})().catch(console.error);
