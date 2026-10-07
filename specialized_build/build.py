"""Stage3: 除外条件を当てて CSV を出す
  specialized_agencies.csv          … 採用（既存リストと同じ列＋制作実績数・情報源・特化業界）
  specialized_agencies_excluded.csv … 除外した会社と理由（手動確認用）
"""
import csv, json, re, sys
from collections import Counter
from enrich import domain
from collect import SRC_LABEL

OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else "."
EXISTING = r"C:\Users\taked\Desktop\companies_with_form.csv"           # 既存の制作会社リスト
SCOPE_SENT = r"C:\Users\taked\Desktop\form-automation\companies.csv"   # SCOPE営業の送信リスト（参考）
SLUG = dict(zip("hokkaido aomori iwate miyagi akita yamagata fukushima ibaraki tochigi gunma saitama chiba tokyo kanagawa niigata toyama ishikawa fukui yamanashi nagano gifu shizuoka aichi mie shiga kyoto osaka hyogo nara wakayama tottori shimane okayama hiroshima yamaguchi tokushima kagawa ehime kochi fukuoka saga nagasaki kumamoto oita miyazaki kagoshima okinawa".split(),
    "北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県".split()))
ORDER = ["歯科", "整骨院・整体院・治療院", "製造業", "介護・福祉"]
COLS = ["会社名", "コーポレートURL", "お問い合わせフォームURL", "所在地", "従業員数", "電話番号", "BaseconnectURL",
        "制作実績数", "情報源", "特化業界"]


# 制作会社ではない／明らかに大規模（従業員数が取れなかったため手動で除外）
MANUAL_DROP = {"株式会社ニチイ学館": "従業員100名以上（大手介護事業者・制作会社ではない）",
               "公益財団法人介護労働安定センター": "制作会社ではない（公益財団法人）",
               "ケアミックス株式会社": "制作会社ではない（老人ホーム紹介等が本業）"}


def nkey(x):
    return re.sub(r"[\s　]|株式会社|有限会社|合同会社", "", x)


def emp_lower(s):
    s = (s or "").replace(",", "").replace("，", "")
    s = s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else None


def main():
    ex = list(csv.DictReader(open(EXISTING, encoding="utf-8-sig")))
    ex_dom = {domain(r[k]) for r in ex for k in ("コーポレートURL", "お問い合わせフォームURL") if r.get(k, "").startswith("http")}
    ex_dom.discard("")
    ex_names = {re.sub(r"\s|株式会社|有限会社|合同会社", "", r["会社名"]) for r in ex}
    sc_dom = {domain(r["url"]) for r in csv.DictReader(open(SCOPE_SENT, encoding="utf-8-sig", errors="replace")) if r.get("url")}

    gs = json.load(open("enriched.json", encoding="utf-8"))
    keep, drop = [], []
    reasons = Counter()
    for g in gs:
        rec0 = g["recs"][0]
        name = rec0["name"]
        emp = next((r.get("employees") for r in g["recs"] if r.get("employees")), "") or g.get("emp_site", "")
        pref = next((r.get("pref") for r in g["recs"] if r.get("pref")), "") or             next((SLUG.get(r.get("pref_slug", "")) for r in g["recs"] if SLUG.get(r.get("pref_slug", ""))), "")
        works = g.get("works_site") or next((r.get("works_dir") for r in g["recs"] if r.get("works_dir")), "")
        srcs = "／".join(sorted({f"{SRC_LABEL[r['src']]}({r['industry']})" for r in g["recs"]}))
        row = {"会社名": name, "コーポレートURL": g.get("url", ""), "お問い合わせフォームURL": g.get("form", ""),
               "所在地": pref, "従業員数": emp, "電話番号": "", "BaseconnectURL": "",
               "制作実績数": works, "情報源": srcs,
               "特化業界": "／".join(i for i in ORDER if i in g.get("spec", []))}
        nm = re.sub(r"\s|株式会社|有限会社|合同会社", "", name)
        lo = emp_lower(emp)
        if not g.get("url"):
            r = "公式URL不明"
        elif g.get("top_status") != 200:
            r = f"公式サイト取得不可({g.get('top_status')})"
        elif name in MANUAL_DROP:
            r = MANUAL_DROP[name]
        elif g["domain"] in ex_dom or nm in ex_names:
            r = "既存190社リストと重複"
        elif lo is not None and lo >= 100:
            r = "従業員100名以上"
        elif g["domain"] in sc_dom:
            r = "SCOPE営業の送信リストと重複"
        elif not g.get("spec"):
            r = "特化を名乗っていない（対応可能止まり）"
        else:
            keep.append(row); continue
        reasons[r.split("(")[0]] += 1
        drop.append({**row, "候補だった業界": "／".join(g["industries"]), "除外理由": r, "判定メモ": g.get("judge", ""),
                     "公式トップ見出し": g.get("head", "")[:150]})

    # 同じ会社で業界専用ドメインが別にある場合は1行にまとめる（特化業界・情報源は合算、URLは先の行）
    merged = {}
    for r in keep:
        k = nkey(r["会社名"])
        if k not in merged:
            merged[k] = r; continue
        m = merged[k]
        for c in ("特化業界", "情報源"):
            m[c] = "／".join(dict.fromkeys([x for x in (m[c] + "／" + r[c]).split("／") if x]))
        for c in ("お問い合わせフォームURL", "所在地", "従業員数", "制作実績数"):
            m[c] = m[c] or r[c]
        reasons["同一社の別ドメイン（統合）"] += 1
    keep = list(merged.values())
    keep.sort(key=lambda r: (min([ORDER.index(i) for i in r["特化業界"].split("／") if i in ORDER] or [9]), r["所在地"], r["会社名"]))
    with open(f"{OUT_DIR}/specialized_agencies.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(keep)
    dcols = COLS + ["候補だった業界", "除外理由", "判定メモ", "公式トップ見出し"]
    with open(f"{OUT_DIR}/specialized_agencies_excluded.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=dcols); w.writeheader(); w.writerows(drop)

    print(f"候補（ドメイン名寄せ後）: {len(gs)}社 / 採用: {len(keep)}社 / 除外: {len(drop)}社")
    for k, v in reasons.most_common():
        print(f"  除外 {k}: {v}")
    print("業界別（採用・複数業界は重複カウント）:")
    for i in ORDER:
        print(f"  {i}: {sum(1 for r in keep if i in r['特化業界'])}")
    print("フォームURLあり:", sum(1 for r in keep if r["お問い合わせフォームURL"]), "/ 空欄:", sum(1 for r in keep if not r["お問い合わせフォームURL"]))
    print("従業員数あり:", sum(1 for r in keep if r["従業員数"]), "/ 実績数あり:", sum(1 for r in keep if r["制作実績数"]))


if __name__ == "__main__":
    main()
