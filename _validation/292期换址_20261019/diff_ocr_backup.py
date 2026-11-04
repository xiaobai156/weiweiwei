# -*- coding: utf-8 -*-
"""对比 20:24 OCR 备份与当前 292期-尾.txt，确认定向重抓只增加了 6 个换址站。"""
from __future__ import annotations

import re
from pathlib import Path

BASE = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集")
CUR = BASE / "七类数据统一归纳" / "292期-尾.txt"
OCR = BASE / "七类数据统一归纳" / ".ocr-backups" / "292期-尾.txt.bak"
BEFORE = BASE / "杀尾-修复版2" / "_validation" / "292期失败复检_20261019" / "before" / "292期-尾.txt"

RANK = re.compile(r"^\d尾\s+\d+\s+\d+$")


def site_names(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    out = []
    for line in lines:
        if not line.strip() or RANK.match(line):
            continue
        if re.match(r"^\d尾", line):
            out.append(re.sub(r"^(?:\d尾\s+)+", "", line).strip())
    return out


cur = site_names(CUR)
ocr = site_names(OCR)
before = site_names(BEFORE)

print("当前站点数", len(cur))
print("20:24 OCR备份站点数", len(ocr))
print("18:29 原始站点数", len(before))

added_vs_ocr = [n for n in cur if n not in set(ocr)]
removed_vs_ocr = [n for n in ocr if n not in set(cur)]
print("相对OCR备份新增", len(added_vs_ocr), added_vs_ocr)
print("相对OCR备份消失", len(removed_vs_ocr), removed_vs_ocr)

print("OCR备份相对原始新增(即OCR加的)", len([n for n in ocr if n not in set(before)]))
