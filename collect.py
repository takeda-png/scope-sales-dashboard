#!/usr/bin/env python3
"""
Google検索で埼玉県内の企業HPを収集し companies.csv に追記する
"""
import asyncio
import csv
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright

CONFIG_FILE = Path(__file__).parent / "config.json"
CSV_FILE = Path(__file__).parent / "companies.csv"


def load_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_existing_urls():
    if not CSV_FILE.exists():
        return set()
    with open(CSV_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["url"] for row in reader if row.get("url")}


def save_company(url, company_name=""):
    with open(CSV_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([url, company_name, "", "pending", "", ""])


def is_valid_company_url(url, exclude_domains):
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # 除外ドメインチェック
        for excl in exclude_domains:
            if excl in domain:
                return False
        # .co.jp / .com / .jp などの企業ドメインのみ
        if not any(parsed.scheme.startswith(s) for s in ["http", "https"]):
            return False
        # GoogleのキャッシュURLなどを除外
        if "google" in domain or "cache" in url:
            return False
        return True
    except Exception:
        return False


def extract_base_url(url):
    """サブページをトップページに変換"""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"


async def search_google(page, query, max_results=10, exclude_domains=None):
    """Google検索して企業URLを収集"""
    exclude_domains = exclude_domains or []
    urls = []

    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&num={max_results}"
    print(f"  🔍 検索: {query}")

    try:
        await page.goto(search_url, timeout=15000)
        await page.wait_for_timeout(2000)

        # 検索結果のリンクを取得
        links = await page.locator("a[href]").all()
        for link in links:
            try:
                href = await link.get_attribute("href")
                if not href:
                    continue
                # Google検索結果の実URLを抽出
                if href.startswith("/url?q="):
                    href = href.split("/url?q=")[1].split("&")[0]
                if href.startswith("http") and is_valid_company_url(href, exclude_domains):
                    base = extract_base_url(href)
                    if base not in urls:
                        urls.append(base)
                        if len(urls) >= max_results:
                            break
            except Exception:
                continue

    except Exception as e:
        print(f"  ⚠️ 検索エラー: {e}")

    return urls


async def collect():
    config = load_config()
    existing_urls = load_existing_urls()
    search_cfg = config["search"]

    new_count = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # User-Agentを一般ブラウザに偽装
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        for query in search_cfg["queries"]:
            urls = await search_google(
                page,
                query,
                max_results=search_cfg["results_per_query"],
                exclude_domains=search_cfg["exclude_domains"]
            )

            for url in urls:
                if url not in existing_urls:
                    save_company(url)
                    existing_urls.add(url)
                    new_count += 1
                    print(f"    ✅ 追加: {url}")
                else:
                    print(f"    ⏭️  既存: {url}")

            # 検索間の待機（Googleへの負荷軽減）
            await page.wait_for_timeout(3000)

        await browser.close()

    print(f"\n📊 収集完了: {new_count}件追加 / 合計 {len(existing_urls)}件")


if __name__ == "__main__":
    asyncio.run(collect())
