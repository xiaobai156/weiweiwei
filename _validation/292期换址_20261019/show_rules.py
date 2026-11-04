# -*- coding: utf-8 -*-
"""打印 6 个换址站对应的 rules.py 规则块原文（只读）。"""
from __future__ import annotations

import re
from pathlib import Path

RULES = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\shawei\config\rules.py")
text = RULES.read_text(encoding="utf-8")

for topic in ("324698", "678625", "248009", "305414", "324703", "559099"):
    idx = text.find(topic)
    while idx != -1:
        line_start = text.rfind("\n", 0, idx) + 1
        line = text[line_start: text.find("\n", idx)]
        if "StrictRule(" in line:
            indent = re.match(r"(\s*)", line).group(1)
            end = text.find("\n" + indent + "),", idx)
            block = text[line_start: end + len("\n" + indent + "),")]
            print("=== topic", topic)
            print(block)
            print()
            break
        idx = text.find(topic, idx + 1)
