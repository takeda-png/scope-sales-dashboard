const { chromium } = require('playwright');
const fs = require('fs');

const content = fs.readFileSync('companies.csv', 'utf-8');
const lines = content.trim().split('\n');
const headers = lines[0].split(',').map(h => h.trim());
const companies = lines.slice(1).map(function(line) {
  var vals = line.split(',');
  var obj = {};
  headers.forEach(function(h, i) { obj[h] = (vals[i] || '').trim(); });
  return obj;
}).filter(function(c) { return c.status === 'manual_check'; });

// 前回スキャンでno-inputsまたはno-inputs系だったURL
const noInputUrls = [
  'https://www.c-linkage.co.jp/contact.html',
  'https://www.genetec.co.jp/contact/',
  'https://www.taki.co.jp/contact/?lfcpid=4#contact04',
  'https://www.ascon.co.jp/contact/',
  'https://www.nik-prt.co.jp/contact/',
  'http://nagasakisyouji.com/p_toiawase.htm',
  'https://support.n-create.co.jp/information/info_20240828.php',
  'https://nextage.persol-group.co.jp/contact/',
  'https://www.hbs.co.jp/cgi-bin/form_toiawase.cgi',
  'https://www.robo.co.jp/contact/',
  'https://www.sezax.co.jp/company_information/',
  'https://www.max-ltd.co.jp/toiawase/',
  'https://www.techfirm.co.jp/inquiry',
  'https://www.cyber-records.co.jp/contact',
];

(async function() {
  var browser = await chromium.launch({ headless: true });
  var page = await browser.newPage();
  await page.setExtraHTTPHeaders({ 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' });

  for (var i = 0; i < noInputUrls.length; i++) {
    var url = noInputUrls[i];
    var company = companies.find(function(c) { return c.contact_url === url; }) || {};
    try {
      await page.goto(url, { timeout: 15000, waitUntil: 'networkidle' });
      await page.waitForTimeout(3000);

      var inputs = await page.locator("input[type='text'], input[type='email'], input[type='tel'], textarea").count();
      var btns = await page.locator("button[type='submit'], input[type='submit'], button:has-text('送信'), button:has-text('確認')").count();
      var recap = await page.locator("iframe[src*='recaptcha'], .g-recaptcha").count();
      var iframes = await page.locator('iframe').count();
      var currentUrl = page.url();

      var status = 'still-empty';
      if (inputs >= 2 && btns > 0) status = 'FIXABLE';
      else if (inputs >= 2) status = 'needs-submit';
      else if (iframes > 0) status = 'iframe';
      else if (recap > 0) status = 'recaptcha';

      console.log('[' + status + '] ' + (company.company_name || url.slice(0, 40)) + ' | inputs=' + inputs + ' btns=' + btns + ' recap=' + recap + ' iframe=' + iframes);
      if (currentUrl !== url) console.log('  → redirected to: ' + currentUrl);
    } catch(e) {
      console.log('[timeout] ' + (company.company_name || url) + ': ' + e.message.slice(0, 60));
    }
  }

  await browser.close();
})().catch(console.error);
