"""Stage2: ドメインで名寄せ → 各社の公式サイトを1〜数ページ見て
  ・特化判定（トップの title/description/h1 に業界語があるか、本文に「◯◯専門/特化」とあるか）
  ・お問い合わせフォームURL（contact/inquiry/お問い合わせ を探索。無ければ空欄）
  ・従業員数／制作実績数の補完
出力: enriched.json
"""
import json, re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from fetch import get

KW = {
    "歯科": ["歯科", "デンタル", "dental", "歯医者"],
    "整骨院・整体院・治療院": ["整骨", "接骨", "整体", "治療院", "鍼灸", "柔整", "カイロプラクティック"],
    "製造業": ["製造業", "メーカー", "ものづくり", "モノづくり", "工場", "製造"],
    "介護・福祉": ["介護", "福祉", "老人ホーム", "デイサービス", "高齢者施設"],
}
OTHER = ["建設", "建築", "不動産", "工務店", "住宅", "飲食", "美容", "サロン", "士業", "税理士", "弁護士",
         "学校", "教育", "ホテル", "旅館", "小売", "物流", "IT企業", "病院", "クリニック", "医療",
         "歯科", "整骨", "製造", "介護", "福祉"]
MEDICAL = {"病院", "クリニック", "医療", "歯科", "整骨", "介護", "福祉"}
CONTACT_WORDS = ["contact", "inquiry", "toiawase", "otoiawase", "お問い合わせ", "問い合わせ", "お問合わせ", "お問合せ", "問合せ"]
FALLBACK = ["/contact/", "/contact", "/inquiry/", "/contact.html", "/otoiawase/", "/toiawase/"]
DIR_HOSTS = ("biz.ne.jp", "imitsu.jp", "web-kanji.com", "hnavi.co.jp")


def domain(u):
    try:
        h = urlparse(u if "://" in u else "http://" + u).netloc.lower()
    except Exception:
        return ""
    h = h.split(":")[0]
    return h[4:] if h.startswith("www.") else h


def head_text(s):
    parts = [s.title.get_text(" ", strip=True) if s.title else ""]
    for m in s.find_all("meta"):
        if (m.get("name") or m.get("property") or "").lower() in ("description", "og:description", "og:title", "keywords"):
            parts.append(m.get("content", ""))
    for h in s.find_all(["h1"])[:3]:
        parts.append(h.get_text(" ", strip=True))
    return " ".join(parts)


def judge(industries, head, body):
    """戻り: (特化業界list, 判定メモ)"""
    hl, bl = head.lower(), body.lower()
    hit, notes = [], []
    for ind in industries:
        kws = KW[ind]
        in_head = any(k.lower() in hl for k in kws)
        claim = any(re.search(rf"{re.escape(k)}[^。\n]{{0,15}}(特化|専門|専業|に強い)|(特化|専門)[^。\n]{{0,15}}{re.escape(k)}", body, re.I) for k in kws)
        if in_head or claim:
            others = {o for o in OTHER if o in head and not any(o in k or k in o for k in kws)}
            if ind != "製造業":
                others -= MEDICAL
            if in_head and not claim and len(others) >= 3:
                notes.append(f"{ind}:業種を幅広く列挙({'/'.join(sorted(others))[:40]})")
                continue
            hit.append(ind)
            notes.append(f"{ind}:{'トップ見出し' if in_head else ''}{'+' if in_head and claim else ''}{'本文で特化/専門' if claim else ''}")
        else:
            notes.append(f"{ind}:公式トップに業界の明記なし")
    return hit, " / ".join(notes)


def find_form(top_url, s):
    root = "{0.scheme}://{0.netloc}".format(urlparse(top_url))
    dom = domain(top_url)
    cands = []
    for a in s.find_all("a", href=True):
        href, txt = a["href"].strip(), a.get_text(" ", strip=True)
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        if any(w in href.lower() or w in txt.lower() for w in CONTACT_WORDS):
            full = urljoin(top_url, href)
            if domain(full) == dom or dom in domain(full):
                cands.append(full)
    if cands:
        # recruit/採用 系を後ろに回す
        cands.sort(key=lambda u: ("recruit" in u or "entry" in u, len(u)))
        return cands[0]
    for p in FALLBACK:
        st, fu, t = get(root + p)
        if st == 200 and re.search(r"<form", t, re.I) and domain(fu) == dom:
            return fu
    return ""


