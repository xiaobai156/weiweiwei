# -*- coding: utf-8 -*-
"""打印 7 个站当前 rules.py 规则块，用于按原字段克隆新规则（只读）。"""
from __future__ import annotations

import re
from pathlib import Path

RULES = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\shawei\config\rules.py")
text = RULES.read_text(encoding="utf-8")

OLD = [
    "https://0130190827.673454.xyz/bbs/topic.php?id=20144",
    "https://67806780827.325346.xyz/bbs/topic.php?id=19812",
    "https://88888020827.983654.xyz/bbs/topic.php?id=20758",
    "https://12388990827.794555.xyz/bbs/topic.php?id=21353",
    "https://12388990827.688756.xyz/bbs/topic.php?id=18520",
    "https://12388990827.688756.xyz/bbs/topic.php?id=19930",
    "https://88888020827.997595.xyz/bbs/topic.php?id=18490",
]

for url in OLD:
    idx = text.find(f'"{url}"')
    if idx < 0:
        idx = text.find(f"'{url}'")
    if idx < 0:
        print(f"!!! 未找到 {url}")
        continue
    line_start = text.rfind("\n", 0, idx) + 1
    indent = re.match(r"(\s*)", text[line_start:]).group(1)
    end = text.find("\n" + indent + "),", idx)
    block = text[line_start: end + len("\n" + indent + "),")]
    print("=== ", url)
    print(block)
    print()
