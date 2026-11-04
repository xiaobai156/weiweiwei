# -*- coding: utf-8 -*-
"""六玄网新域名（ulgvaugz…:17455）链路勘察（只读）。

旧链路：入口 -> yjjy/wenzhang.js -> iframe -> cj/zhjs.js
新域名上旧脚本 404，需要重新定位加载器与综合绝杀脚本位置。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.fetch.http_client import fetch_text  # noqa: E402

OUT = Path(__file__).resolve().parent
BASE = "https://ulgvaugz.1vh1x-5fer6-nlzydr.work:17455/"

page = fetch_text(BASE, 25)
(OUT / "liuxuan_new_index.html").write_text(page, encoding="utf-8")

print("首页长度", len(page))
print("含87127:", "87127" in page, "| 含292:", "292" in page, "| 含六玄:", "六玄" in page)

scripts = [urljoin(BASE, m.group(1)) for m in re.finditer(r"""src=["']([^"']+\.js)""", page)]
print("脚本数", len(scripts))
for s in scripts:
    print("  script", s)

iframes = [urljoin(BASE, m.group(1)) for m in re.finditer(r"""<iframe[^>]*src=["']([^"']+)""", page, re.I)]
print("iframe 数", len(iframes))
for i in iframes:
    print("  iframe", i)

# 首页里直接出现的期数锚点
periods = sorted({int(x) for x in re.findall(r"(?<!\d)(\d{2,4})\s*期", page)})
print("首页期数尾段", periods[-8:])
