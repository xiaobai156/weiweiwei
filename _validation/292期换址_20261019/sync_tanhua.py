# -*- coding: utf-8 -*-
"""昙花一现换址：同步缓存与失败清单里的 URL（历史记录原样保留）。

用项目自身 file_lock + 原子替换写入。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.persistence.atomic_file import _atomic_write_text_unlocked, file_lock  # noqa: E402

CACHE = ROOT / "recent_10_cache.json"
FAIL = ROOT.parent / "七类数据统一归纳失败" / "292期-尾-失败.txt"
OLD = "https://www.www144344.com/read.php?tid=1904"
NEW = "http://38.177.253.132:31882/read.php?tid=1904"


def sync_cache() -> int:
    with file_lock(CACHE):
        payload = json.loads(CACHE.read_text(encoding="utf-8-sig"))
        touched = 0
        for item in payload.get("sites", []):
            if item.get("url") != OLD:
                continue
            item["url"] = NEW
            reasons = item.get("failure_reasons") or {}
            for period, reason in list(reasons.items()):
                reasons[period] = str(reason).replace(OLD, NEW)
            touched += 1
        payload["fail_lines"] = [str(l).replace(OLD, NEW) for l in (payload.get("fail_lines") or [])]
        _atomic_write_text_unlocked(
            CACHE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return touched


def sync_fail() -> int:
    if not FAIL.exists():
        return 0
    with file_lock(FAIL):
        text = FAIL.read_text(encoding="utf-8-sig")
        if OLD not in text:
            return 0
        _atomic_write_text_unlocked(FAIL, text.replace(OLD, NEW), encoding="utf-8-sig")
    return 1


cache_hits = sync_cache()
fail_hits = sync_fail()
print("缓存同步条数", cache_hits)
print("失败清单同步条数", fail_hits)
