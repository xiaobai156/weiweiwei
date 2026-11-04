# -*- coding: utf-8 -*-
"""封存「再度归来」：sites.json 与 recent_10_cache.json 加 archived:true。

沿用本项目既有做法（内联 archived 字段，不写 archived_sites.json）。
缓存保留 periods/values 历史。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.persistence.atomic_file import _atomic_write_text_unlocked, file_lock  # noqa: E402

SITES_JSON = ROOT / "sites.json"
CACHE = ROOT / "recent_10_cache.json"
NAME = "再度归来"

# ---------- 1. sites.json 字节级插入 ----------
with file_lock(SITES_JSON):
    text = SITES_JSON.read_text(encoding="utf-8")
    marker = f'"name": "{NAME}",'
    idx = text.find(marker)
    if idx < 0:
        raise SystemExit(f"未找到 {NAME}")
    end = text.find("}", idx)
    seg = text[idx:end]
    if '"archived"' in seg:
        print("sites.json 已封存")
    else:
        m = re.search(r'("pick":\s*"[^"]*")', seg)
        if not m:
            raise SystemExit("未找到 pick 字段")
        # 沿用文件实际行尾（此处为 \r\r\n）
        eol = "\r\r\n" if "\r\r\n" in text else "\n"
        new_seg = seg.replace(m.group(1), m.group(1) + f",{eol}    \"archived\": true", 1)
        text = text[:idx] + new_seg + text[end:]
        _atomic_write_text_unlocked(SITES_JSON, text, encoding="utf-8")
        print("sites.json 已封存")

# ---------- 2. 缓存 ----------
with file_lock(CACHE):
    payload = json.loads(CACHE.read_text(encoding="utf-8-sig"))
    hit = 0
    for item in payload.get("sites", []):
        if item.get("name") == NAME:
            item["archived"] = True
            hit += 1
    active = sum(1 for s in payload["sites"] if not s.get("archived"))
    payload["site_count"] = active
    _atomic_write_text_unlocked(
        CACHE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"缓存封存 {hit} 条，活动站数 {active}")
