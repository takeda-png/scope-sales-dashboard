"""Stage1: 4サイトの一覧記事から候補を抜き、各サイトの会社詳細ページで URL・所在地・従業員数などを取る
出力: candidates.json（1社×1情報源 = 1レコード。名寄せは enrich/build 側）
"""
import json, re, sys
from bs4 import BeautifulSoup
from fetch import get

PREFS = "北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|奈良県|和歌山県|鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|佐賀県|長崎県|熊本県|大分県|宮崎県|鹿児島県|沖縄県"
PREF_RE = re.compile(PREFS)

DENT, SEIK, MANU, NURS = "歯科", "整骨院・整体院・治療院", "製造業", "介護・福祉"

SOURCES = [
    ("biz", "https://www.biz.ne.jp/matome/2003008/", DENT),
    ("biz", "https://www.biz.ne.jp/matome/2003015/", SEIK),
    ("biz", "https://www.biz.ne.jp/matome/2003017/", NURS),
    ("imitsu", "https://imitsu.jp/list/hp-design/dental-clinic/", DENT),
    ("imitsu", "https://imitsu.jp/list/hp-design/seitai/", SEIK),
    ("imitsu", "https://imitsu.jp/list/hp-design/manufacturer/", MANU),
    ("imitsu", "https://imitsu.jp/list/hp-design/nursing/", NURS),
    ("webkanji", "https://web-kanji.com/posts/dental-clinic", DENT),
    ("webkanji", "https://web-kanji.com/posts/dental-clinic-homepage-design", DENT),
    ("webkanji", "https://web-kanji.com/posts/osteopathic-clinic", SEIK),
    ("webkanji", "https://web-kanji.com/posts/acupuncture-and-moxibustion-clinic", SEIK),
    ("webkanji", "https://web-kanji.com/posts/manufacturing", MANU),
    ("webkanji", "https://web-kanji.com/posts/manufacturing-homepage-design", MANU),
    ("webkanji", "https://web-kanji.com/posts/nursing", NURS),
    ("webkanji", "https://web-kanji.com/posts/nursing-homepage-design", NURS),
    ("hnavi", "https://hnavi.co.jp/knowledge/blog/nursing_hp_companies/", NURS),
    ("hnavi", "https://hnavi.co.jp/knowledge/blog/manufacturing-hp_companies/", MANU),
]
SRC_LABEL = {"biz": "比較ビズ", "imitsu": "アイミツ", "webkanji": "Web幹事", "hnavi": "発注ナビ"}


def clean_name(t):
    t = re.sub(r"^[●■◆◎・\d０-９]+[\.．、)）]?\s*", "", t.strip())
    t = re.sub(r"[（(].*?[）)]$", "", t).strip()
    return t


def block(h):
    """h3 から次の h2/h3 までのノード列"""
    out = []
    for n in h.next_elements:
        if getattr(n, "name", None) in ("h2", "h3") and n is not h:
            break
        out.append(n)
    return out


def section_of(h):
    p = h.find_previous("h2")
    return p.get_text(" ", strip=True) if p else ""


def kv_table(soup):
    d = {}
    for th in soup.find_all(["th", "dt"]):
        td = th.find_next_sibling(["td", "dd"])
        if td:
            k = th.get_text(strip=True)
            d.setdefault(k, td.get_text(" ", strip=True))
    return d


def pref_of(s):
    m = PREF_RE.search(s or "")
    return m.group(0) if m else ""


