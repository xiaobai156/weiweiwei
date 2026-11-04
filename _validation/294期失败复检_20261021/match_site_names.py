# -*- coding: utf-8 -*-
"""在全部书签条目里按「我们的 10 个站名」精确/模糊匹配（只读）。"""
from __future__ import annotations

import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
ent = json.loads((OUT / "bookmark_hosts_all.json").read_text(encoding="utf-8"))["entries"]

SITES = [
    "坚持战斗", "无量寿佛", "再度归来", "童颜鹤发", "一心为民",
    "怪咖小生", "澳彩碼王", "寻宝探码", "财源滚滚", "海角天涯",
]

print("=== 书签名精确/包含匹配 ===")
for site in SITES:
    rows = []
    for host, items in ent.items():
        for url, bname, src in items:
            b = bname.strip()
            if site in b:
                rows.append((host, b, url))
    uniq = list(dict.fromkeys(rows))
    print(f"\n{site}: {len(uniq)} 条")
    for host, b, url in uniq[:6]:
        print(f"    {host:36s} {b[:26]:28s} {url}")

print("\n\n=== 书签里所有「论坛/bbs」类条目的名称清单（人工比对用） ===")
names = sorted({
    bname.strip()
    for items in ent.values()
    for _, bname, _ in items
    if bname.strip()
})
print(f"共 {len(names)} 个名称")
for n in names:
    print("  ", n[:40])
