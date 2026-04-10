const { chromium } = require('playwright');

const targets = [
  { name: '光風舎', url: 'http://www.kofuu.co.jp/contact.shtml' },
  { name: '日精サービス', url: 'https://www.nissei-service.jp/contact.html' },
  { name: 'D2C', url: 'https://www.d2c.co.jp/inquiryform/' },
  { name: 'セレス', url: 'https://ceres-inc.jp/index/inquiry/?origin=media' },
  { name: 'オービック', url: 'https://www.oa.obic.co.jp/other_contact/form.html' },
  { name: 'カントー', url: 'https://www.kantoh.co.jp/pages/495/' },
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setExtraHTTPHeaders({ 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' });

  for (const t of targets) {
    try {
      await page.goto(t.url, { timeout: 12000, waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(1500);

      const btns = await page.locator('button, input[type=submit], input[type=button]').evaluateAll(function(els) {
        return els.map(function(el) {
          return {
            tag: el.tagName,
            type: el.type,
            text: (el.textContent || '').trim().slice(0, 40),
            value: (el.value || '').slice(0, 40),
            disabled: el.disabled,
            visible: el.offsetParent !== null
          };
        });
      });
      const recap = await page.locator('iframe[src*="recaptcha"], .g-recaptcha').count();

      console.log('\n--- ' + t.name + ' ---');
      console.log('reCAPTCHA:', recap);
      btns.forEach(function(b) {
        var label = b.text || b.value;
        console.log('  [' + b.tag + '/' + b.type + '] text="' + label + '" disabled=' + b.disabled + ' visible=' + b.visible);
      });
    } catch(e) {
      console.log('\n--- ' + t.name + ' --- ERROR: ' + e.message.slice(0, 80));
    }
  }
  await browser.close();
})().catch(console.error);
