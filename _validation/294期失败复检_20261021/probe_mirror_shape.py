# -*- coding: utf-8 -*-
"""探测书签里新式镜像（带端口）的首页结构，确认帖子链接形式（只读）。"""
from __future__ import annotations

import re
import ssl
from pathlib import Path
from urllib.request import Request, urlopen

OUT = Path(__file__).resolve().parent
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
ctx = ssl._create_unverified_context()

TARGETS = [
    ("澳门金算盘", "https://lonwrl.bqy9l-s52t4-zdxbkp.xyz:17488/"),
    ("澳门曾道人", "https://wqpqqc.ek4n8-bsb5r-yiufum.xyz:17466/"),
    ("澳门红财神", "https://oofsukyp.7u9l0-zq8hd-obpxwe.work:29455/"),
]


def get(url: str, timeout: int = 25) -> tuple[int, str]:
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=timeout, context=ctx) as r:
            raw = r.read()
            code = r.status
    except Exception as exc:  # noqa: BLE001
        return 0, f"ERR {type(exc).__name__}: {str(exc)[:100]}"
    for enc in ("utf-8", "gb18030"):
        try:
            return code, raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return code, raw.decode("utf-8", errors="replace")


for name, url in TARGETS:
    code, body = get(url)
    print("=" * 60)
    print(name, url, "->", code, len(body))
    if code == 0:
        print("  ", body[:120])
        continue
    fn = OUT / f"mirror_{name}.html"
    fn.write_text(body, encoding="utf-8")
    # 链接形式
    hrefs = re.findall(r'(?:href|src)="([^"]{2,120})"', body)
    topic_like = [h for h in hrefs if "topic" in h or "read.php" in h or "id=" in h]
    print("  链接样例 topic 类:", topic_like[:6])
    hashes = re.findall(r'"(#[A-Za-z0-9/_.=\-]{2,60})"', body)
    print("  hash 路由样例:", list(dict.fromkeys(hashes))[:8])
    plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))
    print("  正文前 300:", plain[:300])
    periods = sorted({int(x) for x in re.findall(r"(?<!\d)(\d{2,4})\s*期", plain)})
    print("  期数尾段:", periods[-6:])
