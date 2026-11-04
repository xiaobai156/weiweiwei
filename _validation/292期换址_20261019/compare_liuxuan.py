# -*- coding: utf-8 -*-
"""六玄网新域名 vs 旧域名/缓存 历史逐期对比（只读）。

判定依据：同期开奖号相同但绝杀值不同 => 同名不同源，不可换址。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
CACHE = ROOT / "recent_10_cache.json"

NEW_FRAME = OUT / "liuxuan_new_frame0.txt"
OLD_ZHJS = ROOT / "_validation" / "292期失败复检_20261019" / "liuxuan_zhjs.html"

row_re = re.compile(
    r"(\d{3})期\s*[:：]\s*绝杀\s*[【\[]\s*(\d)\s*头\s*[.．]\s*(\d)\s*尾\s*[.．]\s*"
    r"(红|蓝|绿)\s*(单|双)\s*[.．]\s*(\S{1,3}?)肖\s*[】\]]\s*开\s*[:：]?\s*(\S{1,6}?)(?:\s*(准|错|奖))?"
)


def parse(text: str) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    for m in row_re.finditer(text):
        period = int(m.group(1))
        rows.setdefault(period, {
            "head": int(m.group(2)),
            "tail": int(m.group(3)),
            "color": m.group(4) + m.group(5),
            "zodiac": m.group(6),
            "draw": m.group(7).strip(),
        })
    return rows


new_text = NEW_FRAME.read_text(encoding="utf-8")
old_text = OLD_ZHJS.read_text(encoding="utf-8")
new_rows = parse(new_text)
old_rows = parse(old_text)

cache = json.loads(CACHE.read_text(encoding="utf-8-sig"))
cached: dict[int, str] = {}
for item in cache["sites"]:
    if item["name"] == "六玄网":
        cached = {int(p): str(v) for p, v in zip(item["periods"], item["values"])}

print(f"{'期':>5} {'旧域名尾':>8} {'新域名尾':>8} {'缓存尾':>6} {'旧开奖':>6} {'新开奖':>6}  结论")
periods = sorted(set(old_rows) | set(new_rows) | set(cached), reverse=True)[:12]
mismatch = 0
for p in periods:
    o = old_rows.get(p, {})
    n = new_rows.get(p, {})
    c = cached.get(p)
    o_tail = o.get("tail")
    n_tail = n.get("tail")
    o_draw = o.get("draw", "")
    n_draw = n.get("draw", "")
    same_draw = o_draw and n_draw and o_draw == n_draw
    verdict = ""
    if o_tail is not None and n_tail is not None and o_tail != n_tail:
        verdict = "值不同" + ("(开奖同)" if same_draw else "(开奖也不同)")
        mismatch += 1
    elif n_tail is not None and c is not None and str(n_tail) != c:
        verdict = "与缓存不符"
        mismatch += 1
    elif n_tail is not None:
        verdict = "一致"
    print(f"{p:>5} {str(o_tail):>8} {str(n_tail):>8} {str(c):>6} {o_draw:>6} {n_draw:>6}  {verdict}")

print()
print("旧域名(87127) 最新期", max(old_rows) if old_rows else None)
print("新域名 最新期", max(new_rows) if new_rows else None)
print("冲突期数", mismatch)
