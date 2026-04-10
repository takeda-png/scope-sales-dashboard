#!/usr/bin/env python3
"""
SCOPE営業パイプライン
companies.csv の pending 企業にフォーム送信する
"""
import asyncio
import csv
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

CONFIG_FILE = Path(__file__).parent / "config.json"
CSV_FILE = Path(__file__).parent / "companies.csv"

# お問い合わせページを示すキーワード
CONTACT_KEYWORDS = [
    "お問い合わせ", "お問合せ", "お問合わせ",
    "contact", "CONTACT", "Contact",
    "コンタクト", "ご相談", "ご連絡", "ご質問",
    "inquiry", "INQUIRY",
]

# フォームフィールド検出マッピング
FIELD_LABELS = {
    "name": ["お名前", "氏名", "名前", "お名前（漢字）", "姓名", "ご担当者名"],
    "furigana": ["ふりがな", "フリガナ", "カナ", "よみがな", "ふりがな（カタカナ）"],
    "company": ["会社名", "御社名", "企業名", "法人名", "貴社名", "会社・団体名"],
    "department": ["部署", "部署名", "所属", "役職・部署"],
    "phone": ["電話番号", "TEL", "Tel", "電話", "お電話番号", "携帯番号"],
    "email": ["メールアドレス", "メール", "E-mail", "email", "Email", "メールアドレス（確認）"],
}


