# -*- coding: utf-8 -*-
"""核对 292期-尾.txt 结构：站点行、排行行、重复、与配置的差集。"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集")
SUCCESS = BASE / "七类数据统一归纳" / "292期-尾.txt"
SITES = BASE / "杀尾-修复版2" / "sites.json"

lines = SUCCESS.read_text(encoding="utf-8-sig").splitlines()
rank_re = re.compile(r"^\d尾\s+\d+\s+\d+$")
site_lines = [l for l in lines if l.strip() and re.match(r"^\d尾", l) and not rank_re.match(l)]
rank_lines = [l for l in lines if rank_re.match(l)]

names = []
for line in site_lines:
    name = re.sub(r"^(?:\d尾\s+)+", "", line).strip()
    names.append(name)

print("总行", len(lines))
print("空行", sum(1 for l in lines if not l.strip()))
print("站点行", len(site_lines))
print("排行行", len(rank_lines))
print("唯一站名", len(set(names)))

dup = [(n, c) for n, c in Counter(names).items() if c > 1]
print("重复站名", len(dup), dup[:20])

sites = json.loads(SITES.read_text(encoding="utf-8-sig"))
active = [s["name"] for s in sites if not s.get("archived")]
print("活动配置站数", len(active))
missing = [n for n in active if n not in set(names)]
extra = [n for n in set(names) if n not in set(active)]
print("配置有但TXT没有", len(missing), missing)
print("TXT有但配置没有", len(extra), extra)

tails = 0
for line in site_lines:
    tails += len(re.findall(r"\d尾", line))
rank_sum = sum(int(re.split(r"\s+", l)[1]) for l in rank_lines)
print("尾数合计", tails, "排行合计", rank_sum)
