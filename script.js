const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

async function fillForm() {
  // JSONファイルから入力データを読み込む
  const dataFile = path.join(__dirname, 'data.json');
  const data = JSON.parse(fs.readFileSync(dataFile, 'utf-8'));

  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  page.setDefaultTimeout(10000);

  try {
    // ページにアクセス
    console.log(`🌐 アクセス中: ${data.url}`);
    await page.goto(data.url);
    await page.waitForTimeout(1000);

    // お問い合わせ項目（複数選択）
    console.log('\n📋 お問い合わせ項目を選択中...');
    for (const item of data.inquiry_items) {
      const checkbox = page.locator(`text='${item}'`).locator('..');
      await checkbox.click();
      console.log(`  ✓ ${item}`);
    }

    await page.waitForTimeout(500);

    // テキスト入力フィールドを全て取得
    const inputs = page.locator("input[placeholder='入力してください']");
    const inputCount = await inputs.count();

    // お名前
    if (inputCount > 0) {
      await inputs.nth(0).fill(data.name);
      console.log(`\n👤 お名前: ${data.name}`);
    }

    // フリガナ
    if (inputCount > 1) {
      await inputs.nth(1).fill(data.furigana);
      console.log(`📝 フリガナ: ${data.furigana}`);
    }

    // 会社名
    if (inputCount > 2) {
      await inputs.nth(2).fill(data.company);
      console.log(`🏢 会社名: ${data.company}`);
    }

    // 部署（任意）
    let inputIndex = 3;
    if (data.department) {
      if (inputCount > inputIndex) {
        await inputs.nth(inputIndex).fill(data.department);
        console.log(`🏪 部署: ${data.department}`);
      }
      inputIndex++;
    }

    // 電話番号
    if (inputCount > inputIndex) {
      await inputs.nth(inputIndex).fill(data.phone);
      console.log(`📞 電話番号: ${data.phone}`);
    }
    inputIndex++;

    // メールアドレス
    if (inputCount > inputIndex) {
      await inputs.nth(inputIndex).fill(data.email);
      console.log(`📧 メールアドレス: ${data.email}`);
    }

    // お問い合わせ内容
    const textarea = page.locator('textarea');
    await textarea.fill(data.inquiry_content);
    console.log(`💬 お問い合わせ内容: ${data.inquiry_content.substring(0, 30)}...`);

    // 個人情報の取扱いについて同意
    const allCheckboxes = page.locator("input[type='checkbox']");
    const checkboxCount = await allCheckboxes.count();
    await allCheckboxes.nth(checkboxCount - 1).check();
    console.log(`✅ 個人情報の取扱いについて: 同意\n`);

    // 送信ボタンをクリック
    const submitButton = page.locator("button:has-text('入力内容を確認する')");
    await submitButton.click();
    console.log('📤 フォーム送信中...\n');

    // 確認画面待機
    await page.waitForTimeout(2000);

    console.log('✅ フォーム送信完了\n');

    // ブラウザを3秒間開いたままにして確認
    await page.waitForTimeout(3000);
  } catch (error) {
    console.error('❌ エラーが発生しました:', error.message);
  } finally {
    await browser.close();
  }
}

fillForm();