def emp_from(text):
    m = re.search(r"従業員数?[\s:：]*([0-9０-９,，]+)\s*(名|人)", text)
    return f"{m.group(1)}{m.group(2)}" if m else ""


def works_from(text):
    pats = [r"(?:制作|導入|支援)?実績[^\d。]{0,10}?([0-9,]{2,7})\s*(件|院|社|サイト|医院|施設)",
            r"([0-9,]{2,7})\s*(件|院|社|サイト|医院|施設)以上の(?:制作|導入|支援)?実績"]
    for p in pats:
        m = re.search(p, text)
        if m:
            return f"{m.group(1)}{m.group(2)}（公式サイト記載）"
    return ""


def company_page(top_url, s):
    for a in s.find_all("a", href=True):
        t = a.get_text(" ", strip=True)
        h = a["href"].lower()
        if any(w in t for w in ("会社概要", "会社案内", "企業情報", "会社情報")) or re.search(r"/(company|about|corporate|outline|profile)(/|\.html|$)", h):
            u = urljoin(top_url, a["href"])
            if domain(u) == domain(top_url):
                return u
    return ""


def main():
    recs = json.load(open("candidates.json", encoding="utf-8"))
    def nn(x):
        return re.sub(r"[\s　]|株式会社|有限会社|合同会社|一般社団法人|（.*?）|\(.*?\)", "", x).lower()
    groups, byname = {}, {}
    def add(d, r, u):
        g = groups.setdefault(d, {"domain": d, "names": [], "urls": [], "industries": [], "srcs": [], "recs": []})
        g["names"].append(r["name"]); g["urls"].append(u); g["recs"].append(r)
        if r["industry"] not in g["industries"]:
            g["industries"].append(r["industry"])
        if r["src"] not in g["srcs"]:
            g["srcs"].append(r["src"])
        byname.setdefault(nn(r["name"]), d)
    later = []
    for r in recs:
        u = (r.get("url") or "").strip()
        d = domain(u)
        if not d or any(h in d for h in DIR_HOSTS):
            later.append(r); continue
        add(d, r, u)
    for r in later:
        add(byname.get(nn(r["name"]), "noname:" + r["name"]), r, "")
    out = []
    keys = list(groups)
    for i, d in enumerate(keys, 1):
        g = groups[d]
        url = next((u for u in g["urls"] if u.startswith("http")), "")
        g["url"] = url
        if not url:
            g["note"] = "公式URL不明"
            out.append(g); continue
        st, fu, t = get(url)
        g["top_status"] = st
        if st != 200:
            g["note"] = f"公式サイト取得不可({st})"
            out.append(g); continue
        s = BeautifulSoup(t, "html.parser")
        body = s.get_text(" ", strip=True)
        g["head"] = head_text(s)[:300]
        g["spec"], g["judge"] = judge(g["industries"], g["head"], body)
        # 業界専用ページ（例 /manufacture/）がディレクトリで紹介されていれば、そちらでも判定
        pages = {r.get("page") for r in g["recs"] if r.get("page") and urlparse(r["page"]).path.strip("/")
                 and domain(r["page"]) == d}
        for pg in list(pages)[:2]:
            stp, _, tp = get(pg)
            if stp == 200:
                sp = BeautifulSoup(tp, "html.parser")
                h2, n2 = judge(g["industries"], head_text(sp), sp.get_text(" ", strip=True))
                add2 = [x for x in h2 if x not in g["spec"]]
                if add2:
                    g["spec"] += add2
                    g["judge"] += f" / 業界専用ページあり({pg}):" + "・".join(add2)
        g["form"] = find_form(fu, s)
        g["emp_site"] = emp_from(body)
        g["works_site"] = works_from(body)
        if not g["emp_site"]:
            cp = company_page(fu, s)
            if cp:
                st2, _, t2 = get(cp)
                if st2 == 200:
                    tx2 = BeautifulSoup(t2, "html.parser").get_text(" ", strip=True)
                    g["emp_site"] = emp_from(tx2)
                    if not g["works_site"]:
                        g["works_site"] = works_from(tx2)
        out.append(g)
        if i % 10 == 0:
            print(f"  {i}/{len(keys)}", flush=True)
            json.dump(out, open("enriched.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(out, open("enriched.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved enriched.json", len(out))


if __name__ == "__main__":
    main()
