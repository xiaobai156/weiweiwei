# -*- coding: utf-8 -*-
"""跨项目查找 294 期 10 个不可达站的最新地址（只读）。

场景：DNS 被解析到 198.18.x.x 假段、TLS 握手失败，可能站方已换域名。
在合集内所有 sites.json / targets.json / 缓存里按站名找同名站的其他 URL。
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集")
NAMES = [
    "坚持战斗", "无量寿佛", "再度归来", "童颜鹤发", "一心为民",
    "怪咖小生", "澳彩碼王", "寻宝探码", "财源滚滚", "海角天涯",
]

hits: dict[str, list[tuple[str, str]]] = {n: [] for n in NAMES}

for path in list(BASE.glob("*/sites.json")) + list(BASE.glob("*/targets.json")) + list(
    BASE.glob("*/config/sites.json")
) + list(BASE.glob("*/config/targets.json")) + list(BASE.glob("*/recent_10_cache.json")):
    if not path.is_file():
        continue
    text = None
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            text = path.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, OSError):
            continue
    if not text or not any(n in text for n in NAMES):
        continue
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        continue

    def walk(node):
        if isinstance(node, dict):
            name = str(node.get("name") or node.get("site_name") or "")
            url = str(node.get("url") or "")
            if name in NAMES and url:
                hits[name].append((str(path.relative_to(BASE)), url))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)

for n in NAMES:
    print(f"=== {n}")
    seen = set()
    for proj, url in hits[n]:
        key = (proj, url)
        if key in seen:
            continue
        seen.add(key)
        print(f"   {proj}  {url}")
    if not seen:
        print("   （其他项目也未登记）")
