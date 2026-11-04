# -*- coding: utf-8 -*-
"""昙花一现论坛页检索：首页与相邻帖是否出现 293/294 期数据（只读）。"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen
import ssl

OUT = Path(__file__).resolve().parent
BASE = "http://38.177.253.132:31882"
PERIOD_RE = re.compile(r"(?<!\d)(\d{2,4})\s*期")

ctx = ssl._create_unverified_context()
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def get(url: str) -> str:
    with urlopen(Request(url, headers=HEADERS), timeout=25, context=ctx) as r:
        raw = r.read()
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


# 1) 首页里找 昙花一现 的链接
index = get(BASE + "/")
(OUT / "tanhua_index.html").write_text(index, encoding="utf-8")
links = re.findall(r'href="([^"]*read\.php\?tid=\d+[^"]*)"[^>]*>([^<]{0,60})', index)
named = [x for x in links if "昙花" in x[1] or "绝杀一尾" in x[1]]
print("首页链接总数", len(links), "｜含昙花/绝杀一尾", len(named))
for href, text in named[:10]:
    print("  ", href, "|", text.strip())

# 2) 检查相邻帖 1905 是否有 293/294 的昙花一现
for tid in (1904, 1905):
    html = get(f"{BASE}/read.php?tid={tid}")
    plain = re.sub(r"<[^>]+>", " ", html)
    plain = re.sub(r"\s+", " ", plain)
    periods = sorted({int(x) for x in PERIOD_RE.findall(plain)})
    has293 = 293 in periods
    has294 = 294 in periods
    title = re.search(r"主题\s*:\s*([^<]{0,80})", re.sub(r"<[^>]+>", " ", html))
    print(f"\ntid={tid} 期数尾段 {periods[-8:]} | 293={has293} 294={has294}")
    print("   标题:", (title.group(1).strip() if title else "")[:80])
    for m in re.finditer(r"(?<!\d)(293|294)\s*期", plain):
        s = m.start()
        print("   CTX:", plain[max(0, s - 100): s + 200][:280])
        break
