# -*- coding: utf-8 -*-
"""295 期 7 站换址：
1) rules.py 按原常量克隆新 URL 规则（旧条目保留）
2) sites.json 改 url
3) recent_10_cache.json 改 url + 失败原因文本

用项目自身 file_lock + 原子替换。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.persistence.atomic_file import _atomic_write_text_unlocked, file_lock  # noqa: E402

RULES = ROOT / "shawei" / "config" / "rules.py"
SITES = ROOT / "sites.json"
CACHE = ROOT / "recent_10_cache.json"

# 站名 -> (旧URL, 新URL, 规则常量)
MAP = {
    "再度归来": (
        "https://0130190827.673454.xyz/bbs/topic.php?id=20144",
        "https://0130190827.673454.xyz/bbs/topic.php?id=20330",
        "_SCANNED_TOPIC_TWO_TAIL_RULE",
    ),
    "童颜鹤发": (
        "https://67806780827.325346.xyz/bbs/topic.php?id=19812",
        "https://67806780827.325346.xyz/bbs/topic.php?id=19581",
        "_SCANNED_TOPIC_SINGLE_TAIL_RULE",
    ),
    "一心为民": (
        "https://88888020827.983654.xyz/bbs/topic.php?id=20758",
        "https://88888020827.983654.xyz/bbs/topic.php?id=20915",
        "_SCANNED_TOPIC_SINGLE_TAIL_RULE",
    ),
    "澳彩碼王": (
        "https://12388990827.794555.xyz/bbs/topic.php?id=21353",
        "https://12388990827.794555.xyz/bbs/topic.php?id=19959",
        "_SCANNED_TOPIC_SINGLE_TAIL_RULE",
    ),
    "寻宝探码": (
        "https://12388990827.688756.xyz/bbs/topic.php?id=18520",
        "https://12388990827.688756.xyz/bbs/topic.php?id=19155",
        "_SCANNED_TOPIC_SINGLE_TAIL_RULE",
    ),
    "财源滚滚": (
        "https://12388990827.688756.xyz/bbs/topic.php?id=19930",
        "https://12388990827.688756.xyz/bbs/topic.php?id=19128",
        "_SCANNED_TOPIC_SINGLE_TAIL_RULE",
    ),
    "海角天涯": (
        "https://88888020827.997595.xyz/bbs/topic.php?id=18490",
        "https://88888020827.997595.xyz/bbs/topic.php?id=19471",
        "_SCANNED_TOPIC_SINGLE_TAIL_RULE",
    ),
}

# ---------- 1. rules.py 新增规则 ----------
with file_lock(RULES):
    text = RULES.read_text(encoding="utf-8")
    added = []
    for name, (old, new, const) in MAP.items():
        key = f'"{new}": {const},'
        if key in text:
            print(f"  规则已存在 {name}")
            continue
        old_line = f'        "{old}": {const},'
        if old_line not in text:
            print(f"  !!! 未找到旧规则行 {name}: {old_line[:70]}")
            continue
        text = text.replace(old_line, old_line + "\n" + f'        "{new}": {const},', 1)
        added.append(name)
    if added:
        _atomic_write_text_unlocked(RULES, text, encoding="utf-8")
    print(f"rules.py 新增 {len(added)} 条: {added}")

# ---------- 2. sites.json ----------
with file_lock(SITES):
    raw = SITES.read_bytes()
    stext = raw.decode("utf-8")
    changed = []
    for name, (old, new, _c) in MAP.items():
        if f'"{new}"' in stext:
            print(f"  sites.json 已是新地址 {name}")
            continue
        if f'"{old}"' not in stext:
            print(f"  !!! sites.json 未找到旧地址 {name}")
            continue
        stext = stext.replace(f'"{old}"', f'"{new}"', 1)
        changed.append(name)
    if changed:
        _atomic_write_text_unlocked(SITES, stext, encoding="utf-8")
    print(f"sites.json 改址 {len(changed)} 站: {changed}")

# ---------- 3. 缓存 ----------
with file_lock(CACHE):
    payload = json.loads(CACHE.read_text(encoding="utf-8-sig"))
    hits = []
    for item in payload.get("sites", []):
        name = item.get("name")
        if name not in MAP:
            continue
        old, new, _c = MAP[name]
        if item.get("url") == old:
            item["url"] = new
            for p, reason in list((item.get("failure_reasons") or {}).items()):
                item["failure_reasons"][p] = str(reason).replace(old, new)
            hits.append(name)
        elif item.get("url") == new:
            print(f"  缓存已是新地址 {name}")
    lines = []
    for line in payload.get("fail_lines") or []:
        t = str(line)
        for name, (old, new, _c) in MAP.items():
            t = t.replace(old, new)
        lines.append(t)
    payload["fail_lines"] = lines
    _atomic_write_text_unlocked(
        CACHE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"缓存改址 {len(hits)} 站: {hits}")
