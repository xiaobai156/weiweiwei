# -*- coding: utf-8 -*-
"""赤兔 293 期「稳杀一头」栏目正文核查（只读）。"""
from __future__ import annotations

import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
body = (OUT / "pw_赤兔_293.txt").read_text(encoding="utf-8")

# 找所有 293 期出现处，打印上下文
idxs = [m.start() for m in re.finditer(r"(?<!\d)293\s*期", body)]
print("293 出现次数", len(idxs))
for i in idxs[:12]:
    seg = re.sub(r"\s+", " ", body[max(0, i - 100): i + 260])
    print("---", i)
    print(seg)

print("\n=== 稳杀一头 相关 ===")
for m in re.finditer("稳杀", body):
    s = m.start()
    print("---", s)
    print(re.sub(r"\s+", " ", body[max(0, s - 80): s + 300]))
    if s > 60000:
        break
