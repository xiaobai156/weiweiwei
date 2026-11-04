# -*- coding: utf-8 -*-
"""封存六玄网：recent_10_cache.json 该条加 archived:true，历史 periods/values 原样保留。

用项目自身 file_lock + 原子替换。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.persistence.atomic_file import _atomic_write_text_unlocked, file_lock  # noqa: E402

CACHE = ROOT / "recent_10_cache.json"
NAME = "六玄网"

with file_lock(CACHE):
    payload = json.loads(CACHE.read_text(encoding="utf-8-sig"))
    hits = 0
    for item in payload.get("sites", []):
        if item.get("name") != NAME:
            continue
        item["archived"] = True
        hits += 1
    if hits != 1:
        raise SystemExit(f"中止：缓存中匹配到 {hits} 条")
    active = sum(1 for s in payload["sites"] if not s.get("archived"))
    payload["site_count"] = active
    _atomic_write_text_unlocked(
        CACHE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
print("缓存已封存六玄网，活动站数", active)
