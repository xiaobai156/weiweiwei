# -*- coding: utf-8 -*-
"""扩散扫描：所有书签里活着的 bbs 论坛，抓帖子标题，找我们 10 个站 + 杀尾栏目（只读）。"""
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

# 书签里的 bbs 论坛 + 从活站外链挖到的 .shop/.top 论坛
BASES = [
    "https://pa4dwcnd64.772149.shop",
    "https://i97lk4jb16.333741bbs1.shop",
    "https://5ipaulfv56.1081085bbs1.shop",
    "https://b7sz3gaw48.552149.shop",
    "https://z0gcdiww42.669332.shop",
    "https://bbs02.341627.cyou",
    "https://bbs06.933558.vip",
    "https://nlafoq9v.dh5565656.xyz",
    "https://2k7az34b71.669332.shop",
    "https://6xrvz.992148.shop",
    "https://gimam.552148.shop",
    "https://gydlhtca7.998994.shop",
    "https://h2kv0esm15.772149.shop",
    "https://txn.772148.shop",
    "https://uubve.662194.shop",
    "https://dtn0csgk43.1081085bbs1.shop",
    "https://tkjcodn376.566369bbs1.shop",
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


summary = []
for base in BASES:
    html = get(base + "/bbs/")
    if not html:
        print(f"DEAD  {base}")
        continue
    titles = [
        (tid, re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inner)).strip())
        for href, tid, inner in re.findall(
            r'<a[^>]+href="([^"]*topic\.php\?id=(\d+)[^"]*)"[^>]*>(.*?)</a>',
            html, re.I | re.S,
        )
    ]
    plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    site_hits = [s for s in SITES if s in plain]
    tail_titles = [(t, s) for t, s in titles if "尾" in s]
    ours_tail = [(t, s) for t, s in tail_titles if any(x in s for x in SITES)]
    summary.append({
        "base": base,
        "titles": len(titles),
        "site_hits": site_hits,
        "tail_count": len(tail_titles),
        "ours_tail": ours_tail,
    })
    print(f"\nOK {base}  标题 {len(titles)}  含我们站名 {site_hits}")
    if tail_titles:
        print(f"   含尾标题 {len(tail_titles)} 条，示例:")
        for t, s in tail_titles[:5]:
            print(f"     id={t} {s[:70]}")
    if ours_tail:
        print(f"   ★ 我们站 + 尾栏目 {len(ours_tail)} 条:")
        for t, s in ours_tail[:10]:
            print(f"     id={t} {s[:80]}")

print("\n\n=== 汇总：哪些论坛出现我们的站名 ===")
for r in summary:
    if r["site_hits"]:
        print(f"  {r['base']}  -> {r['site_hits']}")

(OUT / "spread_scan_294.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
)
