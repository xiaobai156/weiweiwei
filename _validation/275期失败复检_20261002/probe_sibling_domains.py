# -*- coding: utf-8 -*-
"""只读旁证：同论坛(小仙女288060com)其他域名实例首页是否还存在「潇洒人生」275期帖。
仅 HTTP GET，不写任何正式文件。"""
import io, json, re, ssl, urllib.request, socket

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
socket.setdefaulttimeout(25)

DOMAINS = [
    "https://12388990827.794555.xyz",
    "https://12388990827.688756.xyz",
    "https://88888020827.897657.xyz",
    "https://88888020827.997595.xyz",
    "https://0130190827.767566.xyz",
]
KEYS = ["潇洒人生", "潇洒", "潇洒人生"]

out = []
for base in DOMAINS:
    rec = {"domain": base}
    try:
        url = base + "/bbs/index.php"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, context=CTX) as r:
            raw = r.read()
            rec["status"] = r.status
            rec["len"] = len(raw)
        html = raw.decode("gb2312", "replace")
        rec["has_xiaosa"] = "潇洒人生" in html
        rec["has_xiaosa_any"] = "潇洒" in html
        rec["has_275"] = "275期" in html
        ids = re.findall(r'topic\.php\?id=(\d+)', html)
        rec["topic_ids"] = len(ids)
        rec["id_min"] = min(ids) if ids else None
        rec["id_max"] = max(ids) if ids else None
        # 抓 275 期行的作者名，与站点名比对
        authors = re.findall(r'275期：【([^🔴<\]]+)', html)
        rec["authors_275_count"] = len(authors)
        rec["xiaosa_author_hit"] = [a for a in authors if "潇洒" in a]
        rec["sample_authors"] = authors[:5]
        rec["title"] = (re.search(r"<title>(.*?)</title>", html) or [None, ""])[1]
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
    out.append(rec)
    print(json.dumps(rec, ensure_ascii=False))

with io.open("probe_sibling_domains_out.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("saved probe_sibling_domains_out.json")
