# -*- coding: utf-8 -*-
"""在活着的书签论坛里定位我们 10 个站的帖子链接（只读）。

新论坛是 SPA，帖子链接可能是 hash 路由或 topic.php?id=新ID。
输出：站名 +=> 候选链接列表 + 上下文。
"""
from __future__ import annotations

import json
import re
import ssl
from pathlib import Path
from urllib.request import Request, urlopen

OUT = Path(__file__).resolve().parent
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
ctx = ssl._create_unverified_context()

SITE_NAMES = [
    "坚持战斗", "无量寿佛", "再度归来", "童颜鹤发", "一心为民",
    "怪咖小生", "澳彩碼王", "寻宝探码", "财源滚滚", "海角天涯",
]

ALIVE = [
    "https://pa4dwcnd64.772149.shop",
    "https://i97lk4jb16.333741bbs1.shop",
    "https://5ipaulfv56.1081085bbs1.shop",
    "https://b7sz3gaw48.552149.shop",
    "https://z0gcdiww42.669332.shop",
    "https://bbs02.341627.cyou",
    "https://bbs06.933558.vip",
    "https://nlafoq9v.dh5565656.xyz",
]


def get(url: str, timeout: int = 20) -> str:
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=timeout, context=ctx) as r:
            raw = r.read()
    except Exception as exc:  # noqa: BLE001
        return f"__ERR__ {type(exc).__name__}: {str(exc)[:80]}"
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


report: dict[str, list[dict]] = {n: [] for n in SITE_NAMES}

for base in ALIVE:
    html = get(base + "/bbs/")
    if html.startswith("__ERR__"):
        print(f"SKIP {base} {html[:60]}")
        continue
    (OUT / f"forum_{re.sub(r'[^a-z0-9]+', '_', base.split('//')[1])}.html").write_text(
        html, encoding="utf-8"
    )
    for name in SITE_NAMES:
        for m in re.finditer(re.escape(name), html):
            s = m.start()
            seg = html[max(0, s - 600): s + 600]
            hrefs = re.findall(r'(?:href|data-href|onclick)="([^"]{3,200})"', seg)
            # 也抓 href 之外的 #xxx 路由
            hashes = re.findall(r'"(#[A-Za-z0-9/_.=-]{2,80})"', seg)
            if hrefs or hashes:
                report[name].append({
                    "base": base,
                    "hrefs": hrefs[:6],
                    "hashes": hashes[:6],
                    "ctx": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", seg))[:200],
                })

for name in SITE_NAMES:
    print(f"\n=== {name}  命中 {len(report[name])} 处")
    seen = set()
    for r in report[name][:4]:
        key = (r["base"], tuple(r["hrefs"]), tuple(r["hashes"]))
        if key in seen:
            continue
        seen.add(key)
        print(f"  base={r['base']}")
        print(f"    hrefs={r['hrefs']}")
        print(f"    hashes={r['hashes']}")
        print(f"    ctx={r['ctx'][:160]}")

(OUT / "site_links_294.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
