# -*- coding: utf-8 -*-
"""从 recent_10_cache.json 重建指定期的成功 TXT。

用法：python rebuild_tail_txt.py 303
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2")
sys.path.insert(0, str(ROOT))

from shawei.config.constants import TWO_TAIL_SITE_URLS
from shawei.persistence.atomic_file import atomic_write_text
from shawei.persistence.txt_writer import format_ranking

CACHE = ROOT / "recent_10_cache.json"
OUT_DIR = ROOT.parent / "七类数据统一归纳"


def build(period: int) -> Path:
    payload = json.loads(CACHE.read_text(encoding="utf-8-sig"))
    if period not in range(payload["period"], payload["period"] - int(payload["window"]), -1):
        raise SystemExit(f"{period} 不在缓存窗口内")
    lines: list[str] = []
    values: list[str] = []
    skipped: list[str] = []
    for item in payload["sites"]:
        if item.get("archived"):
            continue
        periods = [int(p) for p in item.get("periods") or []]
        if period not in periods:
            skipped.append(item["name"])
            continue
        value = str(item["values"][periods.index(period)])
        url = str(item.get("url") or "")
        labels = (
            " ".join(f"{v}尾" for v in value.split("、"))
            if url in TWO_TAIL_SITE_URLS
            else f"{value}尾"
        )
        lines.append(f"{labels} {item['name']}")
        values.append(value)
    out = format_ranking(lines, values)
    target = OUT_DIR / f"{period}期-尾.txt"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_text(target, "\n".join(out) + "\n", encoding="utf-8-sig")
    print(f"{period}期-尾.txt 站点 {len(lines)} 条，跳过无数据 {len(skipped)} 条: {skipped}")
    print(f"总行 {len(out)}，写出 {target}")
    return target


if __name__ == "__main__":
    build(int(sys.argv[1]))
