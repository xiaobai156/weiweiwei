# -*- coding: utf-8 -*-
"""赤兔 293 期表格行核查：定位含「杀一肖/杀半波/杀一尾/杀一头」的表，看最新期号（只读）。"""
from __future__ import annotations

import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
body = (OUT / "pw_赤兔_293.txt").read_text(encoding="utf-8")
lines = [l.strip() for l in body.splitlines() if l.strip()]

print("总非空行", len(lines))

# 找表头
for i, l in enumerate(lines):
    if "杀一肖" in l and "杀一尾" in l:
        print("表头行", i, repr(l[:200]))

# 找「杀一尾」出现的行，打印周围
hits = [i for i, l in enumerate(lines) if "杀一尾" in l]
print("含杀一尾的行数", len(hits))

# 找形如 293/292 期 + 尾 的数据行
row_re = re.compile(r"(?<!\d)(\d{2,4})\s*期")
data_rows = []
for i, l in enumerate(lines):
    if "尾" in l and row_re.search(l):
        data_rows.append((i, l))

print("含期数且含尾的行数", len(data_rows))
for i, l in data_rows[:12]:
    print(f"[{i}] {l[:200]}")

print("\n=== 最后 20 行 ===")
for i, l in enumerate(lines[-20:], start=len(lines) - 20):
    print(f"[{i}] {l[:160]}")
