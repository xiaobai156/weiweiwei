# -*- coding: utf-8 -*-
"""确认 IP 直连镜像上 292 期昙花一现的取值与方向（bottom 取最后一条）。"""
from __future__ import annotations

import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
body = (OUT / "pw_tanhua_IP直连.txt").read_text(encoding="utf-8")

lines = [l.strip() for l in body.splitlines() if l.strip()]
hits = [(i, l) for i, l in enumerate(lines) if "昙花一现" in l and "绝杀一尾" in l]
print("命中行数", len(hits))
for i, line in hits[:6]:
    print(f"[{i}] {line}")

print("--- 292 期相关行 ---")
for i, l in enumerate(lines):
    if re.search(r"(?<!\d)292\s*期", l):
        print(f"[{i}] {l}")

print("--- 最后 5 条昙花一现记录 ---")
for i, line in hits[-5:]:
    print(f"[{i}] {line}")
