# -*- coding: utf-8 -*-
"""解封 10 个站：sites.json 与 recent_10_cache.json 去掉 archived 标记。

保留文件原有行尾（\\r\\r\\r\\n），仅删除目标条目的 archived 行。
昙花一现不解封。
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

NAMES = [
    "坚持战斗", "无量寿佛", "再度归来", "童颜鹤发", "一心为民",
    "怪咖小生", "澳彩碼王", "寻宝探码", "财源滚滚", "海角天涯",
]

# ---------- sites.json ----------
with file_lock(SITES_JSON):
    raw = SITES_JSON.read_bytes()
    text = raw.decode("utf-8")
    done = []
    for name in NAMES:
        marker = f'"name": "{name}",'
        idx = text.find(marker)
        if idx < 0:
            print(f"  跳过 {name}：未找到")
            continue
        end = text.find("}", idx)
        seg = text[idx:end]
        if '"archived"' not in seg:
            print(f"  {name} 本来未封存")
            continue
        # 删除 ,<换行>    "archived": true
        new_seg, n = re.subn(
            r',\s*"archived":\s*true\s*$', "", seg.rstrip(), count=1
        )
        if n != 1:
            # 兜底：直接把 archived 行连同前导逗号去掉
            new_seg = re.sub(r',\s*\r*\n\s*"archived":\s*true', "", seg, count=1).rstrip()
        # 保留原结尾空白
        tail = seg[len(seg.rstrip()):]
        text = text[:idx] + new_seg + tail + text[end:]
        done.append(name)
    if done:
        _atomic_write_text_unlocked(SITES_JSON, text, encoding="utf-8")
    print(f"sites.json 解封 {len(done)} 站: {done}")

# ---------- 缓存 ----------
with file_lock(CACHE):
    payload = json.loads(CACHE.read_text(encoding="utf-8-sig"))
    hit = []
    for item in payload.get("sites", []):
        if item.get("name") in NAMES and item.get("archived"):
            item.pop("archived", None)
            hit.append(item["name"])
    active = sum(1 for s in payload["sites"] if not s.get("archived"))
    payload["site_count"] = active
    _atomic_write_text_unlocked(
        CACHE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"缓存解封 {len(hit)} 站，活动站数 {active}")
