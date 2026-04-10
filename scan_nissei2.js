const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setExtraHTTPHeaders({ 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' });
  await page.goto('https://www.nissei-service.jp/contact.html', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);

  // ラジオボタン・セレクトを調べる
  const radios = await page.locator('input[type=radio]').evaluateAll(function(els) {
    return els.map(function(el) {
      return { name: el.name, value: el.value, checked: el.checked, visible: el.offsetParent !== null };
    });
  });
  console.log('Radio buttons:', JSON.stringify(radios, null, 2));

  // ラジオを1つクリックした後の状態を確認
  if (radios.length > 0) {
    await page.locator('input[type=radio]').first().click({ force: true });
    await page.waitForTimeout(500);

    const submitVisible = await page.locator('#submit').isVisible();
    console.log('\nAfter radio click, #submit visible:', submitVisible);

    const submitEl = await page.locator('#submit').evaluate(function(el) {
      return { style: el.getAttribute('style'), display: window.getComputedStyle(el).display };
    });
    console.log('submit style:', JSON.stringify(submitEl));
  }
})().catch(console.error);
