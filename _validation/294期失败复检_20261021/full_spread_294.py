# -*- coding: utf-8 -*-
"""全量扩散：把书签里 345 个域名全部测活，活着的抓 /bbs/ 帖子标题，
找我们 10 个缺失站的杀尾帖（只读，并发）。
"""
from __future__ import annotations

import json
import re
import ssl
from concurrent.futures import ThreadPoolExecutor
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

data = json.loads((OUT / "bookmark_hosts_all.json").read_text(encoding="utf-8"))
hosts = list(data["entries"].keys())
print("书签域名数", len(hosts))

# 只测可能是论坛的（带端口 / .shop / .top / .cyou / .vip / .xyz / .work）
cands = [
    h for h in hosts
    if re.search(r"\.(shop|top|cyou|vip|xyz|work|cc)$", h) or re.search(r":\d{2,5}$", h)
]
print("候选域名", len(cands))


def get(url: str, timeout: int = 12) -> str:
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


def probe(host: str) -> dict | None:
    for scheme in ("https", "http"):
        base = f"{scheme}://{host}"
        for path in ("/bbs/", "/bbs/index.php", "/"):
            html = get(base + path)
            if not html or len(html) < 500:
                continue
            titles = [
                (tid, re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inner)).strip())
                for href, tid, inner in re.findall(
                    r'<a[^>]+href="([^"]*topic\.php\?id=(\d+)[^"]*)"[^>]*>(.*?)</a>',
                    html, re.I | re.S,
                )
            ]
            if not titles:
                continue
            ours = [
                (tid, t) for tid, t in titles
                if any(s in t for s in SITES) and "尾" in t
            ]
            return {
                "host": host,
                "base": base,
                "path": path,
                "titles": len(titles),
                "our_tail": ours[:10],
            }
    return None


results = []
with ThreadPoolExecutor(max_workers=12) as pool:
    for r in pool.map(probe, cands):
        if r:
            results.append(r)
            print(f"\nOK {r['base']}{r['path']}  标题 {r['titles']}")
            if r["our_tail"]:
                print("   ★ 我们的杀尾帖:", r["our_tail"])

print("\n\n=== 有帖子的论坛 ===")
for r in results:
    print(f"  {r['base']}{r['path']}  标题 {r['titles']}  命中 {len(r['our_tail'])}")

(OUT / "full_spread_294.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)
