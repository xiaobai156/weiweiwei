# -*- coding: utf-8 -*-
"""用项目自身 fetch_text（自动解 gzip/字符集）探测书签新式镜像（只读）。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.fetch.http_client import fetch_text  # noqa: E402

OUT = Path(__file__).resolve().parent
TARGETS = [
    ("澳门金算盘", "https://lonwrl.bqy9l-s52t4-zdxbkp.xyz:17488/"),
    ("澳门曾道人", "https://wqpqqc.ek4n8-bsb5r-yiufum.xyz:17466/"),
    ("澳门红财神", "https://oofsukyp.7u9l0-zq8hd-obpxwe.work:29455/"),
]

for name, url in TARGETS:
    print("=" * 64)
    try:
        body = fetch_text(url, 25)
    except Exception as exc:  # noqa: BLE001
        print(name, url, "-> ERR", type(exc).__name__, str(exc)[:100])
        continue
    (OUT / f"mirror_{name}.html").write_text(body, encoding="utf-8")
    print(name, url, "-> len", len(body))
    hrefs = re.findall(r'(?:href|src)="([^"]{2,140})"', body)
    print("  链接数", len(hrefs), "样例:", list(dict.fromkeys(hrefs))[:6])
    plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))
    print("  正文前 400:", plain[:400])
    periods = sorted({int(x) for x in re.findall(r"(?<!\d)(\d{2,4})\s*期", plain)})
    print("  期数尾段:", periods[-8:])
    for kw in ("绝杀一尾", "杀一尾", "一尾", "坚持战斗", "怪咖小生", "澳彩碼王"):
        if kw in plain:
            print(f"  含关键词 {kw}")
