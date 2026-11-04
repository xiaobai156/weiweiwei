# -*- coding: utf-8 -*-
"""292 期换址：同步 recent_10_cache.json 中 6 站的 url 与失败原因文本（历史记录原样保留）。

用项目自身的 file_lock + 原子替换写入；不改 periods/values/extended。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.persistence.atomic_file import _atomic_write_text_unlocked, file_lock  # noqa: E402

CACHE = ROOT / "recent_10_cache.json"
NEW_ORIGIN = "https://dzdsqxrw.1mppg-x8rsf-cxwlxc.cyou:17455"

# 站名 -> (旧URL, 新URL)
MAP = {
    "龙凤呈祥": (
        "https://tulprhfc.wghcb-bnmgm-hyymaz.work:16655/topic/324698.html",
        f"{NEW_ORIGIN}/topic/324698.html",
    ),
    "可怜春天": (
        "https://jogavu.6bl6s-ilo1w-yfnvvl.work:16677/topic/678625.html",
        f"{NEW_ORIGIN}/topic/678625.html",
    ),
    "正气凛然": (
        "https://whsbrmz.qclrc-4mk42-vnxbyg.work:16677/topic/248009.html",
        f"{NEW_ORIGIN}/topic/248009.html",
    ),
    "违背烟蒂": (
        "https://tulprhfc.wghcb-bnmgm-hyymaz.work:16655/topic/305414.html",
        f"{NEW_ORIGIN}/topic/305414.html",
    ),
    "清清淡淡": (
        "https://iboatq.pjgpm-epbf7-lxpezb.work:16677/topic/324703.html",
        f"{NEW_ORIGIN}/topic/324703.html",
    ),
    "八面驶风": (
        "https://pvxiftuf.yumkw-u4s81-hpytyz.work:16677/topic/559099.html",
        f"{NEW_ORIGIN}/topic/559099.html",
    ),
}


def rewrite(payload: dict) -> tuple[dict, list[str]]:
    changes = []
    old_to_new = {old: new for old, new in MAP.values()}
    for item in payload.get("sites", []):
        name = item.get("name")
        if name not in MAP:
            continue
        old_url, new_url = MAP[name]
        if item.get("url") != old_url:
            changes.append(f"{name}: 缓存url不是预期旧值({item.get('url')})，跳过")
            continue
        item["url"] = new_url
        reasons = item.get("failure_reasons") or {}
        for period, reason in list(reasons.items()):
            reasons[period] = reason.replace(old_url, new_url)
        changes.append(f"{name}: url -> {new_url}")
    rewritten_lines = []
    for line in payload.get("fail_lines") or []:
        text = str(line)
        for old, new in old_to_new.items():
            text = text.replace(old, new)
        rewritten_lines.append(text)
    payload["fail_lines"] = rewritten_lines
    return payload, changes


def main() -> int:
    with file_lock(CACHE):
        payload = json.loads(CACHE.read_text(encoding="utf-8-sig"))
        payload, changes = rewrite(payload)
        _atomic_write_text_unlocked(
            CACHE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    for c in changes:
        print(c)
    print("改动条数:", len([c for c in changes if "->" in c]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
