#!/usr/bin/env python3
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

async def fill_form():
    # JSONファイルから入力データを読み込む
    data_file = Path(__file__).parent / "data.json"
    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        page.set_default_timeout(10000)

        # ページにアクセス
        print(f"🌐 アクセス中: {data['url']}")
        await page.goto(data['url'])
        await page.wait_for_timeout(1000)

        # お問い合わせ項目（複数選択）
        print("\n📋 お問い合わせ項目を選択中...")
        for item in data['inquiry_items']:
            # チェックボックスの親要素を見つけてクリック
            checkbox = page.locator(f"text='{item}'").locator("..")
            await checkbox.click()
            print(f"  ✓ {item}")

        # 待機
        await page.wait_for_timeout(500)

        # お名前
        name_inputs = page.locator("input[placeholder='入力してください']")
        await name_inputs.nth(0).fill(data['name'])
        print(f"\n👤 お名前: {data['name']}")

        # フリガナ
        await name_inputs.nth(1).fill(data['furigana'])
        print(f"📝 フリガナ: {data['furigana']}")

        # 会社名
        await name_inputs.nth(2).fill(data['company'])
        print(f"🏢 会社名: {data['company']}")

        # 部署（任意）
        if data.get('department'):
            await name_inputs.nth(3).fill(data['department'])
            print(f"🏪 部署: {data['department']}")

        # 電話番号
        await name_inputs.nth(4).fill(data['phone'])
        print(f"📞 電話番号: {data['phone']}")

        # メールアドレス
        await name_inputs.nth(5).fill(data['email'])
        print(f"📧 メールアドレス: {data['email']}")

        # お問い合わせ内容
        textarea = page.locator("textarea")
        await textarea.fill(data['inquiry_content'])
        print(f"💬 お問い合わせ内容: {data['inquiry_content'][:30]}...")

        # 個人情報の取扱いについて同意
        all_checkboxes = page.locator("input[type='checkbox']")
        checkbox_count = await all_checkboxes.count()
        await all_checkboxes.nth(checkbox_count - 1).check()
        print(f"✅ 個人情報の取扱いについて: 同意\n")

        # 送信ボタンをクリック
        submit_button = page.locator("button:has-text('入力内容を確認する')")
        await submit_button.click()
        print("📤 フォーム送信中...\n")

        # 確認画面待機
        await page.wait_for_timeout(2000)

        print("✅ フォーム送信完了\n")

        # ブラウザを3秒間開いたままにして確認
        await page.wait_for_timeout(3000)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(fill_form())