# ---------------- 一覧ページの解析 ----------------
def parse_list(kind, url, industry):
    st, fu, t = get(url)
    if st != 200:
        print("  !! list", st, url)
        return []
    s = BeautifulSoup(t, "html.parser")
    rows = []
    for h in s.find_all("h3"):
        nodes = block(h)
        links = [n.get("href", "") for n in nodes if getattr(n, "name", None) == "a"]
        name = clean_name(h.get_text(" ", strip=True))
        rec = {"name": name, "src": kind, "list_url": url, "industry": industry, "section": section_of(h)}
        if kind == "biz":
            det = [l for l in links if re.match(r"^/corporation/\d+/?$", l)]
            if not det:
                continue
            rec["detail"] = "https://www.biz.ne.jp" + det[0]
        elif kind == "imitsu":
            det = [l for l in links if "/supplier/" in l]
            if not det:
                continue
            rec["detail"] = re.sub(r"[#/]service.*$", "", det[0].split("#")[0])
            ext = [l for l in links if l.startswith("http") and "imitsu.jp" not in l and "wevery" not in l]
            if ext:
                rec["url"] = ext[0]
            m = re.search(r"/pr-([a-z]+)/", det[0])
            rec["pref_slug"] = m.group(1) if m else ""
        elif kind == "webkanji":
            tb = next((n for n in nodes if getattr(n, "name", None) == "table"), None)
            if not tb:
                continue
            for tr in tb.find_all("tr"):
                c = [x.get_text(" ", strip=True) for x in tr.find_all(["td", "th"])]
                if len(c) >= 2 and c[0] == "URL":
                    rec["url"] = c[1]
                if len(c) >= 2 and c[0] == "会社所在地":
                    rec["address"] = c[1]
            det = [l for l in links if re.search(r"/companies/[a-z0-9\-]+$", l) and not re.search(r"/(industries|objects|features)$", l)]
            if det:
                rec["detail"] = det[0] if det[0].startswith("http") else "https://web-kanji.com" + det[0]
            ext = [l.split("?")[0] for l in links if l.startswith("http") and "web-kanji.com" not in l]
            if ext:
                rec["page"] = ext[0]  # 業界専用ページのことがある（例 /manufacture/）
                if not rec.get("url"):
                    rec["url_guess"] = re.sub(r"^(https?://[^/]+).*$", r"/", ext[0])
            if not (rec.get("url") or rec.get("detail") or rec.get("url_guess")):
                continue
        elif kind == "hnavi":
            det = [l for l in links if re.search(r"/corporation/\d+/?$", l)]
            if not det:
                continue
            rec["detail"] = det[0]
            tbl = {}
            for n in nodes:
                if getattr(n, "name", None) == "th":
                    td = n.find_next_sibling("td")
                    if td:
                        tbl[n.get_text(strip=True)] = td.get_text(" ", strip=True)
            rec["address"] = tbl.get("会社所在地", "")
        rows.append(rec)
    print(f"  {SRC_LABEL[kind]} {industry}: {len(rows)}社  {url}")
    return rows


# ---------------- 詳細ページ ----------------
def enrich_detail(rec):
    u = rec.get("detail")
    if not u:
        return
    st, fu, t = get(u)
    if st != 200:
        rec["detail_status"] = st
        return
    s = BeautifulSoup(t, "html.parser")
    kv = kv_table(s)
    tx = s.get_text(" ", strip=True)
    k = rec["src"]
    if k == "biz":
        rec["url"] = kv.get("URL", "") or rec.get("url", "")
        rec["address"] = kv.get("所在地", "")
        rec["employees"] = kv.get("従業員数", "")
        rec["business"] = kv.get("事業内容", "")
    elif k == "imitsu":
        rec["url"] = kv.get("会社URL", "") or kv.get("サービスURL", "") or rec.get("url", "")
        rec["address"] = kv.get("住所", "")
        rec["industries"] = kv.get("対応可能な業界", "")
        rec["business"] = kv.get("会社概要", "")
        m = re.search(r"実績・事例（(\d+)件", tx)
        if m:
            rec["works_dir"] = f"{m.group(1)}（アイミツ掲載）"
    elif k == "webkanji":
        m = re.search(r"対応業界 (.*?) 特徴 ", tx)
        rec["industries"] = m.group(1) if m else ""
        m = re.search(r"所在地 (.*?) 対応サイト", tx)
        if m and not rec.get("address"):
            rec["address"] = m.group(1)
        m = re.search(r"URL (https?://\S+)", tx)
        if m and "web-kanji.com" not in m.group(1):
            rec["url"] = rec.get("url") or m.group(1)
        m = re.search(r"制作実績\s*[（(]?\s*(\d[\d,]*)\s*件", tx)
        if m:
            rec["works_dir"] = f"{m.group(1)}（Web幹事掲載）"
    elif k == "hnavi":
        m = re.search(r"従業員数 (\S+)", tx)
        rec["employees"] = m.group(1) if m else ""
        m = re.search(r"ホームページ (https?://\S+)", tx)
        if m:
            rec["url"] = m.group(1)
        if not rec.get("address"):
            m = re.search(r"所在地 (\S+ \S+)", tx)
            rec["address"] = m.group(1) if m else ""


def main():
    allrec = []
    for kind, url, ind in SOURCES:
        allrec += parse_list(kind, url, ind)
    print("候補レコード:", len(allrec))
    for i, r in enumerate(allrec, 1):
        enrich_detail(r)
        if i % 20 == 0:
            print(f"  detail {i}/{len(allrec)}", flush=True)
    for r in allrec:
        if not r.get("url") and r.get("url_guess"):
            r["url"] = r["url_guess"]
        r["pref"] = pref_of(r.get("address", ""))
    json.dump(allrec, open("candidates.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved candidates.json", len(allrec))


if __name__ == "__main__":
    main()
