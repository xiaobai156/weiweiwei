# -*- coding: utf-8 -*-
"""精确核对：所有活论坛的「帖子标题」里，是否有我们 10 个站的杀尾坛（只读）。"""
from __future__ import annotations

import json
import re
import ssl
from pathlib import Path
from urllib.request import Request, urlopen

OUT = Path(__file__).resolve().parent
ctx = ssl._create_unverified_context()
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
SITES = [
    "坚持战斗", "无量寿佛", "再度归来", "童颜鹤发", "一心为民",
    "怪咖小生", "澳彩碼王", "寻宝探码", "财源滚滚", "海角天涯",
]
BASES = [
    "https://pa4dwcnd64.772149.shop", "https://i97lk4jb16.333741bbs1.shop",
    "https://5ipaulfv56.1081085bbs1.shop", "https://b7sz3gaw48.552149.shop",
    "https://z0gcdiww42.669332.shop", "https://bbs02.341627.cyou",
    "https://bbs06.933558.vip", "https://nlafoq9v.dh5565656.xyz",
    "https://2k7az34b71.669332.shop", "https://h2kv0esm15.772149.shop",
    "https://dtn0csgk43.1081085bbs1.shop", "https://tkjcodn376.566369bbs1.shop",
]


def get(url: str, timeout: int = 18) -> str:
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=timeout, context=ctx) as r:
            raw = r.read()
    except Exception:  # noqa: BLE001
        return ""
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


rows = []
for base in BASES:
    html = get(base + "/bbs/")
    if not html:
        continue
    for href, tid, inner in re.findall(
        r'<a[^>]+href="([^"]*topic\.php\?id=(\d+)[^"]*)"[^>]*>(.*?)</a>',
        html, re.I | re.S,
    ):
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inner)).strip()
        if not title:
            continue
        rows.append({"base": base, "tid": tid, "title": title})

print("标题总数", len(rows))
print("\n=== 标题含我们站名的 ===")
found_any = False
for site in SITES:
    hits = [r for r in rows if site in r["title"]]
    if hits:
        found_any = True
        print(f"\n{site}: {len(hits)} 条")
        seen = set()
        for h in hits:
            if h["title"] in seen:
                continue
            seen.add(h["title"])
            print(f"   {h['base']}  id={h['tid']}  {h['title'][:80]}")
if not found_any:
    print("  （无）")

print("\n=== 标题含「绝杀一尾」且含我们站名的 ===")
strict = [r for r in rows if "绝杀一尾" in r["title"] and any(s in r["title"] for s in SITES)]
print("  命中", len(strict))
for r in strict:
    print(f"   {r['base']} id={r['tid']} {r['title'][:90]}")

(OUT / "title_check_294.json").write_text(
    json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
)
