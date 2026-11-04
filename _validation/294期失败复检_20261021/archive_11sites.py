# -*- coding: utf-8 -*-
"""294 期 11 个失败站封存：sites.json + recent_10_cache.json 加 archived:true。

- 字节级最小改动，保留原文件 \\r\\r\\n 行尾
- 缓存保留 periods/values 历史，仅追加 archived:true
- 封存后不写正式 TXT、不抓取
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.persistence.atomic_file import _atomic_write_text_unlocked, file_lock  # noqa: E402

SITES_JSON = ROOT / "sites.json"
CACHE = ROOT / "recent_10_cache.json"

NAMES = [
    "坚持战斗", "无量寿佛", "再度归来", "童颜鹤发", "一心为民",
    "怪咖小生", "澳彩碼王", "寻宝探码", "财源滚滚", "海角天涯", "昙花一现",
]

# ---------- 1. sites.json：字节级插入 archived ----------
with file_lock(SITES_JSON):
    raw = SITES_JSON.read_bytes()
    text = raw.decode("utf-8")
    done = []
    for name in NAMES:
        marker = f'"name": "{name}",'
        idx = text.find(marker)
        if idx < 0:
            print(f"  跳过 {name}：sites.json 未找到")
            continue
        # 该条目的 url / pick 行
        seg_start = idx
        seg_end = text.find("}", seg_start)
        seg = text[seg_start:seg_end]
        if '"archived"' in seg:
            print(f"  已封存 {name}")
            continue
        # 在 pick 行末追加 ,"archived": true
        import re
        m = re.search(r'("pick":\s*"[^"]*")', seg)
        if not m:
            print(f"  跳过 {name}：未找到 pick 字段")
            continue
        pick_literal = m.group(1)
        new_seg = seg.replace(pick_literal, pick_literal + ',\r\r\n    "archived": true', 1)
        text = text[:seg_start] + new_seg + text[seg_end:]
        done.append(name)
    if done:
        _atomic_write_text_unlocked(SITES_JSON, text, encoding="utf-8")
    print(f"sites.json 封存 {len(done)} 站: {done}")

# ---------- 2. 缓存 ----------
with file_lock(CACHE):
    payload = json.loads(CACHE.read_text(encoding="utf-8-sig"))
    hit = []
    for item in payload.get("sites", []):
        if item.get("name") in NAMES and not item.get("archived"):
            item["archived"] = True
            hit.append(item["name"])
    active = sum(1 for s in payload["sites"] if not s.get("archived"))
    payload["site_count"] = active
    _atomic_write_text_unlocked(
        CACHE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"缓存封存 {len(hit)} 站，活动站数 {active}")