def load_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_companies():
    if not CSV_FILE.exists():
        return []
    with open(CSV_FILE, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def update_company_status(url, status, contact_url="", note=""):
    companies = load_companies()
    for c in companies:
        if c["url"] == url:
            c["status"] = status
            c["submitted_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if contact_url:
                c["contact_url"] = contact_url
            if note:
                c["note"] = note
            break

    with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
        fieldnames = ["url", "company_name", "contact_url", "status", "submitted_at", "note"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(companies)


async def find_contact_url(page, base_url):
    """会社HPからお問い合わせページのURLを探す"""
    for keyword in CONTACT_KEYWORDS:
        try:
            links = page.locator(f"a:has-text('{keyword}')")
            count = await links.count()
            for i in range(count):
                link = links.nth(i)
                href = await link.get_attribute("href")
                if href:
                    return urljoin(base_url, href)
        except Exception:
            continue
    return None


async def try_fill_input(page, field_type, labels, value):
    """ラベル・プレースホルダー・name属性などでフィールドを特定して入力"""
    if not value:
        return False

    # 1. label for= 属性で探す
    for label_text in labels:
        try:
            label = page.locator(f"label:has-text('{label_text}')").first
            if await label.count() > 0:
                for_id = await label.get_attribute("for")
                if for_id:
                    inp = page.locator(f"#{for_id}").first
                    if await inp.count() > 0:
                        tag = await inp.evaluate("el => el.tagName.toLowerCase()")
                        if tag == "input":
                            await inp.fill(value)
                            return True
        except Exception:
            pass

    # 2. placeholder に含まれるキーワードで探す
    for label_text in labels:
        try:
            inp = page.locator(f"input[placeholder*='{label_text}']").first
            if await inp.count() > 0:
                await inp.fill(value)
                return True
        except Exception:
            pass

    # 3. name/id 属性で探す（英語）
    name_map = {
        "name": ["name", "full_name", "fullname", "your_name"],
        "furigana": ["kana", "furigana", "yomi"],
        "company": ["company", "company_name", "corp"],
        "department": ["department", "dept", "section"],
        "phone": ["phone", "tel", "telephone", "mobile"],
        "email": ["email", "mail", "e_mail"],
    }
    for attr_val in name_map.get(field_type, []):
        try:
            inp = page.locator(f"input[name*='{attr_val}'], input[id*='{attr_val}']").first
            if await inp.count() > 0:
                await inp.fill(value)
                return True
        except Exception:
            pass

    return False


async def fill_and_submit(page, config):
    """フォームを汎用的に入力して送信"""
    sender = config["sender"]
    filled = {}

    # 各フィールドを入力
    field_data = {
        "name": sender["name"],
        "furigana": sender["furigana"],
        "company": sender["company"],
        "department": sender.get("department", ""),
        "phone": sender["phone"],
        "email": sender["email"],
    }

    for field_type, labels in FIELD_LABELS.items():
        value = field_data.get(field_type, "")
        result = await try_fill_input(page, field_type, labels, value)
        filled[field_type] = result

    # お問い合わせ内容（textarea）
    try:
        textareas = page.locator("textarea")
        ta_count = await textareas.count()
        if ta_count > 0:
            await textareas.first.fill(config["message"])
            filled["message"] = True
    except Exception:
        filled["message"] = False

    # プライバシーポリシー同意チェックボックス（最後のチェックボックス）
    try:
        checkboxes = page.locator("input[type='checkbox']")
        cb_count = await checkboxes.count()
        if cb_count > 0:
            await checkboxes.nth(cb_count - 1).check()
            filled["privacy"] = True
    except Exception:
        filled["privacy"] = False

    # 送信ボタンを探してクリック
    submit_texts = ["送信", "確認", "次へ", "submit", "Submit", "送信する", "入力内容を確認"]
    submit_clicked = False
    for btn_text in submit_texts:
        try:
            btn = page.locator(
                f"button:has-text('{btn_text}'), input[type='submit'][value*='{btn_text}']"
            ).first
            if await btn.count() > 0:
                await btn.click()
                submit_clicked = True
                break
        except Exception:
            pass

    if not submit_clicked:
        # type=submitのボタンを試す
        try:
            btn = page.locator("input[type='submit'], button[type='submit']").first
            if await btn.count() > 0:
                await btn.click()
                submit_clicked = True
        except Exception:
            pass

    return filled, submit_clicked


async def process_company(page, company, config, delay):
    """1社分の処理"""
    url = company["url"]
    print(f"\n{'='*50}")
    print(f"🌐 {url}")

    try:
        # 会社HPにアクセス
        await page.goto(url, timeout=15000, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)

        # お問い合わせページを探す
        contact_url = await find_contact_url(page, url)
        if not contact_url:
            print("  ❌ お問い合わせページが見つかりません")
            update_company_status(url, "no_form", note="contact link not found")
            return False

        print(f"  📋 フォームページ: {contact_url}")

        # フォームページに移動
        await page.goto(contact_url, timeout=15000, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)

        # フォーム入力・送信
        filled, submitted = await fill_and_submit(page, config)
        filled_fields = [k for k, v in filled.items() if v]
        print(f"  ✅ 入力完了: {', '.join(filled_fields)}")

        if submitted:
            await page.wait_for_timeout(2000)
            print("  📤 送信完了")
            update_company_status(url, "submitted", contact_url=contact_url)
        else:
            print("  ⚠️ 送信ボタンが見つかりません（手動確認が必要）")
            update_company_status(url, "manual_check", contact_url=contact_url, note="submit button not found")

        await page.wait_for_timeout(delay * 1000)
        return submitted

    except PWTimeout:
        print(f"  ⏱️ タイムアウト")
        update_company_status(url, "error", note="timeout")
        return False
    except Exception as e:
        print(f"  ❌ エラー: {e}")
        update_company_status(url, "error", note=str(e)[:100])
        return False


async def run_pipeline():
    config = load_config()
    sub_cfg = config["submission"]
    companies = load_companies()

    pending = [c for c in companies if c.get("status") == "pending"]
    print(f"📊 pending: {len(pending)}件")

    if not pending:
        print("送信待ちの企業がありません。先に collect.py を実行してURLを収集してください。")
        return

    # 1セッションの上限
    batch = pending[:sub_cfg["max_per_session"]]
    print(f"🚀 今回の送信: {len(batch)}件\n")

    success = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=sub_cfg["headless"])
        page = await browser.new_page()
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        for company in batch:
            ok = await process_company(page, company, config, sub_cfg["delay_between_sites"])
            if ok:
                success += 1

        await browser.close()

    print(f"\n{'='*50}")
    print(f"✅ 完了: {success}/{len(batch)}件 送信成功")


if __name__ == "__main__":
    asyncio.run(run_pipeline())
