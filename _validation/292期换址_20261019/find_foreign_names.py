# -*- coding: utf-8 -*-
"""跨项目查找「紫燕儿尾」等 30 个外来站名的配置来源（只读，多编码兜底）。"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集")
NEEDLES = ["紫燕儿尾", "君军两尾", "华林尾", "大小姐", "姨妈尾杀"]

hits = []
for path in BASE.rglob("*.json"):
    parts = {p.lower() for p in path.parts}
    if {"__pycache__", "browser-profile", "node_modules", ".git"} & parts:
        continue
    if path.stat().st_size > 20_000_000:
        continue
    text = None
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            text = path.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, OSError):
            continue
    if not text:
        continue
    found = [n for n in NEEDLES if n in text]
    if found:
        hits.append((str(path.relative_to(BASE)), found))

for rel, found in hits:
    print(rel, "->", found)
print("命中文件数", len(hits))
